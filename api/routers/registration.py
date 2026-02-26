from datetime import datetime, timezone
import re
import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/registrations", tags=["registrations"])

KNOWN_EVENT_IDS = {"evt_001", "evt_002"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]{7,20}$")


class RegistrationUpsertIn(BaseModel):
    event_id: str = Field(min_length=1)
    telegram_user_id: int
    full_name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str

    @field_validator("email")
    @classmethod
    # Purpose: Validate and normalize email input for registrations.
    def validate_email(cls, value: str) -> str:
        email = value.strip()
        if not EMAIL_PATTERN.fullmatch(email):
            raise ValueError("Invalid email format")
        return email

    @field_validator("phone")
    @classmethod
    # Purpose: Validate and normalize phone input for registrations.
    def validate_phone(cls, value: str) -> str:
        phone = value.strip()
        if not PHONE_PATTERN.fullmatch(phone):
            raise ValueError("Invalid phone format")
        return phone


class RegistrationUpsertOut(BaseModel):
    registration_id: str
    status: str


class RegistrationOut(BaseModel):
    registration_id: str
    event_id: str
    telegram_user_id: int
    full_name: str
    email: str
    phone: str
    created_at: datetime
    updated_at: datetime

class RegistrationQRResponse(BaseModel):
    registration_id: str
    qr_token: str


registrations_by_id: dict[str, dict] = {}
registration_key_to_id: dict[tuple[str, int], str] = {}


# Purpose: Return the current UTC timestamp for record metadata.
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Purpose: Generate a unique registration identifier.
def _new_registration_id() -> str:
    return f"reg_{secrets.token_hex(6)}"


@router.post("", response_model=RegistrationUpsertOut)
# Purpose: Create or update a registration for an event and Telegram user.
def upsert_registration(payload: RegistrationUpsertIn) -> RegistrationUpsertOut:
    if payload.event_id not in KNOWN_EVENT_IDS:
        raise HTTPException(status_code=400, detail="Unknown event_id")

    key = (payload.event_id, payload.telegram_user_id)
    existing_id = registration_key_to_id.get(key)
    now = _utcnow()

    if existing_id:
        row = registrations_by_id[existing_id]
        row["full_name"] = payload.full_name.strip()
        row["email"] = payload.email
        row["phone"] = payload.phone
        row["updated_at"] = now
        return RegistrationUpsertOut(registration_id=existing_id, status="updated")

    registration_id = _new_registration_id()
    registrations_by_id[registration_id] = {
        "registration_id": registration_id,
        "event_id": payload.event_id,
        "telegram_user_id": payload.telegram_user_id,
        "full_name": payload.full_name.strip(),
        "email": payload.email,
        "phone": payload.phone,
        "created_at": now,
        "updated_at": now,
        "qr_token": None,
    }
    registration_key_to_id[key] = registration_id
    return RegistrationUpsertOut(registration_id=registration_id, status="created")


@router.get("/{registration_id}", response_model=RegistrationOut)
# Purpose: Return one registration by its identifier.
def get_registration(registration_id: str) -> RegistrationOut:
    row = registrations_by_id.get(registration_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found")
    return RegistrationOut(**row)


@router.post("/{registration_id}/qr", response_model=RegistrationQRResponse)
# Purpose: Generate and return a stable QR token for a registration.
def generate_qr(registration_id: str) -> RegistrationQRResponse:
    row = registrations_by_id.get(registration_id)
    if not row:
        raise HTTPException(status_code=404, detail="Registration not found")

    if not row["qr_token"]:
        row["qr_token"] = f"qr_{registration_id}_{secrets.token_urlsafe(16)}"
        row["updated_at"] = _utcnow()

    return RegistrationQRResponse(
        registration_id=registration_id,
        qr_token=row["qr_token"],
    )
