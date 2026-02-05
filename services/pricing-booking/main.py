"""
Pricing + Quota + Booking microservice for the Medical Clinic Booking System.
Exposes POST /price, /reserve-quota, /create-booking, /release-quota for GCP Workflows.
Expects PYTHONPATH to include the backend app (e.g. PYTHONPATH=../../backend).
"""

import logging
import sys
from pathlib import Path

# Ensure backend app is on path (for local run and Docker with PYTHONPATH=/app/backend)
_backend = Path(__file__).resolve().parent.parent.parent / "backend"
if _backend.exists() and str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from fastapi import FastAPI
from pydantic import BaseModel

from app.events.publisher import event_publisher
from app.services.pricing import pricing_service
from app.services.quota import quota_service
from app.services.booking import booking_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pricing & Booking Service",
    description="Pricing, quota, and booking microservice for booking SAGA",
    version="1.0.0",
)


class RequestIdBody(BaseModel):
    request_id: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pricing-booking"}


@app.post("/price")
async def price(body: RequestIdBody):
    """Calculate price and R1 eligibility. Used by GCP Workflows."""
    request_id = body.request_id
    logger.info("Price request", extra={"request_id": request_id})

    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        return {"success": False, "message": "Booking not found"}

    ok, message = await pricing_service.calculate_price(state)
    return {
        "success": ok,
        "message": message or ("Pricing completed" if ok else "Pricing failed"),
        "r1_eligible": getattr(state, "r1_eligible", False),
    }


@app.post("/reserve-quota")
async def reserve_quota(body: RequestIdBody):
    """Reserve discount quota (R2). Used by GCP Workflows."""
    request_id = body.request_id
    logger.info("Reserve quota request", extra={"request_id": request_id})

    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        return {"success": False, "message": "Booking not found"}

    ok, message = await quota_service.try_reserve_quota(state)
    return {"success": ok, "message": message or ("Quota reserved" if ok else "Quota exhausted")}


@app.post("/create-booking")
async def create_booking(body: RequestIdBody):
    """Create final booking. Used by GCP Workflows."""
    request_id = body.request_id
    logger.info("Create booking request", extra={"request_id": request_id})

    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        return {"success": False, "message": "Booking not found"}

    ok, message = await booking_service.create_booking(state)
    reference_id = getattr(state, "reference_id", None)
    return {
        "success": ok,
        "message": message or ("Booking created" if ok else "Booking failed"),
        "reference_id": reference_id,
    }


@app.post("/release-quota")
async def release_quota(body: RequestIdBody):
    """Release reserved quota (compensation). Used by GCP Workflows on failure."""
    request_id = body.request_id
    logger.info("Release quota request", extra={"request_id": request_id})

    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        return {"success": True, "message": "No state to compensate"}

    released = await quota_service.release_quota(state)
    return {"success": released, "message": "Quota released" if released else "Release failed"}
