from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import Event

router = APIRouter(prefix="/events", tags=["events"])


class EventOut(BaseModel):
    id: str
    title: str
    start_time: datetime
    location: str
    capacity: int
    status: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[EventOut])
# Purpose: Return events filtered by status for bot and clients.
def list_events(status: str = "OPEN", db: Session = Depends(get_db)) -> list[EventOut]:
    stmt = select(Event)
    if status:
        stmt = stmt.where(Event.status == status)
    stmt = stmt.order_by(Event.start_time.asc())

    rows = db.scalars(stmt).all()
    return [EventOut.model_validate(row) for row in rows]
