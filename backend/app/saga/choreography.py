"""
SAGA Choreography implementation using Redis Streams.
"""

import logging
import json
import asyncio
from typing import Dict, Any

from app.models.schemas import TransactionState, TransactionStatus, EventType
from app.events.publisher import event_publisher
from app.services.validation import validation_service
from app.services.pricing import pricing_service
from app.services.quota import quota_service
from app.services.booking import booking_service
from app.saga.compensation import compensation_handler

logger = logging.getLogger(__name__)

class SagaChoreographer:
    """
    Coordinates the SAGA workflow using Choreography pattern.
    Listens to events on the Redis Stream and triggers the next step.
    """
    
    def __init__(self):
        self.is_running = False
        self._last_id = "0"
    
    async def start(self):
        """Start the event listener loop."""
        if self.is_running:
            return
        
        # We use '$' to get ONLY new events arriving from this point forward.
        # This prevents the choreographer from "replaying" old events on restart.
        self._last_id = "$"
        self.is_running = True
        logger.info(f"SAGA Choreographer starting listener on stream: {event_publisher.STREAM_NAME}")
        asyncio.create_task(self._listen_for_events())

    async def _listen_for_events(self):
        """Listen for new events on the Redis Stream."""
        while self.is_running:
            try:
                r = await event_publisher.get_redis()
                # Read new messages from the stream
                # Use '$' on the first call to only get NEW events, then use the last message ID
                current_id = self._last_id
                events = await r.xread({event_publisher.STREAM_NAME: current_id}, count=5, block=2000)
                
                if not events:
                    continue

                for stream_name, messages in events:
                    for message_id, data in messages:
                        self._last_id = message_id
                        event_type = data.get("event_type")
                        request_id = data.get("request_id")
                        
                        if event_type and request_id:
                            logger.info(f"Choreography: Reacting to '{event_type}' for {request_id}")
                            await self.handle_event(event_type, request_id)
                        
            except Exception as e:
                logger.error(f"Error in Choreography loop: {str(e)}")
                await asyncio.sleep(1)

    async def handle_event(self, event_type: str, request_id: str):
        """Route event to the next service in the chain."""
        state = await event_publisher.get_transaction_state(request_id)
        if not state:
            return

        try:
            # Choreography routing table
            if event_type == EventType.BOOKING_INITIATED:
                # 1. Initiated -> Start Validation
                await validation_service.validate(state)

            elif event_type == EventType.VALIDATION_COMPLETED:
                # 2. Validated -> Start Pricing
                await pricing_service.calculate_price(state)

            elif event_type == EventType.PRICING_COMPLETED:
                # 3. Priced -> Check Quota (if R1) or Go to Booking
                if state.r1_eligible:
                    await quota_service.try_reserve_quota(state)
                else:
                    # Skip R2 check, manually publish skip event
                    await event_publisher.publish_event(
                        EventType.QUOTA_RESERVED, 
                        request_id, 
                        {"skipped": True, "reason": "Not R1 eligible"}
                    )

            elif event_type == EventType.QUOTA_RESERVED:
                # 4. Quota Reserved -> Finalize Booking
                await booking_service.create_booking(state)

            elif event_type in [EventType.BOOKING_FAILED, EventType.QUOTA_EXHAUSTED, EventType.VALIDATION_FAILED]:
                # 5. Any critical failure -> Trigger Compensation
                if event_type != EventType.BOOKING_FAILED: # Booking failure handled separately in booking service
                     await self._handle_failure(state, state.error_message or "Process failed")
                else:
                    # If booking fails, trigger compensation immediately
                    await self._handle_failure(state, state.error_message or "Booking failed")

        except Exception as e:
            logger.error(f"SAGA Choreography error for {request_id}: {str(e)}")
            await self._handle_failure(state, str(e))

    async def _handle_failure(self, state: TransactionState, error_message: str):
        """Handle failure and trigger compensation."""
        # Update state with failure info
        state.status = TransactionStatus.FAILED
        state.error_message = error_message
        state.add_event(EventType.BOOKING_FAILED, f"Transaction failed: {error_message}")
        await event_publisher.save_transaction_state(state)
        
        logger.warning(f"SAGA Compensation triggered for {state.request_id}: {error_message}")
        await compensation_handler.compensate(state)

saga_choreographer = SagaChoreographer()
