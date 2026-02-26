from fastapi import FastAPI
from api.routers.events import router as events_router
from api.routers.registration import router as registration_router

app = FastAPI()
app.include_router(events_router)
app.include_router(registration_router)