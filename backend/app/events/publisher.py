"""
Redis event publisher for the SAGA workflow.
Uses Redis Streams for event-driven communication.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import redis.asyncio as redis

from app.config import settings
from app.models.schemas import EventType, EventPayload, TransactionState

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes events to Redis Streams."""
    
    STREAM_NAME = "booking:events"
    MAX_STREAM_LENGTH = 100  # Keep last 100 events to save space
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    async def get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                username=settings.redis_username,
                password=settings.redis_password,
                decode_responses=True
            )
        return self._redis
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    async def publish_event(
        self,
        event_type: EventType,
        request_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish an event to the Redis stream.
        Returns the message ID.
        """
        r = await self.get_redis()
        
        payload = EventPayload(
            event_type=event_type,
            request_id=request_id,
            data=data or {}
        )
        
        # Publish to stream with auto-trimming
        message_id = await r.xadd(
            self.STREAM_NAME,
            {
                "event_type": event_type.value,
                "request_id": request_id,
                "data": json.dumps(payload.data),
                "timestamp": datetime.utcnow().isoformat()
            },
            maxlen=self.MAX_STREAM_LENGTH
        )
        
        logger.info(
            f"Published event: {event_type.value}",
            extra={
                "event_type": event_type.value,
                "request_id": request_id,
                "message_id": message_id
            }
        )
        
        return message_id
    
    async def save_transaction_state(self, state: TransactionState) -> None:
        """Save transaction state to Redis."""
        r = await self.get_redis()
        key = f"txn:{state.request_id}"
        
        await r.set(
            key,
            json.dumps(state.to_dict()),
            ex=settings.transaction_ttl_seconds
        )
        
        logger.debug(
            f"Saved transaction state: {state.request_id}",
            extra={"status": state.status.value}
        )
    
    async def get_transaction_state(self, request_id: str) -> Optional[TransactionState]:
        """Retrieve transaction state from Redis."""
        r = await self.get_redis()
        key = f"txn:{request_id}"
        
        data = await r.get(key)
        if data:
            return TransactionState.from_dict(json.loads(data))
        return None
    
    async def update_transaction_status(
        self,
        request_id: str,
        status: str,
        event_type: EventType,
        message: str,
        details: Optional[Dict] = None
    ) -> Optional[TransactionState]:
        """Update transaction status and add event."""
        state = await self.get_transaction_state(request_id)
        if state:
            from app.models.schemas import TransactionStatus
            state.status = TransactionStatus(status)
            state.add_event(event_type, message, details)
            await self.save_transaction_state(state)
        return state


# Global publisher instance
event_publisher = EventPublisher()
