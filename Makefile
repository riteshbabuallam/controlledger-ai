.PHONY: install test lint evaluate ai-smoke seed api dashboard mcp

install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check backend dashboard scripts tests

evaluate:
	.venv/bin/python scripts/evaluate.py --output outputs/evaluation_results.json

ai-smoke:
	.venv/bin/python scripts/smoke_ai.py

seed:
	.venv/bin/python scripts/seed_demo.py

api:
	.venv/bin/uvicorn backend.main:app --reload

dashboard:
	.venv/bin/streamlit run dashboard/app.py

mcp:
	.venv/bin/python -m backend.mcp_server.server
