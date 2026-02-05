# Build from repo root: docker build -f services/validation/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

# Copy backend (shared app) and this service
COPY backend/ ./backend/
COPY services/validation/ ./services/validation/

WORKDIR /app/services/validation
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/backend
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
