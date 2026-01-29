"""
Validation service for the booking workflow.
Validates user input and service selections.
"""

import logging
from typing import List, Tuple

from app.models.schemas import (
    UserInput,
    TransactionState,
    EventType,
    TransactionStatus,
    MedicalService
)
from app.data.services import get_services_by_ids
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class ValidationService:
    """Validates user input and service selections."""
    
    async def validate(self, state: TransactionState) -> Tuple[bool, str, List[MedicalService]]:
        """
        Validate user input and service selections.
        
        Returns:
            Tuple of (is_valid, message, services)
        """
        logger.info(
            f"Validating request: {state.request_id}",
            extra={"user": state.user.name, "services": state.service_ids}
        )
        
        # Update status to validating
        state.status = TransactionStatus.VALIDATING
        state.add_event(
            EventType.VALIDATION_STARTED,
            "Starting validation of user input and services"
        )
        await event_publisher.save_transaction_state(state)
        
        # Publish event
        await event_publisher.publish_event(
            EventType.VALIDATION_STARTED,
            state.request_id,
            {"user_name": state.user.name}
        )
        
        try:
            # Validate user name
            if not state.user.name or len(state.user.name.strip()) < 2:
                raise ValueError("Name must be at least 2 characters long")
            
            # Validate service selections
            if not state.service_ids:
                raise ValueError("At least one service must be selected")
            
            # Get and validate services
            services = get_services_by_ids(
                state.service_ids,
                state.user.gender.value
            )
            
            # Update state with validated services
            state.services = services
            state.status = TransactionStatus.VALIDATION_COMPLETED
            state.add_event(
                EventType.VALIDATION_COMPLETED,
                f"Validation successful. {len(services)} services selected.",
                {"services": [s.name for s in services]}
            )
            await event_publisher.save_transaction_state(state)
            
            # Publish success event
            await event_publisher.publish_event(
                EventType.VALIDATION_COMPLETED,
                state.request_id,
                {"service_count": len(services)}
            )
            
            logger.info(
                f"Validation completed: {state.request_id}",
                extra={"services": [s.name for s in services]}
            )
            
            return True, "Validation successful", services
            
        except ValueError as e:
            error_msg = str(e)
            state.status = TransactionStatus.FAILED
            state.error_message = error_msg
            state.add_event(
                EventType.VALIDATION_FAILED,
                f"Validation failed: {error_msg}"
            )
            await event_publisher.save_transaction_state(state)
            
            # Publish failure event
            await event_publisher.publish_event(
                EventType.VALIDATION_FAILED,
                state.request_id,
                {"error": error_msg}
            )
            
            logger.warning(
                f"Validation failed: {state.request_id}",
                extra={"error": error_msg}
            )
            
            return False, error_msg, []


# Global service instance
validation_service = ValidationService()
