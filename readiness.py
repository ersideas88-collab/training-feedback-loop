"""
Readiness engine — the core feedback loop logic.

Takes today's check-in + recent history → produces a readiness score
and tomorrow's session plan parameters.

This is where all your training intelligence lives.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CheckInRow, SessionPlanRow, Intensity


@dataclass
class ReadinessResult:
    score: float            # 0-100
    intensity: Intensity
    focus: str
    notes: str
    plan_data: dict


# ── Weights (tune these over time) ─────────────────────────

SUBJECTIVE_WEIGHTS = {
    "stress_level":  -0.20,  # high stress = bad → negative weight
    "sleep_quality":  0.25,
    "soreness":      -0.15,  # high soreness = bad
    "energy":         0.25,
    "motivation":     0.15,
}

# How many recent days to factor into trend analysis
LOOKBACK_DAYS = 7


# ── Core scoring ───────────────────────────────────────────

def compute_readiness_score(check_in: CheckInRow) -> float:
    """
    Weighted composite of subjective + biometric inputs.
    Returns 0-100 scale.
    """
    # Subjective component (each metric is 1-10)
    raw = 0.0
    for field, weight in SUBJECTIVE_WEIGHTS.items():
        val = getattr(check_in, field, None)
        if val is not None:
            if weight < 0:
                # Invert: high stress (10) → low contribution
                raw += abs(weight) * (11 - val)
            else:
                raw += weight * val

    # Normalize subjective to 0-100
    subjective_score = (raw / 10) * 100

    # Biometric adjustments
    bio_modifier = 0.0

    if check_in.hrv_ms is not None:
        hrv = float(check_in.hrv_ms)
        if hrv >= 60:
            bio_modifier += 5      # good HRV
        elif hrv < 30:
            bio_modifier -= 10     # poor HRV, flag recovery

    if check_in.resting_hr_bpm is not None:
        rhr = float(check_in.resting_hr_bpm)
        if rhr > 80:
            bio_modifier -= 5      # elevated RHR suggests fatigue
        elif rhr < 55:
            bio_modifier += 3      # well-recovered

    if check_in.sleep_hours is not None:
        sleep = float(check_in.sleep_hours)
        if sleep < 6:
            bio_modifier -= 10
        elif sleep >= 8:
            bio_modifier += 5

    return max(0, min(100, subjective_score + bio_modifier))


# ── Trend analysis ─────────────────────────────────────────

async def get_recent_scores(
    db: AsyncSession,
    user_id,
    before_date: date,
    days: int = LOOKBACK_DAYS,
) -> list[float]:
    """Pull the last N readiness scores for trend detection."""
    cutoff = before_date - timedelta(days=days)
    result = await db.execute(
        select(CheckInRow.readiness_score)
        .where(
            CheckInRow.user_id == user_id,
            CheckInRow.date >= cutoff,
            CheckInRow.date < before_date,
            CheckInRow.readiness_score.isnot(None),
        )
        .order_by(CheckInRow.date.desc())
    )
    return [float(row[0]) for row in result.all()]


def detect_trend(scores: list[float]) -> str:
    """Simple trend: are they trending up, down, or flat?"""
    if len(scores) < 3:
        return "insufficient_data"

    recent_avg = sum(scores[:3]) / 3
    older_avg = sum(scores[3:]) / max(len(scores[3:]), 1)
    diff = recent_avg - older_avg

    if diff > 8:
        return "improving"
    elif diff < -8:
        return "declining"
    return "stable"


# ── Plan generation ────────────────────────────────────────

def determine_intensity(score: float, trend: str) -> Intensity:
    """Map readiness score + trend → training intensity."""
    if score < 30:
        return Intensity.DELOAD
    elif score < 50:
        return Intensity.LOW if trend != "improving" else Intensity.MODERATE
    elif score < 70:
        return Intensity.MODERATE
    elif score < 85:
        return Intensity.HIGH if trend != "declining" else Intensity.MODERATE
    else:
        return Intensity.PEAK if trend == "improving" else Intensity.HIGH


FOCUS_MAP = {
    Intensity.DELOAD:   "recovery",
    Intensity.LOW:      "mobility + light conditioning",
    Intensity.MODERATE: "strength maintenance",
    Intensity.HIGH:     "strength + conditioning",
    Intensity.PEAK:     "max effort / testing",
}


async def generate_plan(
    db: AsyncSession,
    check_in: CheckInRow,
    target_date: date,
) -> ReadinessResult:
    """
    The main feedback loop:
    1. Score today's check-in
    2. Pull recent history
    3. Detect trend
    4. Determine tomorrow's intensity + focus
    """
    score = compute_readiness_score(check_in)
    recent = await get_recent_scores(db, check_in.user_id, check_in.date)
    trend = detect_trend(recent)
    intensity = determine_intensity(score, trend)
    focus = FOCUS_MAP[intensity]

    notes_parts = [
        f"Readiness: {score:.0f}/100",
        f"Trend: {trend} (last {len(recent)} days)",
    ]
    if float(check_in.soreness or 0) >= 7:
        notes_parts.append("High soreness flagged — avoid heavy eccentric loading")
    if check_in.sleep_hours and float(check_in.sleep_hours) < 6:
        notes_parts.append("Sleep deficit — prioritize recovery")
    if trend == "declining":
        notes_parts.append("Declining trend — consider scheduled deload if this continues")

    return ReadinessResult(
        score=score,
        intensity=intensity,
        focus=focus,
        notes=" | ".join(notes_parts),
        plan_data={
            "readiness_score": score,
            "trend": trend,
            "recent_scores": recent[:5],
            "subjective": {
                "stress": check_in.stress_level,
                "sleep_quality": check_in.sleep_quality,
                "soreness": check_in.soreness,
                "energy": check_in.energy,
                "motivation": check_in.motivation,
            },
            "biometric": {
                "hrv_ms": float(check_in.hrv_ms) if check_in.hrv_ms else None,
                "resting_hr_bpm": float(check_in.resting_hr_bpm) if check_in.resting_hr_bpm else None,
                "sleep_hours": float(check_in.sleep_hours) if check_in.sleep_hours else None,
            },
        },
    )
