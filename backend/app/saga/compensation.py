"""
Compensation handlers for the SAGA workflow.
Handles rollback operations when failures occur.
"""

import logging
from typing import Optional

from app.models.schemas import (
    TransactionState,
    EventType,
    TransactionStatus
)
from app.services.quota import quota_service
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class CompensationHandler:
    """Handles compensation (rollback) operations for failed transactions."""
    
    async def compensate(self, state: TransactionState) -> bool:
        """
        Execute compensation based on the current transaction state.
        
        Determines what resources were allocated and rolls them back.
        
        Returns:
            True if compensation completed successfully
        """
        logger.info(
            f"Starting compensation: {state.request_id}",
            extra={
                "status": state.status.value,
                "quota_reserved": state.quota_reserved
            }
        )
        
        # Update status
        state.status = TransactionStatus.COMPENSATING
        state.add_event(
            EventType.COMPENSATION_STARTED,
            "Starting compensation for failed transaction"
        )
        await event_publisher.save_transaction_state(state)
        
        await event_publisher.publish_event(
            EventType.COMPENSATION_STARTED,
            state.request_id
        )
        
        compensation_actions = []
        success = True
        
        try:
            # Compensate quota if it was reserved
            if state.quota_reserved:
                logger.info(f"Releasing quota for: {state.request_id}")
                quota_released = await quota_service.release_quota(state.request_id)
                
                if quota_released:
                    compensation_actions.append("Quota released")
                    state.quota_reserved = False
                    logger.info(f"Quota released successfully: {state.request_id}")
                else:
                    compensation_actions.append("Quota release FAILED")
                    success = False
                    logger.error(f"Failed to release quota: {state.request_id}")
            
            # Update final state
            state.status = TransactionStatus.COMPENSATED
            state.add_event(
                EventType.COMPENSATION_COMPLETED,
                f"Compensation completed. Actions: {', '.join(compensation_actions) or 'None required'}",
                {"actions": compensation_actions}
            )
            await event_publisher.save_transaction_state(state)
            
            await event_publisher.publish_event(
                EventType.COMPENSATION_COMPLETED,
                state.request_id,
                {"actions": compensation_actions}
            )
            
            logger.info(
                f"Compensation completed: {state.request_id}",
                extra={"actions": compensation_actions}
            )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Compensation error: {state.request_id}",
                extra={"error": str(e)}
            )
            state.add_event(
                EventType.COMPENSATION_COMPLETED,
                f"Compensation error: {str(e)}"
            )
            await event_publisher.save_transaction_state(state)
            return False


# Global handler instance
compensation_handler = CompensationHandler()
