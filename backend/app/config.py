"""
Configuration settings for the Medical Clinic Booking System.
"""

import os
from datetime import datetime
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import pytz


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Redis Configuration
    redis_host: str = Field(
        default="redis-13962.c10.us-east-1-2.ec2.cloud.redislabs.com",
        alias="REDIS_HOST"
    )
    redis_port: int = Field(default=13962, alias="REDIS_PORT")
    redis_username: str = Field(default="default", alias="REDIS_USERNAME")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    
    # Business Rules Configuration
    daily_discount_quota: int = Field(
        default=100,
        alias="DAILY_DISCOUNT_QUOTA",
        description="Maximum number of R1 discounts per day (R2 rule)"
    )
    discount_percentage: float = Field(
        default=12.0,
        alias="DISCOUNT_PERCENTAGE",
        description="Discount percentage for R1 rule"
    )
    high_value_threshold: float = Field(
        default=1000.0,
        alias="HIGH_VALUE_THRESHOLD",
        description="Order value threshold for R1 discount"
    )
    
    # Application Configuration
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")
    transaction_ttl_seconds: int = Field(
        default=3600,
        alias="TRANSACTION_TTL_SECONDS",
        description="TTL for transaction records in Redis (1 hour)"
    )
    
    # Failure Simulation (for testing)
    simulate_booking_failure: bool = Field(
        default=False,
        alias="SIMULATE_BOOKING_FAILURE"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def get_redis_url(self) -> str:
        """Construct Redis URL from components or return provided URL."""
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_username}:{self.redis_password}@{self.redis_host}:{self.redis_port}"
    
    def get_timezone(self) -> pytz.timezone:
        """Get timezone object."""
        return pytz.timezone(self.timezone)
    
    def get_today_ist(self) -> str:
        """Get today's date in IST as string (YYYY-MM-DD)."""
        tz = self.get_timezone()
        return datetime.now(tz).strftime("%Y-%m-%d")
    
    def get_current_time_ist(self) -> datetime:
        """Get current datetime in IST."""
        tz = self.get_timezone()
        return datetime.now(tz)
    
    def get_seconds_until_midnight_ist(self) -> int:
        """Calculate seconds until midnight IST for Redis key expiration."""
        tz = self.get_timezone()
        now = datetime.now(tz)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= midnight:
            from datetime import timedelta
            midnight += timedelta(days=1)
        return int((midnight - now).total_seconds())


# Global settings instance
settings = Settings()
