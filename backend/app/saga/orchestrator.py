"""
SAGA Orchestrator for the booking workflow.
Coordinates the entire transaction flow with proper error handling.
"""

import logging
from typing import Optional

from app.models.schemas import (
    TransactionState,
    TransactionStatus,
    BookingRequest,
    BookingResult,
    EventType
)
from app.services.validation import validation_service
from app.services.pricing import pricing_service
from app.services.quota import quota_service
from app.services.booking import booking_service
from app.saga.compensation import compensation_handler
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class BookingSagaOrchestrator:
    """
    Orchestrates the booking SAGA workflow.
    
    Flow:
    1. Validation → 2. Pricing → 3. Quota Check (if R1 eligible) → 4. Booking
    
    On failure at any step, compensation is triggered to rollback.
    """
    
    async def execute(self, request: BookingRequest) -> BookingResult:
        """
        Execute the complete booking SAGA.
        
        Args:
            request: The booking request from the client
            
        Returns:
            BookingResult with success/failure details
        """
        # Initialize transaction state
        state = TransactionState(
            user=request.user,
            service_ids=request.service_ids
        )
        
        logger.info(
            f"SAGA started: {state.request_id}",
            extra={
                "user": state.user.name,
                "gender": state.user.gender.value,
                "services": state.service_ids
            }
        )
        
        # Save initial state
        state.add_event(
            EventType.BOOKING_INITIATED,
            f"Booking request initiated for {state.user.name}"
        )
        await event_publisher.save_transaction_state(state)
        
        await event_publisher.publish_event(
            EventType.BOOKING_INITIATED,
            state.request_id,
            {"user_name": state.user.name}
        )
        
        try:
            # Step 1: Validation
            logger.info(f"Step 1 - Validation: {state.request_id}")
            is_valid, message, services = await validation_service.validate(state)
            
            if not is_valid:
                logger.warning(f"Validation failed: {state.request_id} - {message}")
                return booking_service.build_result(state)
            
            # Step 2: Pricing
            logger.info(f"Step 2 - Pricing: {state.request_id}")
            pricing_success, pricing_message = await pricing_service.calculate_price(state)
            
            if not pricing_success:
                logger.warning(f"Pricing failed: {state.request_id} - {pricing_message}")
                await self._handle_failure(state)
                return booking_service.build_result(state)
            
            # Step 3: Quota Check (only if R1 eligible)
            if state.r1_eligible:
                logger.info(f"Step 3 - Quota Check: {state.request_id}")
                quota_success, quota_message = await quota_service.try_reserve_quota(state)
                
                if not quota_success:
                    logger.warning(f"Quota check failed: {state.request_id} - {quota_message}")
                    # No compensation needed - quota wasn't reserved
                    return booking_service.build_result(state)
            
            # Step 4: Create Booking
            logger.info(f"Step 4 - Create Booking: {state.request_id}")
            booking_success, booking_message = await booking_service.create_booking(state)
            
            if not booking_success:
                logger.warning(f"Booking failed: {state.request_id} - {booking_message}")
                await self._handle_failure(state)
                return booking_service.build_result(state)
            
            # Success!
            logger.info(
                f"SAGA completed successfully: {state.request_id}",
                extra={
                    "reference_id": state.reference_id,
                    "final_price": state.final_price
                }
            )
            
            return booking_service.build_result(state)
            
        except Exception as e:
            logger.error(
                f"SAGA exception: {state.request_id}",
                extra={"error": str(e)},
                exc_info=True
            )
            state.status = TransactionStatus.FAILED
            state.error_message = f"Unexpected error: {str(e)}"
            await event_publisher.save_transaction_state(state)
            await self._handle_failure(state)
            return booking_service.build_result(state)
    
    async def _handle_failure(self, state: TransactionState) -> None:
        """Handle failure by triggering compensation."""
        logger.info(f"Handling failure, triggering compensation: {state.request_id}")
        await compensation_handler.compensate(state)
    
    async def get_status(self, request_id: str) -> Optional[TransactionState]:
        """Get current transaction status."""
        return await event_publisher.get_transaction_state(request_id)


# Global orchestrator instance
saga_orchestrator = BookingSagaOrchestrator()
