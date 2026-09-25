from __future__ import annotations

import os
from dataclasses import dataclass
from time import perf_counter


@dataclass
class ExecutionTracker:
    model_identifier: str = "deterministic-evidence-v1"
    prompt_version: str = "risk-explanation-v1"
    model_calls: int = 0
    tool_calls: int = 0
    estimated_cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    ai_calls: list[dict] | None = None
    started_at: float = 0.0

    def start(self) -> None:
        self.started_at = perf_counter()
        self.ai_calls = []

    def record_ai_call(self, metadata: dict) -> None:
        if metadata.get("provider") not in {"offline", "deterministic_fallback"}:
            self.model_calls += 1
        input_tokens = int(metadata.get("input_tokens", 0) or 0)
        output_tokens = int(metadata.get("output_tokens", 0) or 0)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        call_cost = self._estimated_call_cost(metadata, input_tokens, output_tokens)
        metadata["estimated_cost_usd"] = call_cost
        self.estimated_cost_usd += call_cost
        if self.ai_calls is not None:
            self.ai_calls.append(metadata)

    @staticmethod
    def _estimated_call_cost(metadata: dict, input_tokens: int, output_tokens: int) -> float:
        if metadata.get("provider") in {"offline", "deterministic_fallback"}:
            return 0.0
        if metadata.get("operation") == "embedding":
            input_rate = float(os.getenv("CONTROLLEDGER_EMBEDDING_INPUT_USD_PER_M", "0"))
            output_rate = 0.0
        else:
            input_rate = float(os.getenv("CONTROLLEDGER_LLM_INPUT_USD_PER_M", "0"))
            output_rate = float(os.getenv("CONTROLLEDGER_LLM_OUTPUT_USD_PER_M", "0"))
        return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 8)

    def metadata(self) -> dict:
        return {
            "model_identifier": self.model_identifier,
            "prompt_version": self.prompt_version,
            "parameters": {"temperature": 0, "structured_output": True},
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "ai_calls": self.ai_calls or [],
            "latency_ms": round((perf_counter() - self.started_at) * 1000, 2)
            if self.started_at
            else 0,
        }
