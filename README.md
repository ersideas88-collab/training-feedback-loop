# Training Feedback Loop

High-stress training feedback system. Check in daily → get an auto-generated session plan for tomorrow based on readiness scoring and trend analysis.

## Project Structure

```
├── frontend/          ← Static mockup (deploys to Netlify)
│   └── index.html
├── backend/           ← FastAPI service (deploys to Railway)
│   ├── main.py
│   ├── models.py
│   ├── readiness.py
│   ├── schema.sql
│   ├── requirements.txt
│   └── Procfile
├── netlify.toml       ← Netlify config (serves frontend/ as static)
└── ARCHITECTURE.md
```

## Stack

- **API**: Python + FastAPI
- **Database**: PostgreSQL
- **API Hosting**: Railway (backend/)
- **Mockup Hosting**: Netlify (frontend/)
- **CI/CD**: GitHub → auto-deploy both

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/checkin/{user_id}` | Submit check-in, get tomorrow's plan |
| GET | `/plan/{user_id}/{date}` | Look up a session plan |
| PATCH | `/plan/{user_id}/{date}/status` | Mark plan completed/skipped |
| GET | `/history/{user_id}?days=14` | Recent check-ins + plans |

## Deploy

**Netlify (frontend mockup):** Connect this repo → Netlify auto-reads `netlify.toml` and serves `frontend/index.html`. No build step needed.

**Railway (API):** Create a Railway project → set root directory to `backend/` → add PostgreSQL addon → auto-deploys via Procfile.

## Local Dev

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://localhost/training uvicorn main:app --reload
```
