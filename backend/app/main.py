"""
FastAPI main application for the Medical Clinic Booking System.
"""

import logging
import json
from datetime import datetime
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

from app.config import settings
from app.models.schemas import (
    BookingRequest,
    BookingResponse,
    BookingResult,
    TransactionStatus,
    StatusUpdate,
    Gender,
    MedicalService,
    TransactionState,
    EventType
)
from app.data.services import get_services_by_gender
from app.saga.choreography import saga_choreographer
from app.services.quota import quota_service
from app.events.publisher import event_publisher

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra)s' if hasattr(logging, 'extra') else '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Custom JSON formatter for structured logging
class StructuredLogFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Safely extract extra fields added via logger.info(msg, extra={...})
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName', 'extra'
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_data[key] = value
        
        return json.dumps(log_data)


# Apply structured logging
for handler in logging.root.handlers:
    handler.setFormatter(StructuredLogFormatter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Medical Clinic Booking System")
    logger.info(f"Daily discount quota: {settings.daily_discount_quota}")
    logger.info(f"Discount percentage: {settings.discount_percentage}%")
    await saga_choreographer.start()
    yield
    logger.info("Shutting down Medical Clinic Booking System")
    await event_publisher.close()


app = FastAPI(
    title="Medical Clinic Booking System",
    description="Event-driven booking system with SAGA pattern",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models for API
class ServicesResponse(BaseModel):
    gender: str
    services: list[MedicalService]


class QuotaStatus(BaseModel):
    date: str
    current_count: int
    max_quota: int
    remaining: int


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    redis_connected: bool


class SimulateFailureRequest(BaseModel):
    enable: bool


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    redis_ok = False
    try:
        r = await event_publisher.get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass
    
    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        redis_connected=redis_ok
    )


@app.get("/services/{gender}", response_model=ServicesResponse)
async def get_services(gender: str):
    """Get available services for a gender."""
    try:
        # Validate gender
        gender_enum = Gender(gender.lower())
        services = get_services_by_gender(gender_enum.value)
        return ServicesResponse(gender=gender, services=services)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid gender. Use 'male' or 'female'")


@app.post("/booking", response_model=BookingResponse)
async def create_booking(request: BookingRequest, background_tasks: BackgroundTasks):
    """
    Submit a booking request.
    Returns immediately with request_id for status tracking.
    """
    logger.info(
        f"Received booking request",
        extra={
            "user": request.user.name,
            "gender": request.user.gender.value,
            "services": request.service_ids
        }
    )
    # Create initial transaction state
    state = TransactionState(
        user=request.user,
        service_ids=request.service_ids
    )
    
    # Save initial state and publish first event
    await event_publisher.save_transaction_state(state)
    await event_publisher.publish_event(EventType.BOOKING_INITIATED, state.request_id)
    
    return BookingResponse(
        request_id=state.request_id,
        status=TransactionStatus.INITIATED,
        message="Booking request received and being processed"
    )


@app.get("/booking/{request_id}/result", response_model=BookingResult)
async def get_booking_result(request_id: str):
    """Get the final booking result."""
    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    from app.services.booking import booking_service
    return booking_service.build_result(state)


@app.get("/booking/{request_id}/status")
async def get_booking_status(request_id: str):
    """Get current booking status."""
    state = await event_publisher.get_transaction_state(request_id)
    if not state:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    return {
        "request_id": state.request_id,
        "status": state.status.value,
        "events": state.events,
        "error_message": state.error_message
    }


@app.get("/booking/{request_id}/stream")
async def stream_booking_status(request_id: str):
    """
    Server-Sent Events stream for real-time status updates.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        last_event_count = 0
        max_wait = 60  # Maximum wait time in seconds
        start_time = datetime.utcnow()
        
        while True:
            state = await event_publisher.get_transaction_state(request_id)
            
            if not state:
                yield f"data: {json.dumps({'error': 'Booking not found'})}\n\n"
                break
            
            # Send new events
            if len(state.events) > last_event_count:
                for event in state.events[last_event_count:]:
                    update = StatusUpdate(
                        request_id=state.request_id,
                        status=state.status,
                        message=event.get("message", ""),
                        timestamp=datetime.fromisoformat(event.get("timestamp", datetime.utcnow().isoformat())),
                        details=event.get("details")
                    )
                    yield f"data: {update.model_dump_json()}\n\n"
                last_event_count = len(state.events)
            
            # Check if terminal state
            if state.status in [
                TransactionStatus.COMPLETED,
                TransactionStatus.COMPENSATED,
                TransactionStatus.QUOTA_EXHAUSTED
            ]:
                # Send final result
                from app.services.booking import booking_service
                result = booking_service.build_result(state)
                yield f"data: {json.dumps({'final_result': result.model_dump()})}\n\n"
                break
            
            # Timeout check
            elapsed = (datetime.utcnow() - start_time).seconds
            if elapsed > max_wait:
                yield f"data: {json.dumps({'error': 'Timeout waiting for booking completion'})}\n\n"
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# Admin endpoints for testing

@app.get("/admin/quota", response_model=QuotaStatus)
async def get_quota_status():
    """Get current quota status."""
    current = await quota_service.get_current_quota_count()
    remaining = await quota_service.get_remaining_quota()
    
    return QuotaStatus(
        date=settings.get_today_ist(),
        current_count=current,
        max_quota=settings.daily_discount_quota,
        remaining=remaining
    )


@app.post("/admin/quota/reset")
async def reset_quota():
    """Reset quota to 0 (testing only)."""
    success = await quota_service.reset_quota()
    return {"success": success, "message": "Quota reset" if success else "Failed to reset quota"}


@app.post("/admin/quota/set/{count}")
async def set_quota(count: int):
    """Set quota to specific value (testing only)."""
    success = await quota_service.set_quota_count(count)
    return {"success": success, "count": count}


@app.post("/admin/simulate-failure")
async def toggle_failure_simulation(request: SimulateFailureRequest):
    """Toggle booking failure simulation (testing only)."""
    # Store in Redis for persistence
    r = await event_publisher.get_redis()
    await r.set("simulate_failure", "1" if request.enable else "0")
    
    # Also update settings (for current instance)
    settings.simulate_booking_failure = request.enable
    
    return {
        "success": True,
        "simulate_failure": request.enable,
        "message": f"Failure simulation {'enabled' if request.enable else 'disabled'}"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
