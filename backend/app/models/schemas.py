"""
Pydantic schemas for the Medical Clinic Booking System.
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid


class Gender(str, Enum):
    """Gender enumeration."""
    MALE = "male"
    FEMALE = "female"


class TransactionStatus(str, Enum):
    """Transaction workflow status."""
    INITIATED = "initiated"
    VALIDATING = "validating"
    VALIDATION_COMPLETED = "validation_completed"
    PRICING = "pricing"
    PRICING_COMPLETED = "pricing_completed"
    CHECKING_QUOTA = "checking_quota"
    QUOTA_RESERVED = "quota_reserved"
    QUOTA_EXHAUSTED = "quota_exhausted"
    BOOKING = "booking"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class EventType(str, Enum):
    """Event types for the SAGA workflow."""
    BOOKING_INITIATED = "booking.initiated"
    VALIDATION_STARTED = "validation.started"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATION_FAILED = "validation.failed"
    PRICING_STARTED = "pricing.started"
    PRICING_COMPLETED = "pricing.completed"
    QUOTA_CHECK_STARTED = "quota.check_started"
    QUOTA_RESERVED = "quota.reserved"
    QUOTA_RESERVED_OVER_LIMIT = "quota.reserved_over_limit"  # display: reserve first, then check fails
    QUOTA_EXHAUSTED = "quota.exhausted"
    BOOKING_STARTED = "booking.started"
    BOOKING_COMPLETED = "booking.completed"
    BOOKING_FAILED = "booking.failed"
    COMPENSATION_STARTED = "compensation.started"
    COMPENSATION_COMPLETED = "compensation.completed"


class MedicalService(BaseModel):
    """Medical service model."""
    id: str
    name: str
    price: float
    description: Optional[str] = None


class UserInput(BaseModel):
    """User input data."""
    name: str = Field(..., min_length=1, max_length=100)
    gender: Gender
    date_of_birth: date
    
    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return v


class BookingRequest(BaseModel):
    """Booking request from client."""
    user: UserInput
    service_ids: List[str] = Field(..., min_length=1)


class BookingResponse(BaseModel):
    """Booking response to client."""
    request_id: str
    status: TransactionStatus
    message: str


class StatusUpdate(BaseModel):
    """Real-time status update."""
    request_id: str
    status: TransactionStatus
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


class BookingResult(BaseModel):
    """Final booking result."""
    request_id: str
    success: bool
    reference_id: Optional[str] = None
    base_price: Optional[float] = None
    discount_applied: bool = False
    discount_percentage: Optional[float] = None
    discount_reason: Optional[str] = None
    final_price: Optional[float] = None
    error_message: Optional[str] = None
    services: List[MedicalService] = []


class TransactionState(BaseModel):
    """Transaction state stored in Redis."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    status: TransactionStatus = TransactionStatus.INITIATED
    user: UserInput
    service_ids: List[str]
    services: List[MedicalService] = []
    base_price: float = 0.0
    final_price: float = 0.0
    discount_applied: bool = False
    discount_percentage: float = 0.0
    discount_reason: Optional[str] = None
    r1_eligible: bool = False
    quota_reserved: bool = False
    quota_key: Optional[str] = None
    reference_id: Optional[str] = None
    error_message: Optional[str] = None
    events: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add_event(self, event_type: EventType, message: str, details: Optional[Dict] = None):
        """Add event to audit trail."""
        self.events.append({
            "type": event_type.value,
            "message": message,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        })
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage."""
        data = self.model_dump()
        data["user"]["date_of_birth"] = self.user.date_of_birth.isoformat()
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionState":
        """Create from dictionary (Redis retrieval)."""
        if isinstance(data["user"]["date_of_birth"], str):
            data["user"]["date_of_birth"] = date.fromisoformat(data["user"]["date_of_birth"])
        if isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class EventPayload(BaseModel):
    """Event message payload."""
    event_type: EventType
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = {}
