from dataclasses import dataclass
import httpx
from bot.config import API_BASE_URL

@dataclass
class Event:
    id: str
    title: str
    start_time: str
    location: str
    capacity: str
    status: str

@dataclass
class RegistrationUpsertResult:
    registration_id: str
    status: str  # created | updated

@dataclass
class RegistrationQRResult:
    registration_id: str
    qr_token: str


class ApiClient:
    # Purpose: Initialize API client configuration for backend calls.
    def __init__(self,base_url: str = API_BASE_URL,timeout:float =10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        
    # Purpose: Fetch event list from API and map rows to Event models.
    async def list_events(self, status:str = "OPEN") -> list[Event]:
        url = f"{self.base_url}/events"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params={"status":status})
        response.raise_for_status()
        data = response.json()
        return [Event(**row) for row in data]
    
    # Purpose: Create or update a user registration through the API.
    async def upsert_registration(
        self,
        *,
        event_id: str,
        telegram_user_id: int,
        full_name: str,
        email: str,
        phone: str,
    ) -> RegistrationUpsertResult:
        url = f"{self.base_url}/registrations"
        payload = {
            "event_id": event_id,
            "telegram_user_id": telegram_user_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
        return RegistrationUpsertResult(**response.json())

    # Purpose: Request QR token generation for a registration.
    async def generate_registration_qr(self, registration_id: str) -> RegistrationQRResult:
        url = f"{self.base_url}/registrations/{registration_id}/qr"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url)
        response.raise_for_status()
        return RegistrationQRResult(**response.json())

        
