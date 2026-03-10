-- ============================================================
-- HIGH-STRESS TRAINING FEEDBACK LOOP
-- Database Schema (PostgreSQL on Railway)
-- ============================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(100) UNIQUE NOT NULL,  -- your app's user identifier
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Check-ins: subjective + biometric readiness snapshot
CREATE TABLE IF NOT EXISTS check_ins (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        DATE NOT NULL,

    -- Subjective (1-10 scale)
    stress_level    SMALLINT CHECK (stress_level BETWEEN 1 AND 10),
    sleep_quality   SMALLINT CHECK (sleep_quality BETWEEN 1 AND 10),
    soreness        SMALLINT CHECK (soreness BETWEEN 1 AND 10),
    energy          SMALLINT CHECK (energy BETWEEN 1 AND 10),
    motivation      SMALLINT CHECK (motivation BETWEEN 1 AND 10),

    -- Biometric
    hrv_ms          NUMERIC(6,2),   -- heart rate variability in ms
    resting_hr_bpm  NUMERIC(5,2),   -- resting heart rate
    sleep_hours     NUMERIC(4,2),   -- total sleep duration

    -- Derived
    readiness_score NUMERIC(5,2),   -- computed server-side, not client-submitted

    created_at  TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, date)  -- one check-in per user per day
);

-- Session plans: auto-generated from check-in data
CREATE TABLE IF NOT EXISTS session_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    check_in_id     UUID REFERENCES check_ins(id),  -- the check-in that triggered this plan

    -- Plan content
    intensity       VARCHAR(20) NOT NULL CHECK (intensity IN ('deload', 'low', 'moderate', 'high', 'peak')),
    focus           VARCHAR(50),        -- e.g. "recovery", "strength", "conditioning"
    notes           TEXT,               -- human-readable reasoning
    plan_data       JSONB DEFAULT '{}', -- flexible slot for exercises, durations, etc.

    -- Metadata
    status          VARCHAR(20) DEFAULT 'generated' CHECK (status IN ('generated', 'accepted', 'modified', 'completed', 'skipped')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, date)  -- one plan per user per day
);

-- Indexes for the queries you'll actually run
CREATE INDEX idx_check_ins_user_date ON check_ins(user_id, date DESC);
CREATE INDEX idx_session_plans_user_date ON session_plans(user_id, date DESC);
CREATE INDEX idx_session_plans_status ON session_plans(status);

-- Phrase check-ins: one-question-at-a-time language recall flow
CREATE TABLE IF NOT EXISTS phrase_check_ins (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date_of_entry       DATE NOT NULL,

    q1_phrase_recalled  VARCHAR(8) NOT NULL,      -- yes | no
    q2_recall_mode      VARCHAR(20),              -- spontaneous | deliberate
    q3_timing           VARCHAR(10),              -- before | during | after
    q4_effect           VARCHAR(20),              -- helpful | neutral | distracting
    q5_situation_text   TEXT,
    q6_attempted_recall VARCHAR(8),               -- yes | no
    q7_additional_text  TEXT,
    timestamp           TIMESTAMPTZ,

    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),

    UNIQUE(user_id, date_of_entry)
);

CREATE INDEX idx_phrase_check_ins_user_date ON phrase_check_ins(user_id, date_of_entry DESC);
