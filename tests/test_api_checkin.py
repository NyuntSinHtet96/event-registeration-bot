import uuid

from fastapi.testclient import TestClient

from api.main import app


# Purpose: Provide an API test client that runs startup hooks.
def _client() -> TestClient:
    return TestClient(app)


# Purpose: Generate a unique contact pair for registration setup.
def _unique_contact() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:10]
    email = f"checkin.{suffix}@example.com"
    phone = f"+65{int(suffix, 16) % 100_000_000:08d}"
    return email, phone


# Purpose: Return seeded event ids used for check-in tests.
def _event_ids(client: TestClient) -> list[str]:
    response = client.get("/events")
    assert response.status_code == 200, response.text
    events = response.json()
    assert isinstance(events, list) and events, "Expected at least one event"
    return [item["id"] for item in events]


# Purpose: Create a registration and return its id and qr token for scanning.
def _create_registration_with_qr(client: TestClient, event_id: str) -> tuple[str, str]:
    email, phone = _unique_contact()
    registration = client.post(
        "/registrations",
        json={
            "event_id": event_id,
            "telegram_user_id": int(uuid.uuid4().int % 1_000_000_000),
            "full_name": "Check In User",
            "email": email,
            "phone": phone,
        },
    )
    assert registration.status_code == 200, registration.text
    registration_id = registration.json()["registration_id"]

    qr_response = client.post(f"/registrations/{registration_id}/qr")
    assert qr_response.status_code == 200, qr_response.text
    qr_token = qr_response.json()["qr_token"]

    return registration_id, qr_token


# Purpose: Verify check-in GUI page is served for on-site staff usage.
def test_checkin_gui_page_loads() -> None:
    with _client() as client:
        response = client.get("/checkins/gui")
        assert response.status_code == 200, response.text
        assert "Guest Check-in Console" in response.text
        assert "/checkins/scan" in response.text


# Purpose: Verify first scan checks in and duplicate scan is idempotent.
def test_checkin_scan_success_and_duplicate() -> None:
    with _client() as client:
        event_id = _event_ids(client)[0]
        registration_id, qr_token = _create_registration_with_qr(client, event_id)

        first_scan = client.post(
            "/checkins/scan",
            json={"event_id": event_id, "qr_token": qr_token, "method": "web_scanner"},
        )
        assert first_scan.status_code == 200, first_scan.text
        first_payload = first_scan.json()
        assert first_payload["status"] == "checked_in"
        assert first_payload["registration_id"] == registration_id

        second_scan = client.post(
            "/checkins/scan",
            json={"event_id": event_id, "qr_token": qr_token, "method": "web_scanner"},
        )
        assert second_scan.status_code == 200, second_scan.text
        second_payload = second_scan.json()
        assert second_payload["status"] == "already_checked_in"
        assert second_payload["registration_id"] == registration_id


# Purpose: Verify invalid or wrong-event QR scans return clear errors.
def test_checkin_scan_rejects_invalid_or_wrong_event_qr() -> None:
    with _client() as client:
        event_ids = _event_ids(client)
        event_id = event_ids[0]
        _, qr_token = _create_registration_with_qr(client, event_id)

        invalid_scan = client.post(
            "/checkins/scan",
            json={"event_id": event_id, "qr_token": "invalid_qr_token"},
        )
        assert invalid_scan.status_code == 404, invalid_scan.text
        assert invalid_scan.json().get("detail") == "Invalid QR token"

        if len(event_ids) > 1:
            wrong_event_scan = client.post(
                "/checkins/scan",
                json={"event_id": event_ids[1], "qr_token": qr_token},
            )
            assert wrong_event_scan.status_code == 400, wrong_event_scan.text
            assert wrong_event_scan.json().get("detail") == "QR token does not belong to this event"
