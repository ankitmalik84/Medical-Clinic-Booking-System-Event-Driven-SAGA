"""
Pricing service for the booking workflow.
Calculates prices and determines R1 discount eligibility.
"""

import logging
from datetime import date
from typing import Tuple

from app.config import settings
from app.models.schemas import (
    TransactionState,
    EventType,
    TransactionStatus,
    Gender
)
from app.data.services import calculate_base_price
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class PricingService:
    """Calculates pricing and discount eligibility."""
    
    def _is_birthday_today(self, dob: date) -> bool:
        """Check if today is the user's birthday (IST)."""
        today = settings.get_current_time_ist().date()
        return dob.month == today.month and dob.day == today.day
    
    def _calculate_r1_eligibility(
        self,
        gender: Gender,
        dob: date,
        base_price: float
    ) -> Tuple[bool, str]:
        """
        Check R1 discount eligibility.
        
        R1: Apply discount if:
        - (User is female AND today is their birthday) -> 12%
        - (Base price sum > ₹1000) -> 12%
        
        Returns:
            Tuple of (is_eligible, reason)
        """
        is_birthday = self._is_birthday_today(dob)
        is_female = gender == Gender.FEMALE
        is_high_value = base_price > settings.high_value_threshold
        
        if is_female and is_birthday:
            return True, "Birthday discount (Female)"
        elif is_high_value:
            return True, f"High-value order (>₹{settings.high_value_threshold})"
        
        return False, ""
    
    async def calculate_price(self, state: TransactionState) -> Tuple[bool, str]:
        """
        Calculate pricing for the booking.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(
            f"Calculating price: {state.request_id}",
            extra={"services": [s.name for s in state.services]}
        )
        
        # Update status
        state.status = TransactionStatus.PRICING
        state.add_event(
            EventType.PRICING_STARTED,
            "Starting price calculation"
        )
        await event_publisher.save_transaction_state(state)
        
        await event_publisher.publish_event(
            EventType.PRICING_STARTED,
            state.request_id
        )
        
        try:
            # Calculate base price
            base_price = calculate_base_price(state.services)
            state.base_price = base_price
            
            # Check R1 discount eligibility
            is_r1_eligible, discount_reason = self._calculate_r1_eligibility(
                state.user.gender,
                state.user.date_of_birth,
                base_price
            )
            
            state.r1_eligible = is_r1_eligible
            
            if is_r1_eligible:
                state.discount_percentage = settings.discount_percentage
                state.discount_reason = discount_reason
                # Final price will be calculated after quota check
                state.final_price = base_price  # Tentative
                
                logger.info(
                    f"R1 discount eligible: {state.request_id}",
                    extra={"reason": discount_reason, "base_price": base_price}
                )
            else:
                # No discount - final price equals base price
                state.discount_applied = False
                state.discount_percentage = 0
                state.final_price = base_price
            
            # Update state
            state.status = TransactionStatus.PRICING_COMPLETED
            state.add_event(
                EventType.PRICING_COMPLETED,
                f"Base price: ₹{base_price}. R1 eligible: {is_r1_eligible}",
                {
                    "base_price": base_price,
                    "r1_eligible": is_r1_eligible,
                    "discount_reason": discount_reason
                }
            )
            await event_publisher.save_transaction_state(state)
            
            await event_publisher.publish_event(
                EventType.PRICING_COMPLETED,
                state.request_id,
                {
                    "base_price": base_price,
                    "r1_eligible": is_r1_eligible
                }
            )
            
            return True, f"Pricing completed. Base price: ₹{base_price}"
            
        except Exception as e:
            error_msg = f"Pricing error: {str(e)}"
            state.status = TransactionStatus.FAILED
            state.error_message = error_msg
            state.add_event(EventType.PRICING_COMPLETED, error_msg)
            await event_publisher.save_transaction_state(state)
            
            logger.error(
                f"Pricing failed: {state.request_id}",
                extra={"error": str(e)}
            )
            
            return False, error_msg


# Global service instance
pricing_service = PricingService()
