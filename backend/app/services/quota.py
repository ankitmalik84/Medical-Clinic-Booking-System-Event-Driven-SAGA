"""
Quota service for the booking workflow.
Manages R2 daily discount quota with atomic Redis operations.
"""

import logging
from typing import Tuple
import redis.asyncio as redis

from app.config import settings
from app.models.schemas import (
    TransactionState,
    EventType,
    TransactionStatus
)
from app.events.publisher import event_publisher

logger = logging.getLogger(__name__)


class QuotaService:
    """Manages daily discount quota (R2 rule)."""
    
    QUOTA_KEY_PREFIX = "quota_v2:discount:"
    
    def __init__(self):
        self._redis = None
    
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
    
    def _get_quota_key(self) -> str:
        """Get today's quota key (IST date)."""
        today = settings.get_today_ist()
        return f"{self.QUOTA_KEY_PREFIX}{today}"
    
    async def get_current_quota_count(self) -> int:
        """Get current discount count for today."""
        r = await self.get_redis()
        count = await r.get(self._get_quota_key())
        return int(count) if count else 0
    
    async def get_remaining_quota(self) -> int:
        """Get remaining quota for today."""
        current = await self.get_current_quota_count()
        return max(0, settings.daily_discount_quota - current)
    
    async def try_reserve_quota(self, state: TransactionState) -> Tuple[bool, str]:
        """
        Try to reserve a discount quota slot.
        Uses atomic INCR to prevent race conditions.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(
            f"Checking quota: {state.request_id}",
            extra={"r1_eligible": state.r1_eligible}
        )
        
        # If not R1 eligible, skip quota check
        if not state.r1_eligible:
            logger.info(f"Skipping quota check (not R1 eligible): {state.request_id}")
            return True, "Quota check skipped (not eligible for discount)"
        
        # Update status
        state.status = TransactionStatus.CHECKING_QUOTA
        state.add_event(
            EventType.QUOTA_CHECK_STARTED,
            "Checking daily discount quota availability"
        )
        await event_publisher.save_transaction_state(state)
        
        await event_publisher.publish_event(
            EventType.QUOTA_CHECK_STARTED,
            state.request_id
        )
        
        try:
            r = await self.get_redis()
            quota_key = self._get_quota_key()
            
            # Atomic increment
            new_count = await r.incr(quota_key)
            
            # Set expiry if this is a new key (first discount of the day)
            ttl = await r.ttl(quota_key)
            if ttl == -1:  # No expiry set
                seconds_until_midnight = settings.get_seconds_until_midnight_ist()
                await r.expire(quota_key, seconds_until_midnight)
            
            if new_count <= settings.daily_discount_quota:
                # Quota available
                state.quota_reserved = True
                state.quota_key = quota_key
                state.discount_applied = True
                state.final_price = state.base_price * (1 - state.discount_percentage / 100)
                state.status = TransactionStatus.QUOTA_RESERVED
                state.add_event(
                    EventType.QUOTA_RESERVED,
                    f"Discount quota reserved. Slot {new_count}/{settings.daily_discount_quota}",
                    {"slot": new_count, "max": settings.daily_discount_quota}
                )
                await event_publisher.save_transaction_state(state)
                
                await event_publisher.publish_event(
                    EventType.QUOTA_RESERVED,
                    state.request_id,
                    {"slot": new_count}
                )
                
                logger.info(
                    f"Quota reserved: {state.request_id}",
                    extra={"slot": new_count, "final_price": state.final_price}
                )
                
                return True, f"Quota reserved (slot {new_count}/{settings.daily_discount_quota})"
            else:
                # Flow: 1) Reserve first (INCR committed), 2) Check fails (over limit), 3) Revert (compensation DECR)
                state.quota_reserved = True
                state.quota_key = quota_key
                state.status = TransactionStatus.QUOTA_EXHAUSTED
                state.error_message = "Daily discount quota reached. Please try again tomorrow."
                # Event 1: Reserve first (commit) — so terminal shows "first reserved"
                state.add_event(
                    EventType.QUOTA_RESERVED_OVER_LIMIT,
                    f"Quota slot reserved (over limit: {new_count}/{settings.daily_discount_quota}); check will fail",
                    {"current_count": new_count, "max": settings.daily_discount_quota}
                )
                # Event 2: Check failed — then compensation will revert
                state.add_event(
                    EventType.QUOTA_EXHAUSTED,
                    "Daily discount quota exceeded. Compensation will release reserved slot.",
                    {"current_count": new_count, "max": settings.daily_discount_quota}
                )
                await event_publisher.save_transaction_state(state)
                # Only publish QUOTA_EXHAUSTED so choreography triggers compensation (not booking)
                await event_publisher.publish_event(
                    EventType.QUOTA_EXHAUSTED,
                    state.request_id
                )
                
                logger.warning(
                    f"Quota exceeded: {state.request_id} (compensation will release reserved slot)",
                    extra={"current_count": new_count}
                )
                
                return False, "Daily discount quota reached. Please try again tomorrow."
                
        except Exception as e:
            error_msg = f"Quota check error: {str(e)}"
            state.status = TransactionStatus.FAILED
            state.error_message = error_msg
            await event_publisher.save_transaction_state(state)
            
            logger.error(
                f"Quota check failed: {state.request_id}",
                extra={"error": str(e)}
            )
            
            return False, error_msg
    
    async def release_quota(self, state: TransactionState) -> bool:
        """
        Release a previously reserved quota slot (compensation).
        
        Returns:
            True if quota was released successfully
        """
        logger.info(f"Releasing quota for: {state.request_id}")
        
        try:
            r = await self.get_redis()
            # Use the key stored in state, fallback to today's key if missing
            quota_key = state.quota_key or self._get_quota_key()
            
            # Decrement quota
            new_count = await r.decr(quota_key)
            
            # Ensure count doesn't go below 0
            if new_count < 0:
                await r.set(quota_key, 0)
            
            logger.info(
                f"Quota released: {state.request_id}",
                extra={"new_count": max(0, new_count)}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to release quota: {state.request_id}",
                extra={"error": str(e)}
            )
            return False
    
    async def reset_quota(self) -> bool:
        """Reset quota to 0 (for testing purposes)."""
        try:
            r = await self.get_redis()
            quota_key = self._get_quota_key()
            await r.delete(quota_key)
            logger.info("Quota reset successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reset quota: {str(e)}")
            return False
    
    async def set_quota_count(self, count: int) -> bool:
        """Set quota to specific count (for testing purposes)."""
        try:
            r = await self.get_redis()
            quota_key = self._get_quota_key()
            await r.set(quota_key, count)
            seconds_until_midnight = settings.get_seconds_until_midnight_ist()
            await r.expire(quota_key, seconds_until_midnight)
            logger.info(f"Quota set to {count}")
            return True
        except Exception as e:
            logger.error(f"Failed to set quota: {str(e)}")
            return False


# Global service instance
quota_service = QuotaService()
