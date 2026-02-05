"""
Validation microservice for the Medical Clinic Booking System.
Exposes POST /validate for GCP Workflows (and other orchestrators).
Expects PYTHONPATH to include the backend app (e.g. PYTHONPATH=../../backend).
"""

import logging
import sys
from pathlib import Path

# Ensure backend app is on path (for local run and Docker with PYTHONPATH=/app/backend)
_backend = Path(__file__).resolve().parent.parent.parent / "backend"
if _backend.exists() and str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.events.publisher import event_publisher
from app.services.validation import validation_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Validation Service", description="Validation microservice for booking SAGA", version="1.0.0")


class ValidateRequest(BaseModel):
    request_id: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "validation"}


@app.post("/validate")
async def validate(body: ValidateRequest):
    """Validate user and services for a booking. Used by GCP Workflows."""
    request_id = body.request_id
    logger.info("Validation request", extra={"request_id": request_id})

    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        logger.warning("Booking not found", extra={"request_id": request_id})
        return {"success": False, "message": "Booking not found"}

    ok, message, _ = await validation_service.validate(state)
    return {"success": ok, "message": message or ("Validation successful" if ok else "Validation failed")}
