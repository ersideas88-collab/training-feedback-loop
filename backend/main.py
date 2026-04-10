"""
FastAPI app — check-in endpoint with automatic session plan generation.

POST /checkin → saves check-in → computes readiness → generates tomorrow's plan
All in one transaction. No triggers, no cloud functions, no event-driven mystery.
"""

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from models import (
    Base, UserRow, CheckInRow, SessionPlanRow, PhraseCheckInRow,
    CheckInCreate, CheckInWithPlanResponse,
    CheckInResponse, SessionPlanResponse, PhraseCheckInCreate,
)
from readiness import generate_plan, compute_readiness_score


# ── Database setup ─────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/training")

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Pressure Conditioned Language System",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins_env = os.getenv("CORS_ORIGINS", "*").strip()
if cors_origins_env == "*":
    cors_origins = ["*"]
else:
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db():
    async with SessionLocal() as session:
        yield session


# ── Routes ─────────────────────────────────────────────────

@app.post("/checkin/{user_id}", response_model=CheckInWithPlanResponse)
async def create_checkin(
    user_id: UUID,
    payload: CheckInCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    The entire pipeline in one endpoint:
    1. Validate user exists
    2. Save today's check-in
    3. Compute readiness score
    4. Generate tomorrow's session plan
    5. Return both
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # ── 1. Verify user ──
    user = await db.get(UserRow, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # ── 2. Prevent duplicate check-in ──
    existing = await db.execute(
        select(CheckInRow).where(
            CheckInRow.user_id == user_id,
            CheckInRow.date == today,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Check-in already exists for {today}")

    # ── 3. Save check-in ──
    check_in = CheckInRow(
        user_id=user_id,
        date=today,
        stress_level=payload.stress_level,
        sleep_quality=payload.sleep_quality,
        soreness=payload.soreness,
        energy=payload.energy,
        motivation=payload.motivation,
        hrv_ms=payload.hrv_ms,
        resting_hr_bpm=payload.resting_hr_bpm,
        sleep_hours=payload.sleep_hours,
    )

    # ── 4. Compute readiness (server-side, not client) ──
    check_in.readiness_score = compute_readiness_score(check_in)
    db.add(check_in)
    await db.flush()  # get the ID before using it

    # ── 5. Generate tomorrow's plan ──
    result = await generate_plan(db, check_in, tomorrow)

    plan = SessionPlanRow(
        user_id=user_id,
        date=tomorrow,
        check_in_id=check_in.id,
        intensity=result.intensity.value,
        focus=result.focus,
        notes=result.notes,
        plan_data=result.plan_data,
        status="generated",
    )
    db.add(plan)

    # ── 6. Commit everything atomically ──
    await db.commit()
    await db.refresh(check_in)
    await db.refresh(plan)

    return CheckInWithPlanResponse(
        check_in=CheckInResponse.model_validate(check_in),
        session_plan=SessionPlanResponse.model_validate(plan),
    )


@app.get("/plan/{user_id}/{plan_date}", response_model=SessionPlanResponse)
async def get_plan(
    user_id: UUID,
    plan_date: date,
    db: AsyncSession = Depends(get_db),
):
    """Look up a session plan by user + date."""
    result = await db.execute(
        select(SessionPlanRow).where(
            SessionPlanRow.user_id == user_id,
            SessionPlanRow.date == plan_date,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, f"No plan found for {plan_date}")
    return SessionPlanResponse.model_validate(plan)


@app.patch("/plan/{user_id}/{plan_date}/status")
async def update_plan_status(
    user_id: UUID,
    plan_date: date,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Let the client mark a plan as completed/skipped.
    This closes the feedback loop — you can query completion
    rates to refine future plans.
    """
    valid = {"accepted", "modified", "completed", "skipped"}
    if status not in valid:
        raise HTTPException(400, f"Status must be one of: {valid}")

    result = await db.execute(
        select(SessionPlanRow).where(
            SessionPlanRow.user_id == user_id,
            SessionPlanRow.date == plan_date,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")

    plan.status = status
    await db.commit()
    return {"updated": True, "status": status}


@app.get("/history/{user_id}")
async def get_history(
    user_id: UUID,
    days: int = 14,
    db: AsyncSession = Depends(get_db),
):
    """
    Return recent check-ins + plans for the dashboard.
    This is the data your frontend needs to render trends.
    """
    cutoff = date.today() - timedelta(days=days)

    check_ins = await db.execute(
        select(CheckInRow)
        .where(CheckInRow.user_id == user_id, CheckInRow.date >= cutoff)
        .order_by(CheckInRow.date.desc())
    )
    plans = await db.execute(
        select(SessionPlanRow)
        .where(SessionPlanRow.user_id == user_id, SessionPlanRow.date >= cutoff)
        .order_by(SessionPlanRow.date.desc())
    )

    return {
        "check_ins": [
            {
                "date": str(c.date),
                "readiness_score": float(c.readiness_score) if c.readiness_score else None,
                "stress": c.stress_level,
                "energy": c.energy,
                "soreness": c.soreness,
            }
            for c in check_ins.scalars().all()
        ],
        "plans": [
            {
                "date": str(p.date),
                "intensity": p.intensity,
                "focus": p.focus,
                "status": p.status,
            }
            for p in plans.scalars().all()
        ],
    }


async def _save_phrase_checkin(payload: PhraseCheckInCreate, db: AsyncSession):
    # Create/find user by participant external ID
    result = await db.execute(
        select(UserRow).where(UserRow.external_id == payload.participant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = UserRow(external_id=payload.participant_id)
        db.add(user)
        await db.flush()

    # Upsert one row per date per user
    existing = await db.execute(
        select(PhraseCheckInRow).where(
            PhraseCheckInRow.user_id == user.id,
            PhraseCheckInRow.date_of_entry == payload.date_of_entry,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        row = PhraseCheckInRow(
            user_id=user.id,
            date_of_entry=payload.date_of_entry,
            q1_phrase_recalled=payload.q1_phrase_recalled,
            q2_recall_mode=payload.q2_recall_mode,
            q3_timing=payload.q3_timing,
            q4_effect=payload.q4_effect,
            q5_situation_text=payload.q5_situation_text,
            q6_attempted_recall=payload.q6_attempted_recall,
            q7_additional_text=payload.q7_additional_text,
            timestamp=payload.timestamp,
            client_source=payload.client_source,
        )
        db.add(row)
    else:
        row.q1_phrase_recalled = payload.q1_phrase_recalled
        row.q2_recall_mode = payload.q2_recall_mode
        row.q3_timing = payload.q3_timing
        row.q4_effect = payload.q4_effect
        row.q5_situation_text = payload.q5_situation_text
        row.q6_attempted_recall = payload.q6_attempted_recall
        row.q7_additional_text = payload.q7_additional_text
        row.timestamp = payload.timestamp
        row.client_source = payload.client_source

    await db.commit()
    await db.refresh(row)
    return {
        "saved": True,
        "id": str(row.id),
        "user_id": str(user.id),
        "participant_id": user.external_id,
        "date_of_entry": str(row.date_of_entry),
        "client_source": row.client_source,
    }


@app.post("/phrase-checkin")
async def create_phrase_checkin_legacy(
    payload: PhraseCheckInCreate,
    db: AsyncSession = Depends(get_db),
):
    return await _save_phrase_checkin(payload, db)


@app.post("/api/v1/phrase-checkin")
async def create_phrase_checkin_v1(
    payload: PhraseCheckInCreate,
    db: AsyncSession = Depends(get_db),
):
    return await _save_phrase_checkin(payload, db)


@app.get("/api/v1/metrics/overview")
async def metrics_overview(
    days: int = 30,
    participant_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if days < 1:
        raise HTTPException(400, "days must be >= 1")
    if days > 365:
        raise HTTPException(400, "days must be <= 365")

    cutoff = date.today() - timedelta(days=days - 1)

    query = (
        select(PhraseCheckInRow, UserRow.external_id)
        .join(UserRow, UserRow.id == PhraseCheckInRow.user_id)
        .where(PhraseCheckInRow.date_of_entry >= cutoff)
    )
    if participant_id:
        query = query.where(UserRow.external_id == participant_id)

    result = await db.execute(query.order_by(PhraseCheckInRow.date_of_entry.asc()))
    rows = result.all()

    total_entries = len(rows)
    recalled_yes = sum(1 for row, _ in rows if row.q1_phrase_recalled == "yes")
    recalled_no = sum(1 for row, _ in rows if row.q1_phrase_recalled == "no")

    source_counts = {"web": 0, "app": 0}
    daily = {}
    for row, _ in rows:
        src = row.client_source if row.client_source in source_counts else "web"
        source_counts[src] += 1
        key = str(row.date_of_entry)
        if key not in daily:
            daily[key] = {"date": key, "entries": 0, "recalled_yes": 0, "recalled_no": 0}
        daily[key]["entries"] += 1
        if row.q1_phrase_recalled == "yes":
            daily[key]["recalled_yes"] += 1
        elif row.q1_phrase_recalled == "no":
            daily[key]["recalled_no"] += 1

    trend = [daily[k] for k in sorted(daily.keys())]
    recall_rate = (recalled_yes / total_entries) if total_entries else 0.0

    return {
        "range_days": days,
        "from_date": str(cutoff),
        "to_date": str(date.today()),
        "participant_filter": participant_id,
        "totals": {
            "entries": total_entries,
            "recalled_yes": recalled_yes,
            "recalled_no": recalled_no,
            "recall_rate": round(recall_rate, 4),
        },
        "source_counts": source_counts,
        "trend": trend,
    }
