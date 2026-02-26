from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/events", tags=["events"])

class EventOut(BaseModel):
    id:str
    title:str
    start_time:datetime
    location: str
    capacity: int
    status: str

@router.get("",response_model=list[EventOut])
# Purpose: Return events filtered by status for bot and clients.
def list_events(status:str = "OPEN"):
    events = [
         EventOut(
            id="evt_001",
            title="NUS-ISS Career Sharing",
            start_time=datetime(2026, 3, 5, 19, 0),
            location="LT19",
            capacity=100,
            status="OPEN",
        ),
        EventOut(
            id="evt_002",
            title="Python FastAPI Workshop",
            start_time=datetime(2026, 3, 10, 14, 0),
            location="Online",
            capacity=200,
            status="OPEN",
        ),
    ]
    return [e for e in events if e.status==status]
