# High-Stress Training Feedback Loop — Architecture

## Why This Is Different From the ChatGPT Approach

| | ChatGPT (Firestore) | This (Railway + SQL) |
|---|---|---|
| **Trigger** | Firestore `onCreate` listener | Direct API call |
| **Database** | NoSQL document store | PostgreSQL with relations + constraints |
| **Logic location** | Cloud Function (event-driven) | FastAPI endpoint (request-driven) |
| **Plan generation** | Placeholder with no intelligence | Readiness scoring + trend analysis |
| **Feedback loop** | None — just copies a date | Queries last 7 days of check-ins |
| **Atomicity** | Two separate writes that can fail independently | Single database transaction |
| **Deployment** | Firebase deploy | `git push` → Railway auto-deploys |

## How It Works

```
Client: POST /checkin/{user_id}
  ├─ Save check-in (subjective + biometric data)
  ├─ Compute readiness score (server-side, weighted formula)
  ├─ Query last 7 days of scores (trend detection)
  ├─ Map score + trend → intensity level
  ├─ Generate tomorrow's session plan
  └─ Return both in one response (one DB transaction)
```

The client gets back the check-in confirmation AND tomorrow's plan in a single response.
No polling. No waiting for a background function. No eventual consistency.

## The Feedback Loop

```
Day 1: Check in → score 72 → trend: stable → plan: HIGH strength
Day 2: Check in → score 45 → trend: declining → plan: LOW mobility
Day 3: Check in → score 38 → trend: declining → plan: DELOAD recovery
Day 4: Check in → score 55 → trend: improving → plan: MODERATE maintenance
```

The system looks backward before planning forward.

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Database tables — run this first or let SQLAlchemy create them |
| `models.py` | SQLAlchemy ORM models + Pydantic request/response schemas |
| `readiness.py` | Scoring engine, trend detection, plan generation logic |
| `main.py` | FastAPI app with all endpoints |
| `requirements.txt` | Python dependencies |
| `Procfile` | Railway deployment config |

## Railway Setup

1. Create a new project on Railway
2. Add a PostgreSQL service
3. Connect your GitHub repo
4. Set `DATABASE_URL` env var (Railway does this automatically for the Postgres addon)
5. Push to GitHub — Railway auto-deploys

## API Endpoints

- `POST /checkin/{user_id}` — submit check-in, get tomorrow's plan back
- `GET /plan/{user_id}/{date}` — look up any plan by date
- `PATCH /plan/{user_id}/{date}/status` — mark plan as completed/skipped
- `GET /history/{user_id}?days=14` — get recent check-ins + plans for dashboard

## Extending This

Where to add things as the system matures:

- **AI-powered plans**: Replace `determine_intensity()` in `readiness.py` with an LLM call
- **Exercise prescription**: Expand `plan_data` JSONB field with specific exercises
- **Overtraining detection**: Add a weekly aggregate query in the history endpoint
- **User baselines**: Store personal HRV/RHR baselines and score relative to them
- **Notifications**: Add a simple cron job on Railway that checks for missing check-ins
