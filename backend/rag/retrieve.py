from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from backend.models.decisions import PolicyClause
from backend.rag.ingest import load_policy_clauses

if TYPE_CHECKING:
    from backend.services.ai import AIService

TOKEN = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> list[str]:
    return [word for word in TOKEN.findall(text.lower()) if len(word) > 2]


class PolicyRetriever:
    """Version-filtered policy retrieval with a deterministic offline backend."""

    def __init__(self, policy_dir: str | Path | None = None):
        self.policy_dir = Path(policy_dir or os.getenv("CONTROLLEDGER_POLICY_DIR", "data/policies"))
        self.clauses = load_policy_clauses(self.policy_dir)
        self._idf = self._build_idf()

    def _build_idf(self) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for clause in self.clauses:
            document_frequency.update(set(_terms(clause.text + " " + clause.category)))
        total = max(len(self.clauses), 1)
        return {
            term: math.log((total + 1) / (frequency + 1)) + 1
            for term, frequency in document_frequency.items()
        }

    def retrieve(
        self, query: str, *, version: str = "1.0", category: str | None = None, top_k: int = 6
    ) -> list[PolicyClause]:
        query_terms = Counter(_terms(query))
        scored: list[PolicyClause] = []
        for clause in self.clauses:
            if clause.version != version:
                continue
            clause_terms = Counter(
                _terms(clause.text + " " + clause.category + " " + clause.clause_id)
            )
            score = sum(
                query_terms[term] * clause_terms[term] * self._idf.get(term, 1)
                for term in query_terms
            )
            if category and clause.category in {category, "travel"}:
                score += 3
            if category == "meals" and clause.clause_id.startswith("MEALS"):
                score += 4
            score /= max(math.sqrt(sum(value * value for value in clause_terms.values())), 1)
            scored.append(clause.model_copy(update={"score": min(round(score / 5, 4), 1)}))
        return sorted(scored, key=lambda item: (-item.score, item.clause_id))[:top_k]


class ChromaPolicyRetriever(PolicyRetriever):
    """ChromaDB retrieval with explicit Gemini or local test embeddings."""

    def __init__(
        self,
        policy_dir: str | Path | None = None,
        persist_directory: str = ".chromadb",
        ai_service: AIService | None = None,
    ):
        super().__init__(policy_dir)
        import chromadb

        from backend.services.ai import AIService

        self.ai_service = ai_service or AIService()
        client = chromadb.PersistentClient(path=persist_directory)
        provider = self.ai_service.provider if self.ai_service.live else "local"
        model = self.ai_service.embedding_model if self.ai_service.live else "hash-v1"
        safe_model = re.sub(r"[^a-z0-9_-]", "_", model.lower())
        self.collection = client.get_or_create_collection(f"policy_clauses_{provider}_{safe_model}")
        ids = [clause.clause_id for clause in self.clauses]
        documents = [clause.text for clause in self.clauses]
        existing = self.collection.get(ids=ids, include=["documents"])
        existing_documents = dict(zip(existing["ids"], existing["documents"], strict=True))
        index_current = len(existing_documents) == len(ids) and all(
            existing_documents.get(clause_id) == document
            for clause_id, document in zip(ids, documents, strict=True)
        )
        if index_current:
            self.embedding_metadata = {
                "provider": provider,
                "operation": "embedding_index_cache",
                "model": model,
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        else:
            embedded = self.ai_service.embed(documents, task="document")
            self.embedding_metadata = embedded.metadata
            self.collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embedded.value,
                metadatas=[
                    {
                        "policy_name": clause.policy_name,
                        "version": clause.version,
                        "effective_date": clause.effective_date,
                        "category": clause.category,
                        "jurisdiction": clause.jurisdiction,
                    }
                    for clause in self.clauses
                ],
            )

    def retrieve(
        self, query: str, *, version: str = "1.0", category: str | None = None, top_k: int = 6
    ) -> list[PolicyClause]:
        where: dict[str, str] = {"version": version}
        embedded_query = self.ai_service.embed([query], task="query")
        self.embedding_metadata = embedded_query.metadata
        result = self.collection.query(
            query_embeddings=embedded_query.value,
            n_results=top_k,
            where=where,
        )
        clauses: list[PolicyClause] = []
        for clause_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=True,
        ):
            clauses.append(
                PolicyClause(
                    clause_id=clause_id,
                    text=text,
                    score=max(0, min(1, 1 - distance)),
                    **metadata,
                )
            )
        return clauses


def build_retriever(ai_service: AIService | None = None) -> PolicyRetriever:
    if os.getenv("CONTROLLEDGER_RAG_BACKEND", "chroma").lower() == "chroma":
        return ChromaPolicyRetriever(ai_service=ai_service)
    return PolicyRetriever()
