"""
FastAPI app — check-in endpoint with automatic session plan generation.

POST /checkin → saves check-in → computes readiness → generates tomorrow's plan
All in one transaction. No triggers, no cloud functions, no event-driven mystery.
"""

import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from models import (
    Base, UserRow, CheckInRow, SessionPlanRow,
    CheckInCreate, CheckInWithPlanResponse,
    CheckInResponse, SessionPlanResponse,
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
