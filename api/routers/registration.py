from datetime import datetime, timezone
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import Event, Registration

router = APIRouter(prefix="/registrations", tags=["registrations"])

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9()\-\s]{7,20}$")


# Purpose: Normalize phone text into a canonical comparable value.
def _normalize_phone(phone: str) -> str:
    cleaned = phone.strip()
    has_plus = cleaned.startswith("+")
    digits = "".join(char for char in cleaned if char.isdigit())
    return f"+{digits}" if has_plus else digits


# Purpose: Convert DB unique constraint failures into user-facing messages.
def _constraint_error_detail(exc: IntegrityError) -> str:
    message = str(exc.orig)
    if "uq_event_telegram_user" in message:
        return "Telegram user already registered for this event"
    if "uq_event_email" in message:
        return "Email already registered for this event"
    if "uq_event_phone" in message:
        return "Phone already registered for this event"
    return "Registration data conflicts with an existing attendee"


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
        email = value.strip().lower()
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
        normalized = _normalize_phone(phone)
        digit_count = len(normalized.lstrip("+"))
        if digit_count < 7 or digit_count > 20:
            raise ValueError("Invalid phone format")
        return normalized


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


# Purpose: Return the current UTC timestamp for record metadata.
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Purpose: Generate a unique registration identifier.
def _new_registration_id() -> str:
    return f"reg_{secrets.token_hex(6)}"


@router.post("", response_model=RegistrationUpsertOut)
# Purpose: Create or update a registration for an event and Telegram user.
def upsert_registration(
    payload: RegistrationUpsertIn,
    db: Session = Depends(get_db),
) -> RegistrationUpsertOut:
    event = db.get(Event, payload.event_id)
    if event is None:
        raise HTTPException(status_code=400, detail="Unknown event_id")

    existing_by_user = db.scalar(
        select(Registration).where(
            Registration.event_id == payload.event_id,
            Registration.telegram_user_id == payload.telegram_user_id,
        )
    )

    email_match = db.scalar(
        select(Registration).where(
            Registration.event_id == payload.event_id,
            Registration.email == payload.email,
        )
    )
    phone_match = db.scalar(
        select(Registration).where(
            Registration.event_id == payload.event_id,
            Registration.phone == payload.phone,
        )
    )

    if existing_by_user is not None:
        if email_match is not None and email_match.registration_id != existing_by_user.registration_id:
            raise HTTPException(status_code=409, detail="Email already registered for this event")
        if phone_match is not None and phone_match.registration_id != existing_by_user.registration_id:
            raise HTTPException(status_code=409, detail="Phone already registered for this event")
    else:
        if email_match is not None:
            raise HTTPException(status_code=409, detail="Email already registered for this event")
        if phone_match is not None:
            raise HTTPException(status_code=409, detail="Phone already registered for this event")

    now = _utcnow()

    if existing_by_user is not None:
        existing_by_user.full_name = payload.full_name.strip()
        existing_by_user.email = payload.email
        existing_by_user.phone = payload.phone
        existing_by_user.updated_at = now
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=_constraint_error_detail(exc)) from exc
        return RegistrationUpsertOut(registration_id=existing_by_user.registration_id, status="updated")

    registration_id = _new_registration_id()
    while db.get(Registration, registration_id) is not None:
        registration_id = _new_registration_id()

    row = Registration(
        registration_id=registration_id,
        event_id=payload.event_id,
        telegram_user_id=payload.telegram_user_id,
        full_name=payload.full_name.strip(),
        email=payload.email,
        phone=payload.phone,
        created_at=now,
        updated_at=now,
        qr_token=None,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=_constraint_error_detail(exc)) from exc

    return RegistrationUpsertOut(registration_id=registration_id, status="created")


@router.get("/{registration_id}", response_model=RegistrationOut)
# Purpose: Return one registration by its identifier.
def get_registration(registration_id: str, db: Session = Depends(get_db)) -> RegistrationOut:
    row = db.get(Registration, registration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Registration not found")

    return RegistrationOut(
        registration_id=row.registration_id,
        event_id=row.event_id,
        telegram_user_id=row.telegram_user_id,
        full_name=row.full_name,
        email=row.email,
        phone=row.phone,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/{registration_id}/qr", response_model=RegistrationQRResponse)
# Purpose: Generate and return a stable QR token for a registration.
def generate_qr(registration_id: str, db: Session = Depends(get_db)) -> RegistrationQRResponse:
    row = db.get(Registration, registration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Registration not found")

    if not row.qr_token:
        row.qr_token = f"qr_{registration_id}_{secrets.token_urlsafe(16)}"
        row.updated_at = _utcnow()
        db.commit()

    return RegistrationQRResponse(registration_id=row.registration_id, qr_token=row.qr_token)
