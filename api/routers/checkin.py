from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.db import get_db
from api.models import CheckIn, Event, Registration, utcnow

router = APIRouter(prefix="/checkins", tags=["checkins"])

CHECKIN_GUI_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Event Check-in Console</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />
    <script src="https://unpkg.com/html5-qrcode" defer></script>
    <style>
      :root {
        --bg-1: #0b1822;
        --bg-2: #122638;
        --panel: rgba(255, 255, 255, 0.08);
        --panel-border: rgba(255, 255, 255, 0.14);
        --text: #e9f4ff;
        --muted: #a8c2d9;
        --ok: #1ec98f;
        --warn: #f5b84a;
        --danger: #ff6f6f;
        --accent: #5ec9ff;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Space Grotesk", sans-serif;
        color: var(--text);
        background: radial-gradient(1000px 600px at 10% -10%, #1b3952 0%, transparent 60%),
          radial-gradient(1200px 600px at 100% 0%, #163a47 0%, transparent 60%),
          linear-gradient(160deg, var(--bg-1), var(--bg-2));
      }

      .wrap {
        max-width: 1080px;
        margin: 0 auto;
        padding: 24px 16px 36px;
      }

      .title {
        margin: 0;
        font-size: clamp(1.5rem, 3.4vw, 2.2rem);
        letter-spacing: 0.02em;
      }

      .subtitle {
        margin: 8px 0 20px;
        color: var(--muted);
      }

      .grid {
        display: grid;
        gap: 16px;
      }

      @media (min-width: 900px) {
        .grid {
          grid-template-columns: 1.1fr 0.9fr;
        }
      }

      .card {
        border: 1px solid var(--panel-border);
        background: var(--panel);
        backdrop-filter: blur(6px);
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.25);
      }

      .card h2 {
        margin: 0 0 12px;
        font-size: 1.15rem;
      }

      .controls {
        display: grid;
        gap: 10px;
      }

      label {
        font-size: 0.86rem;
        color: var(--muted);
      }

      select,
      input,
      button {
        width: 100%;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.22);
        background: rgba(5, 10, 15, 0.45);
        color: var(--text);
        font: inherit;
        padding: 10px 12px;
      }

      input {
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.92rem;
      }

      button {
        cursor: pointer;
        font-weight: 600;
        background: linear-gradient(135deg, #2a97cc, #34c7cf);
        border: none;
      }

      button.secondary {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
      }

      .button-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }

      #reader {
        width: 100%;
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.16);
      }

      .status {
        margin-top: 14px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        background: rgba(0, 0, 0, 0.22);
        padding: 12px;
        display: none;
      }

      .status.show {
        display: block;
      }

      .status.ok {
        border-color: color-mix(in srgb, var(--ok), white 25%);
      }

      .status.warn {
        border-color: color-mix(in srgb, var(--warn), white 25%);
      }

      .status.error {
        border-color: color-mix(in srgb, var(--danger), white 25%);
      }

      .mono {
        margin-top: 8px;
        font-family: "IBM Plex Mono", monospace;
        font-size: 0.82rem;
        color: #d3ecff;
        word-break: break-all;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1 class="title">Guest Check-in Console</h1>
      <p class="subtitle">Scan attendee QR tickets on arrival, or paste token manually.</p>

      <div class="grid">
        <section class="card">
          <h2>QR Scanner</h2>
          <div class="controls">
            <label for="eventSelect">Event</label>
            <select id="eventSelect"></select>

            <div class="button-row">
              <button id="startScanBtn" type="button">Start Camera</button>
              <button id="stopScanBtn" type="button" class="secondary">Stop Camera</button>
            </div>

            <div id="reader"></div>
          </div>
        </section>

        <section class="card">
          <h2>Manual Token Check</h2>
          <div class="controls">
            <label for="manualToken">QR Token</label>
            <input id="manualToken" placeholder="Paste qr_token here" />
            <button id="manualSubmitBtn" type="button">Submit Check-in</button>
          </div>

          <div id="statusBox" class="status" aria-live="polite">
            <strong id="statusTitle"></strong>
            <div id="statusMessage"></div>
            <div id="statusMeta" class="mono"></div>
          </div>
        </section>
      </div>
    </div>

    <script>
      const eventSelect = document.getElementById("eventSelect");
      const startScanBtn = document.getElementById("startScanBtn");
      const stopScanBtn = document.getElementById("stopScanBtn");
      const manualToken = document.getElementById("manualToken");
      const manualSubmitBtn = document.getElementById("manualSubmitBtn");
      const statusBox = document.getElementById("statusBox");
      const statusTitle = document.getElementById("statusTitle");
      const statusMessage = document.getElementById("statusMessage");
      const statusMeta = document.getElementById("statusMeta");

      let scanner = null;
      let scanLock = false;
      let lastToken = "";
      let lastScanAt = 0;
      const AUTO_STOP_ON_SUCCESS = true;

      function showStatus(kind, title, message, meta = "") {
        statusBox.className = "status show " + kind;
        statusTitle.textContent = title;
        statusMessage.textContent = message;
        statusMeta.textContent = meta;
      }

      async function loadEvents() {
        const response = await fetch("/events?status=OPEN");
        if (!response.ok) {
          throw new Error("Failed to load events");
        }

        const events = await response.json();
        eventSelect.innerHTML = "";

        if (!Array.isArray(events) || events.length === 0) {
          const option = document.createElement("option");
          option.value = "";
          option.textContent = "No open events";
          eventSelect.appendChild(option);
          return;
        }

        events.forEach((event) => {
          const option = document.createElement("option");
          option.value = event.id;
          option.textContent = `${event.title} (${event.id})`;
          eventSelect.appendChild(option);
        });
      }

      async function submitCheckin(token) {
        const eventId = eventSelect.value;
        if (!eventId) {
          showStatus("error", "Event required", "Please select an event first.");
          return;
        }

        if (!token || !token.trim()) {
          showStatus("error", "Token required", "Please scan or paste a token.");
          return;
        }

        if (scanLock) {
          return;
        }

        scanLock = true;
        try {
          const response = await fetch("/checkins/scan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              event_id: eventId,
              qr_token: token.trim(),
              method: "web_scanner",
            }),
          });

          const data = await response.json();
          if (!response.ok) {
            showStatus("error", "Check-in failed", data.detail || "Unexpected error", token);
            return;
          }

          if (data.status === "checked_in") {
            showStatus(
              "ok",
              "Checked in",
              `${data.full_name} has been checked in successfully.`,
              `Registration: ${data.registration_id}`
            );

            if (AUTO_STOP_ON_SUCCESS) {
              try {
                await stopScanner();
              } catch (error) {
                showStatus(
                  "warn",
                  "Checked in",
                  `${data.full_name} was checked in.`
                  `Registration: ${data.registration_id}`
                );
              }
            }
          } else {
            showStatus(
              "warn",
              "Already checked in",
              `${data.full_name} was already checked in.`,
              `Registration: ${data.registration_id}`
            );
          }
        } catch (error) {
          showStatus("error", "Network error", "Could not reach API.");
        } finally {
          scanLock = false;
        }
      }

      async function startScanner() {
        if (scanner) {
          return;
        }

        scanner = new Html5Qrcode("reader");
        await scanner.start(
          { facingMode: "environment" },
          { fps: 10, qrbox: { width: 240, height: 240 } },
          async (decodedText) => {
            const now = Date.now();
            if (decodedText === lastToken && now - lastScanAt < 2000) {
              return;
            }
            lastToken = decodedText;
            lastScanAt = now;
            await submitCheckin(decodedText);
          },
          () => {}
        );
      }

      async function stopScanner() {
        if (!scanner) {
          return;
        }
        await scanner.stop();
        await scanner.clear();
        scanner = null;
      }

      startScanBtn.addEventListener("click", async () => {
        try {
          await startScanner();
          showStatus("ok", "Camera started", "Scan a guest QR ticket to check in.");
        } catch (error) {
          showStatus("error", "Camera unavailable", "Check browser camera permission.");
        }
      });

      stopScanBtn.addEventListener("click", async () => {
        await stopScanner();
        showStatus("warn", "Camera stopped", "Scanner is paused.");
      });

      manualSubmitBtn.addEventListener("click", async () => {
        await submitCheckin(manualToken.value);
      });

      window.addEventListener("beforeunload", () => {
        if (scanner) {
          scanner.stop().catch(() => {});
        }
      });

      loadEvents().catch(() => {
        showStatus("error", "Load failed", "Could not load events from API.");
      });
    </script>
  </body>
</html>
"""


class CheckInScanIn(BaseModel):
    event_id: str = Field(min_length=1)
    qr_token: str = Field(min_length=1)
    method: str = Field(default="qr_scan", min_length=1, max_length=40)


class CheckInScanOut(BaseModel):
    status: str
    message: str
    registration_id: str
    event_id: str
    full_name: str
    checked_in_at: datetime


# Purpose: Serve a browser-based QR scanner UI for on-site check-in staff.
@router.get("/gui", response_class=HTMLResponse)
def checkin_gui() -> HTMLResponse:
    return HTMLResponse(content=CHECKIN_GUI_HTML)


# Purpose: Validate QR token and mark attendee as checked in once.
@router.post("/scan", response_model=CheckInScanOut)
def scan_check_in(payload: CheckInScanIn, db: Session = Depends(get_db)) -> CheckInScanOut:
    event_id = payload.event_id.strip()
    qr_token = payload.qr_token.strip()
    method = payload.method.strip() or "qr_scan"

    if not event_id:
        raise HTTPException(status_code=400, detail="event_id is required")
    if not qr_token:
        raise HTTPException(status_code=400, detail="qr_token is required")

    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=400, detail="Unknown event_id")

    registration = db.scalar(select(Registration).where(Registration.qr_token == qr_token))
    if registration is None:
        raise HTTPException(status_code=404, detail="Invalid QR token")

    if registration.event_id != event_id:
        raise HTTPException(status_code=400, detail="QR token does not belong to this event")

    existing = db.scalar(
        select(CheckIn).where(CheckIn.registration_id == registration.registration_id)
    )
    if existing is not None:
        return CheckInScanOut(
            status="already_checked_in",
            message="Guest already checked in",
            registration_id=registration.registration_id,
            event_id=registration.event_id,
            full_name=registration.full_name,
            checked_in_at=existing.checked_in_at,
        )

    check_in = CheckIn(
        registration_id=registration.registration_id,
        event_id=registration.event_id,
        method=method,
        checked_in_at=utcnow(),
    )
    db.add(check_in)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        duplicate = db.scalar(
            select(CheckIn).where(CheckIn.registration_id == registration.registration_id)
        )
        if duplicate is not None:
            return CheckInScanOut(
                status="already_checked_in",
                message="Guest already checked in",
                registration_id=registration.registration_id,
                event_id=registration.event_id,
                full_name=registration.full_name,
                checked_in_at=duplicate.checked_in_at,
            )
        raise HTTPException(status_code=409, detail="Could not create check-in record") from exc

    db.refresh(check_in)
    return CheckInScanOut(
        status="checked_in",
        message="Check-in successful",
        registration_id=registration.registration_id,
        event_id=registration.event_id,
        full_name=registration.full_name,
        checked_in_at=check_in.checked_in_at,
    )
