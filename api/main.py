from datetime import datetime, timezone

from fastapi import FastAPI
from sqlalchemy import select

from api.db import Base, SessionLocal, engine
from api.models import Event
from api.routers.checkin import router as checkin_router
from api.routers.events import router as events_router
from api.routers.registration import router as registration_router

app = FastAPI(title="Event Bot API")


# Purpose: Seed baseline events when the events table is empty.
def seed_events() -> None:
    db = SessionLocal()
    try:
        has_any_event = db.scalar(select(Event.id).limit(1))
        if has_any_event is not None:
            return

        db.add_all(
            [
                Event(
                    id="evt_001",
                    title="NUS-ISS Career Sharing",
                    start_time=datetime(2026, 3, 5, 19, 0, tzinfo=timezone.utc),
                    location="LT19",
                    capacity=100,
                    status="OPEN",
                ),
                Event(
                    id="evt_002",
                    title="Python FastAPI Workshop",
                    start_time=datetime(2026, 3, 10, 14, 0, tzinfo=timezone.utc),
                    location="Online",
                    capacity=200,
                    status="OPEN",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


# Purpose: Initialize schema and seed startup data.
@app.on_event("startup")
# Purpose: Run startup hooks for DB schema creation and seed data.
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_events()


app.include_router(events_router)
app.include_router(registration_router)
app.include_router(checkin_router)
