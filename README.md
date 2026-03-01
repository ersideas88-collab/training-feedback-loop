# Training Feedback Loop

High-stress training feedback system. Check in daily → get an auto-generated session plan for tomorrow based on readiness scoring and trend analysis.

## Stack

- **API**: Python + FastAPI
- **Database**: PostgreSQL
- **Hosting**: Railway
- **CI/CD**: GitHub → Railway auto-deploy

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/checkin/{user_id}` | Submit check-in, get tomorrow's plan |
| GET | `/plan/{user_id}/{date}` | Look up a session plan |
| PATCH | `/plan/{user_id}/{date}/status` | Mark plan completed/skipped |
| GET | `/history/{user_id}?days=14` | Recent check-ins + plans |

## Local Dev

```bash
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://localhost/training uvicorn main:app --reload
```

## Deploy

Push to `main` → Railway auto-deploys via Procfile.
