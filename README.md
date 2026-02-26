# Event Bot (Telegram + FastAPI + MySQL)

A Telegram registration bot backed by FastAPI and MySQL.

Current scope (user flow):
- View available events from API
- Register via Telegram conversation (event -> name -> email -> phone -> confirm)
- Store/update registration in MySQL
- Generate and send QR code to the user

## Stack

- Telegram bot: `python-telegram-bot`
- Backend API: `FastAPI`
- Database: `MySQL 8.4` (Docker)
- ORM: `SQLAlchemy`

## Project Structure

- `bot/` Telegram bot app
- `api/` FastAPI backend + DB models
- `docker-compose.yml` local MySQL service
- `requirements.txt` Python dependencies

## Prerequisites

- Python 3.11+
- Docker runtime (`Docker Desktop` or `colima`)

If you use Colima (macOS):

```bash
colima start
```

## Environment

Create `.env` in the project root:

```env
BOT_TOKEN=your-telegram-bot-token
API_BASE_URL=http://localhost:8000
DATABASE_URL=mysql+pymysql://event_user:event_pass@127.0.0.1:3306/event_bot
```

## Run Locally

1) Start MySQL

```bash
docker compose up -d mysql
```

2) Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

3) Run API (Terminal 1)

```bash
python3 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

4) Run bot (Terminal 2)

```bash
python3 -m bot.main
```

## Code Quality Tests

Run linting:

```bash
ruff check .
```

Run test suite:

```bash
pytest
```

Run test coverage:

```bash
pytest --cov=api --cov=bot --cov-report=term-missing
```

## API Endpoints

- `GET /events` - list events (default `status=OPEN`)
- `POST /registrations` - create/update registration
- `GET /registrations/{registration_id}` - get one registration
- `POST /registrations/{registration_id}/qr` - create/get QR token

Swagger:
- `http://127.0.0.1:8000/docs`

## Registration Rules

Per event:
- One email can belong to only one registration
- One phone can belong to only one registration

Update behavior:
- Same `telegram_user_id` + same event can update their own registration
- Different `telegram_user_id` cannot reuse existing email/phone in the same event

## Workflow Diagram

```mermaid
flowchart TD
    U[Telegram User] --> S[/start]
    S --> M[Bot Menu]
    M -->|View Events| EV[GET /events]
    EV --> API1[FastAPI]
    API1 --> DB1[(MySQL events)]
    DB1 --> API1
    API1 --> EV
    EV --> U

    M -->|Register| R0[Pick event]
    R0 --> R1[Enter name]
    R1 --> R2[Enter email]
    R2 --> R3[Enter phone]
    R3 --> R4[Confirm]
    R4 --> API2[POST /registrations]
    API2 --> DB2[(MySQL registrations)]
    DB2 --> API2
    API2 --> API3[POST /registrations/{id}/qr]
    API3 --> DB3[(MySQL qr_token)]
    DB3 --> API3
    API3 --> BOTQR[Bot sends styled QR image]
    BOTQR --> U
```

## CI/CD Pipeline

GitHub Actions workflow file:
- `.github/workflows/ci-cd.yml`

What it does:
- CI on pull requests and pushes to `main`
- Starts MySQL service in workflow
- Installs dependencies
- Runs `ruff check .`
- Runs `pytest` with coverage report output

Optional CD deploy:
- Runs only on push to `main`
- Uses SSH and executes a remote deploy command
- Auto-skips if deploy secrets are not configured

Required deploy secrets:
- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_COMMAND`

## Troubleshooting

- Port `8000` already in use:
  - stop old process, then restart `uvicorn`
- DB auth errors (`Access denied`):
  - ensure `.env` `DATABASE_URL` matches `docker-compose.yml` credentials
- Bot not responding:
  - verify `BOT_TOKEN` in `.env`
  - verify API is running at `API_BASE_URL`

## Security Note

- Never commit `.env`.
- If a bot token was exposed, rotate it in BotFather and update `.env`.
