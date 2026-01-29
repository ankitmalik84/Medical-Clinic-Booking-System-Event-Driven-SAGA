"""
Booking service for the booking workflow.
Creates final booking records.
"""

import logging
import random
import string
from datetime import datetime
from typing import Tuple

from app.config import settings
from app.models.schemas import (
    TransactionState,
    EventType,
    TransactionStatus,
    BookingResult
)
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class BookingService:
    """Creates and manages bookings."""
    
    def _generate_reference_id(self) -> str:
        """Generate a unique booking reference ID."""
        today = settings.get_today_ist().replace("-", "")
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"BK-{today}-{random_part}"
    
    async def create_booking(self, state: TransactionState) -> Tuple[bool, str]:
        """
        Create the final booking.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(
            f"Creating booking: {state.request_id}",
            extra={
                "user": state.user.name,
                "final_price": state.final_price
            }
        )
        
        # Update status
        state.status = TransactionStatus.BOOKING
        state.add_event(
            EventType.BOOKING_STARTED,
            "Creating booking record"
        )
        await event_publisher.save_transaction_state(state)
        
        await event_publisher.publish_event(
            EventType.BOOKING_STARTED,
            state.request_id
        )
        
        try:
            # Check if failure simulation is enabled (for testing)
            if settings.simulate_booking_failure:
                raise Exception("Simulated booking failure for testing")
            
            # Generate reference ID
            reference_id = self._generate_reference_id()
            state.reference_id = reference_id
            
            # Mark as completed
            state.status = TransactionStatus.COMPLETED
            state.add_event(
                EventType.BOOKING_COMPLETED,
                f"Booking confirmed with reference: {reference_id}",
                {
                    "reference_id": reference_id,
                    "final_price": state.final_price,
                    "discount_applied": state.discount_applied
                }
            )
            await event_publisher.save_transaction_state(state)
            
            await event_publisher.publish_event(
                EventType.BOOKING_COMPLETED,
                state.request_id,
                {"reference_id": reference_id}
            )
            
            logger.info(
                f"Booking completed: {state.request_id}",
                extra={
                    "reference_id": reference_id,
                    "final_price": state.final_price
                }
            )
            
            return True, f"Booking confirmed: {reference_id}"
            
        except Exception as e:
            error_msg = f"Booking failed: {str(e)}"
            state.status = TransactionStatus.FAILED
            state.error_message = error_msg
            state.add_event(
                EventType.BOOKING_FAILED,
                error_msg
            )
            await event_publisher.save_transaction_state(state)
            
            await event_publisher.publish_event(
                EventType.BOOKING_FAILED,
                state.request_id,
                {"error": str(e)}
            )
            
            logger.error(
                f"Booking failed: {state.request_id}",
                extra={"error": str(e)}
            )
            
            return False, error_msg
    
    def build_result(self, state: TransactionState) -> BookingResult:
        """Build the final booking result from transaction state."""
        return BookingResult(
            request_id=state.request_id,
            success=state.status == TransactionStatus.COMPLETED,
            reference_id=state.reference_id,
            base_price=state.base_price,
            discount_applied=state.discount_applied,
            discount_percentage=state.discount_percentage if state.discount_applied else None,
            discount_reason=state.discount_reason,
            final_price=state.final_price,
            error_message=state.error_message,
            services=state.services
        )


# Global service instance
booking_service = BookingService()
