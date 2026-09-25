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
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
