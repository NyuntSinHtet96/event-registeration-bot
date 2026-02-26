import uuid

from fastapi.testclient import TestClient

from api.main import app


# Purpose: Provide an API client with startup hooks executed.
def _client() -> TestClient:
    return TestClient(app)


# Purpose: Generate a unique Telegram user identifier for tests.
def _unique_telegram_user_id() -> int:
    return int(uuid.uuid4().int % 1_000_000_000)


# Purpose: Generate a unique email and phone pair for tests.
def _unique_contact() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:10]
    email = f"qa.{suffix}@example.com"
    phone = f"+65{int(suffix, 16) % 100_000_000:08d}"
    return email, phone


# Purpose: Fetch one open event id to use in registration tests.
def _first_event_id(client: TestClient) -> str:
    response = client.get("/events")
    assert response.status_code == 200, response.text
    events = response.json()
    assert isinstance(events, list) and events, "Expected at least one seeded event"
    return events[0]["id"]


# Purpose: Verify events endpoint returns at least one event.
def test_events_endpoint_returns_seeded_events() -> None:
    with _client() as client:
        response = client.get("/events")
        assert response.status_code == 200, response.text
        events = response.json()
        assert isinstance(events, list)
        assert len(events) >= 1


# Purpose: Verify creating registration and QR generation flow works.
def test_registration_create_and_qr_generation() -> None:
    with _client() as client:
        event_id = _first_event_id(client)
        email, phone = _unique_contact()

        registration = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": _unique_telegram_user_id(),
                "full_name": "QA Create User",
                "email": email,
                "phone": phone,
            },
        )
        assert registration.status_code == 200, registration.text
        registration_payload = registration.json()
        assert registration_payload["status"] == "created"
        registration_id = registration_payload["registration_id"]

        qr_response = client.post(f"/registrations/{registration_id}/qr")
        assert qr_response.status_code == 200, qr_response.text
        qr_payload = qr_response.json()
        assert qr_payload["registration_id"] == registration_id
        assert qr_payload["qr_token"]

        # Check token remains stable for repeated calls.
        qr_again = client.post(f"/registrations/{registration_id}/qr")
        assert qr_again.status_code == 200, qr_again.text
        assert qr_again.json()["qr_token"] == qr_payload["qr_token"]


# Purpose: Verify same Telegram user can update their own registration.
def test_registration_update_same_user() -> None:
    with _client() as client:
        event_id = _first_event_id(client)
        user_id = _unique_telegram_user_id()
        email, phone = _unique_contact()

        created = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": user_id,
                "full_name": "QA Original Name",
                "email": email,
                "phone": phone,
            },
        )
        assert created.status_code == 200, created.text
        created_payload = created.json()

        updated = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": user_id,
                "full_name": "QA Updated Name",
                "email": email,
                "phone": phone,
            },
        )
        assert updated.status_code == 200, updated.text
        updated_payload = updated.json()
        assert updated_payload["status"] == "updated"
        assert updated_payload["registration_id"] == created_payload["registration_id"]

        current = client.get(f"/registrations/{created_payload['registration_id']}")
        assert current.status_code == 200, current.text
        assert current.json()["full_name"] == "QA Updated Name"


# Purpose: Verify duplicate email or phone is blocked for other users in same event.
def test_registration_blocks_duplicate_email_or_phone_per_event() -> None:
    with _client() as client:
        event_id = _first_event_id(client)
        email, phone = _unique_contact()

        base = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": _unique_telegram_user_id(),
                "full_name": "QA Base User",
                "email": email,
                "phone": phone,
            },
        )
        assert base.status_code == 200, base.text

        _, different_phone = _unique_contact()
        email_conflict = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": _unique_telegram_user_id(),
                "full_name": "QA Email Conflict",
                "email": email,
                "phone": different_phone,
            },
        )
        assert email_conflict.status_code == 409, email_conflict.text
        assert email_conflict.json().get("detail") == "Email already registered for this event"

        different_email, _ = _unique_contact()
        phone_conflict = client.post(
            "/registrations",
            json={
                "event_id": event_id,
                "telegram_user_id": _unique_telegram_user_id(),
                "full_name": "QA Phone Conflict",
                "email": different_email,
                "phone": phone,
            },
        )
        assert phone_conflict.status_code == 409, phone_conflict.text
        assert phone_conflict.json().get("detail") == "Phone already registered for this event"
