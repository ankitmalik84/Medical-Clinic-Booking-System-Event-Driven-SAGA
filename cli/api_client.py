"""
API client for the Medical Clinic Booking System CLI.
"""

import httpx
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import date
import json


class BookingAPIClient:
    """HTTP client for interacting with the booking backend."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check backend health."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
    
    async def get_services(self, gender: str) -> Dict[str, Any]:
        """Get available services for a gender."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/services/{gender}")
            response.raise_for_status()
            return response.json()
    
    async def create_booking(
        self,
        name: str,
        gender: str,
        date_of_birth: date,
        service_ids: list[str]
    ) -> Dict[str, Any]:
        """Submit a booking request."""
        payload = {
            "user": {
                "name": name,
                "gender": gender,
                "date_of_birth": date_of_birth.isoformat()
            },
            "service_ids": service_ids
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/booking",
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def get_booking_result(self, request_id: str) -> Dict[str, Any]:
        """Get the final booking result."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/booking/{request_id}/result")
            response.raise_for_status()
            return response.json()
    
    async def get_booking_status(self, request_id: str) -> Dict[str, Any]:
        """Get current booking status with events."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/booking/{request_id}/status")
            response.raise_for_status()
            return response.json()
    
    async def stream_booking_status(self, request_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time booking status updates via SSE."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            async with client.stream(
                "GET",
                f"{self.base_url}/booking/{request_id}/stream"
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
    
    async def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota status (admin)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/admin/quota")
            response.raise_for_status()
            return response.json()
    
    async def reset_quota(self) -> Dict[str, Any]:
        """Reset quota to 0 (admin)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/admin/quota/reset")
            response.raise_for_status()
            return response.json()
    
    async def set_quota(self, count: int) -> Dict[str, Any]:
        """Set quota to specific value (admin)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/admin/quota/set/{count}")
            response.raise_for_status()
            return response.json()
    
    
    async def toggle_failure_simulation(self, enable: bool) -> Dict[str, Any]:
        """Toggle failure simulation (admin)."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/admin/simulate-failure",
                json={"enable": enable}
            )
            response.raise_for_status()
            return response.json()
