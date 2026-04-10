"""
Database models — SQLAlchemy + Pydantic schemas
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column, Date, ForeignKey, Index, Numeric, SmallInteger, String, Text,
    UniqueConstraint, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


# ── SQLAlchemy Models ──────────────────────────────────────

class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(Date, server_default=func.now())

    check_ins = relationship("CheckInRow", back_populates="user")
    session_plans = relationship("SessionPlanRow", back_populates="user")


class CheckInRow(Base):
    __tablename__ = "check_ins"
    __table_args__ = (
        UniqueConstraint("user_id", "date"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)

    # Subjective
    stress_level = Column(SmallInteger)
    sleep_quality = Column(SmallInteger)
    soreness = Column(SmallInteger)
    energy = Column(SmallInteger)
    motivation = Column(SmallInteger)

    # Biometric
    hrv_ms = Column(Numeric(6, 2))
    resting_hr_bpm = Column(Numeric(5, 2))
    sleep_hours = Column(Numeric(4, 2))

    # Derived
    readiness_score = Column(Numeric(5, 2))

    created_at = Column(Date, server_default=func.now())

    user = relationship("UserRow", back_populates="check_ins")
    session_plan = relationship("SessionPlanRow", back_populates="check_in", uselist=False)


class SessionPlanRow(Base):
    __tablename__ = "session_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "date"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    check_in_id = Column(PG_UUID(as_uuid=True), ForeignKey("check_ins.id"))

    intensity = Column(String(20), nullable=False)
    focus = Column(String(50))
    notes = Column(Text)
    plan_data = Column(JSONB, default={})

    status = Column(String(20), default="generated")
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(Date, server_default=func.now(), onupdate=func.now())

    user = relationship("UserRow", back_populates="session_plans")
    check_in = relationship("CheckInRow", back_populates="session_plan")


# ── Pydantic Schemas (API layer) ──────────────────────────

class Intensity(str, Enum):
    DELOAD = "deload"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PEAK = "peak"


class CheckInCreate(BaseModel):
    """What the client sends when checking in."""
    stress_level: int = Field(ge=1, le=10)
    sleep_quality: int = Field(ge=1, le=10)
    soreness: int = Field(ge=1, le=10)
    energy: int = Field(ge=1, le=10)
    motivation: int = Field(ge=1, le=10)

    hrv_ms: Optional[float] = None
    resting_hr_bpm: Optional[float] = None
    sleep_hours: Optional[float] = None


class CheckInResponse(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    readiness_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionPlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    intensity: Intensity
    focus: Optional[str]
    notes: Optional[str]
    plan_data: dict
    status: str

    model_config = {"from_attributes": True}


class CheckInWithPlanResponse(BaseModel):
    check_in: CheckInResponse
    session_plan: SessionPlanResponse
