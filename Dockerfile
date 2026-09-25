FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend backend
COPY dashboard dashboard
COPY data data
COPY scripts scripts
RUN pip install --no-cache-dir .

ENV CONTROLLEDGER_DB_PATH=/app/data/controlledger.db
EXPOSE 8000
CMD ["sh", "-c", "CONTROLLEDGER_AI_MODE=offline python scripts/seed_demo.py && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
