# Build from repo root: docker build -f services/pricing-booking/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

# Copy backend (shared app) and this service
COPY backend/ ./backend/
COPY services/pricing-booking/ ./services/pricing-booking/

WORKDIR /app/services/pricing-booking
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/backend
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
