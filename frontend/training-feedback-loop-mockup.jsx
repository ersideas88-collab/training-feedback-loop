import { useState, useMemo } from "react";

const INTENSITY_CONFIG = {
  deload:   { color: "#6366f1", bg: "#eef2ff", label: "DELOAD",   emoji: "🧘" },
  low:      { color: "#06b6d4", bg: "#ecfeff", label: "LOW",      emoji: "🚶" },
  moderate: { color: "#f59e0b", bg: "#fffbeb", label: "MODERATE", emoji: "🏋️" },
  high:     { color: "#ef4444", bg: "#fef2f2", label: "HIGH",     emoji: "🔥" },
  peak:     { color: "#dc2626", bg: "#fee2e2", label: "PEAK",     emoji: "⚡" },
};

const MOCK_HISTORY = [
  { date: "Feb 21", score: 82, intensity: "high", status: "completed" },
  { date: "Feb 22", score: 74, intensity: "high", status: "completed" },
  { date: "Feb 23", score: 58, intensity: "moderate", status: "completed" },
  { date: "Feb 24", score: 42, intensity: "low", status: "skipped" },
  { date: "Feb 25", score: 35, intensity: "deload", status: "completed" },
  { date: "Feb 26", score: 51, intensity: "moderate", status: "completed" },
  { date: "Feb 27", score: 63, intensity: "moderate", status: "completed" },
];

function computeReadiness(data) {
  const weights = { stress: -0.20, sleepQuality: 0.25, soreness: -0.15, energy: 0.25, motivation: 0.15 };
  let raw = 0;
  for (const [key, w] of Object.entries(weights)) {
    const val = data[key];
    raw += w < 0 ? Math.abs(w) * (11 - val) : w * val;
  }
  let score = (raw / 10) * 100;
  if (data.hrv) { score += data.hrv >= 60 ? 5 : data.hrv < 30 ? -10 : 0; }
  if (data.rhr) { score += data.rhr > 80 ? -5 : data.rhr < 55 ? 3 : 0; }
  if (data.sleepHours) { score += data.sleepHours < 6 ? -10 : data.sleepHours >= 8 ? 5 : 0; }
  return Math.max(0, Math.min(100, score));
}

function getIntensity(score, trend) {
  if (score < 30) return "deload";
  if (score < 50) return trend !== "improving" ? "low" : "moderate";
  if (score < 70) return "moderate";
  if (score < 85) return trend !== "declining" ? "high" : "moderate";
  return trend === "improving" ? "peak" : "high";
}

function getTrend(history) {
  if (history.length < 3) return "insufficient";
  const recent = history.slice(-3).reduce((a, b) => a + b.score, 0) / 3;
  const older = history.slice(0, -3).reduce((a, b) => a + b.score, 0) / Math.max(history.length - 3, 1);
  const diff = recent - older;
  return diff > 8 ? "improving" : diff < -8 ? "declining" : "stable";
}

const FOCUS_MAP = {
  deload: "Recovery — stretching, breathing, gentle movement",
  low: "Mobility + light conditioning",
  moderate: "Strength maintenance — controlled loads",
  high: "Strength + conditioning — push it",
  peak: "Max effort / testing day",
};

function Slider({ label, value, onChange, inverted }) {
  const pct = ((value - 1) / 9) * 100;
  const barColor = inverted
    ? `hsl(${120 - pct * 1.2}, 70%, 50%)`
    : `hsl(${pct * 1.2}, 70%, 50%)`;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4, fontSize: 13, fontWeight: 600, color: "#374151" }}>
        <span>{label}</span>
        <span style={{ color: barColor, fontWeight: 700, fontSize: 15 }}>{value}</span>
      </div>
      <input
        type="range" min={1} max={10} value={value} onChange={e => onChange(+e.target.value)}
        style={{ width: "100%", accentColor: barColor, height: 6, cursor: "pointer" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#9ca3af", marginTop: 2 }}>
        <span>{inverted ? "Low" : "Poor"}</span>
        <span>{inverted ? "Extreme" : "Excellent"}</span>
      </div>
    </div>
  );
}

function BiometricInput({ label, unit, value, onChange, placeholder }) {
  return (
    <div style={{ flex: 1, minWidth: 120 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: "#374151", display: "block", marginBottom: 4 }}>{label}</label>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <input
          type="number" value={value} onChange={e => onChange(e.target.value ? +e.target.value : "")}
          placeholder={placeholder}
          style={{ width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid #d1d5db", fontSize: 14, outline: "none", background: "#f9fafb" }}
        />
        <span style={{ fontSize: 11, color: "#9ca3af", whiteSpace: "nowrap" }}>{unit}</span>
      </div>
    </div>
  );
}

function ScoreRing({ score, size = 140 }) {
  const r = (size - 16) / 2;
  const c = Math.PI * 2 * r;
  const offset = c - (score / 100) * c;
  const color = score >= 70 ? "#22c55e" : score >= 45 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f3f4f6" strokeWidth={10} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={10}
          strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: 36, fontWeight: 800, color }}>{Math.round(score)}</span>
        <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 500 }}>/ 100</span>
      </div>
    </div>
  );
}

function MiniBar({ history }) {
  const max = 100;
  return (
    <div style={{ display: "flex", alignItems: "end", gap: 3, height: 60 }}>
      {history.map((d, i) => {
        const h = Math.max(4, (d.score / max) * 56);
        const color = d.score >= 70 ? "#22c55e" : d.score >= 45 ? "#f59e0b" : "#ef4444";
        return (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <div style={{ width: 24, height: h, background: color, borderRadius: 4, opacity: d.status === "skipped" ? 0.4 : 1, transition: "height 0.3s" }} />
            <span style={{ fontSize: 9, color: "#9ca3af" }}>{d.date.split(" ")[1]}</span>
          </div>
        );
      })}
    </div>
  );
}

function PlanCard({ intensity, focus, notes, date }) {
  const cfg = INTENSITY_CONFIG[intensity];
  return (
    <div style={{ background: cfg.bg, border: `2px solid ${cfg.color}`, borderRadius: 16, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "#6b7280", textTransform: "uppercase", letterSpacing: 1 }}>Tomorrow's Session</div>
          <div style={{ fontSize: 13, color: "#9ca3af", marginTop: 2 }}>{date}</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, background: cfg.color, color: "#fff", padding: "6px 16px", borderRadius: 20, fontWeight: 700, fontSize: 14 }}>
          <span>{cfg.emoji}</span>
          <span>{cfg.label}</span>
        </div>
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, color: "#111827", marginBottom: 6 }}>{focus}</div>
      {notes && <div style={{ fontSize: 13, color: "#6b7280", lineHeight: 1.5, background: "#fff", borderRadius: 10, padding: 12, marginTop: 8 }}>{notes}</div>}
    </div>
  );
}

function HistoryRow({ day }) {
  const cfg = INTENSITY_CONFIG[day.intensity];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid #f3f4f6" }}>
      <div style={{ width: 48, fontSize: 12, fontWeight: 600, color: "#6b7280" }}>{day.date}</div>
      <div style={{ flex: 1 }}>
        <div style={{ height: 6, background: "#f3f4f6", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${day.score}%`, background: cfg.color, borderRadius: 3, transition: "width 0.5s" }} />
        </div>
      </div>
      <div style={{ width: 32, fontSize: 13, fontWeight: 700, color: cfg.color, textAlign: "right" }}>{day.score}</div>
      <div style={{ fontSize: 10, fontWeight: 700, color: cfg.color, background: cfg.bg, padding: "3px 8px", borderRadius: 10, width: 72, textAlign: "center" }}>{cfg.label}</div>
      <div style={{ fontSize: 18, width: 24, textAlign: "center", opacity: day.status === "skipped" ? 0.4 : 1 }}>
        {day.status === "completed" ? "✓" : day.status === "skipped" ? "—" : "·"}
      </div>
    </div>
  );
}

export default function TrainingFeedbackLoop() {
  const [view, setView] = useState("checkin");
  const [submitted, setSubmitted] = useState(false);

  const [stress, setStress] = useState(5);
  const [sleepQuality, setSleepQuality] = useState(6);
  const [soreness, setSoreness] = useState(4);
  const [energy, setEnergy] = useState(6);
  const [motivation, setMotivation] = useState(7);
  const [hrv, setHrv] = useState(52);
  const [rhr, setRhr] = useState(62);
  const [sleepHours, setSleepHours] = useState(7.2);

  const score = useMemo(() => computeReadiness({ stress, sleepQuality, soreness, energy, motivation, hrv, rhr, sleepHours }), [stress, sleepQuality, soreness, energy, motivation, hrv, rhr, sleepHours]);
  const trend = getTrend(MOCK_HISTORY);
  const intensity = getIntensity(score, trend);

  const noteParts = [`Readiness: ${Math.round(score)}/100`, `Trend: ${trend}`];
  if (soreness >= 7) noteParts.push("High soreness — avoid heavy eccentric loading");
  if (sleepHours < 6) noteParts.push("Sleep deficit — prioritize recovery");

  const handleSubmit = () => setSubmitted(true);
  const handleReset = () => { setSubmitted(false); };

  const navStyle = (active) => ({
    padding: "10px 20px", borderRadius: 10, border: "none", cursor: "pointer", fontWeight: 600, fontSize: 13,
    background: active ? "#111827" : "transparent", color: active ? "#fff" : "#6b7280",
    transition: "all 0.2s",
  });

  return (
    <div style={{ maxWidth: 520, margin: "0 auto", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", color: "#111827", padding: 16 }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -0.5 }}>Training Loop</div>
        <div style={{ fontSize: 13, color: "#9ca3af", marginTop: 4 }}>High-Stress Feedback System</div>
      </div>

      {/* Nav */}
      <div style={{ display: "flex", gap: 4, background: "#f3f4f6", borderRadius: 12, padding: 4, marginBottom: 24 }}>
        <button style={navStyle(view === "checkin")} onClick={() => { setView("checkin"); setSubmitted(false); }}>Check In</button>
        <button style={navStyle(view === "plan")} onClick={() => setView("plan")}>Today's Plan</button>
        <button style={navStyle(view === "history")} onClick={() => setView("history")}>History</button>
      </div>

      {/* CHECK-IN VIEW */}
      {view === "checkin" && !submitted && (
        <div>
          <div style={{ background: "#fff", borderRadius: 16, padding: 24, border: "1px solid #e5e7eb", marginBottom: 16 }}>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, color: "#374151" }}>How are you feeling?</div>
            <Slider label="Stress Level" value={stress} onChange={setStress} inverted />
            <Slider label="Sleep Quality" value={sleepQuality} onChange={setSleepQuality} />
            <Slider label="Soreness" value={soreness} onChange={setSoreness} inverted />
            <Slider label="Energy" value={energy} onChange={setEnergy} />
            <Slider label="Motivation" value={motivation} onChange={setMotivation} />
          </div>

          <div style={{ background: "#fff", borderRadius: 16, padding: 24, border: "1px solid #e5e7eb", marginBottom: 20 }}>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 16, color: "#374151" }}>Biometrics <span style={{ fontWeight: 400, color: "#9ca3af", fontSize: 12 }}>(optional)</span></div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <BiometricInput label="HRV" unit="ms" value={hrv} onChange={setHrv} placeholder="e.g. 55" />
              <BiometricInput label="Resting HR" unit="bpm" value={rhr} onChange={setRhr} placeholder="e.g. 60" />
              <BiometricInput label="Sleep" unit="hrs" value={sleepHours} onChange={setSleepHours} placeholder="e.g. 7.5" />
            </div>
          </div>

          {/* Live readiness preview */}
          <div style={{ background: "#f9fafb", borderRadius: 16, padding: 20, textAlign: "center", marginBottom: 20, border: "1px solid #e5e7eb" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#9ca3af", textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>Live Readiness</div>
            <div style={{ display: "flex", justifyContent: "center" }}>
              <ScoreRing score={score} size={100} />
            </div>
          </div>

          <button onClick={handleSubmit} style={{
            width: "100%", padding: 16, borderRadius: 12, border: "none", background: "#111827", color: "#fff",
            fontSize: 16, fontWeight: 700, cursor: "pointer", transition: "transform 0.1s",
          }}>
            Submit Check-In →
          </button>
        </div>
      )}

      {/* POST-SUBMIT VIEW */}
      {view === "checkin" && submitted && (
        <div>
          <div style={{ textAlign: "center", marginBottom: 24 }}>
            <div style={{ fontSize: 48, marginBottom: 8 }}>✓</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>Check-in recorded</div>
            <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>Feb 28, 2026</div>
          </div>

          <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
            <ScoreRing score={score} />
          </div>

          <PlanCard intensity={intensity} focus={FOCUS_MAP[intensity]} notes={noteParts.join(" · ")} date="March 1, 2026" />

          <div style={{ textAlign: "center", marginTop: 20 }}>
            <button onClick={handleReset} style={{
              padding: "10px 24px", borderRadius: 10, border: "1px solid #d1d5db", background: "#fff",
              color: "#374151", fontSize: 13, fontWeight: 600, cursor: "pointer",
            }}>
              ← Edit Check-In
            </button>
          </div>
        </div>
      )}

      {/* PLAN VIEW */}
      {view === "plan" && (
        <div>
          <PlanCard intensity={intensity} focus={FOCUS_MAP[intensity]} notes={noteParts.join(" · ")} date="Today — Feb 28" />

          <div style={{ background: "#fff", borderRadius: 16, padding: 20, border: "1px solid #e5e7eb", marginTop: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#374151", marginBottom: 12 }}>Session Status</div>
            <div style={{ display: "flex", gap: 8 }}>
              {["accepted", "completed", "skipped"].map(s => (
                <button key={s} style={{
                  flex: 1, padding: "10px 0", borderRadius: 10, border: "1px solid #e5e7eb", background: "#f9fafb",
                  fontSize: 12, fontWeight: 600, color: "#374151", cursor: "pointer", textTransform: "capitalize",
                }}>
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div style={{ background: "#fff", borderRadius: 16, padding: 20, border: "1px solid #e5e7eb", marginTop: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#374151", marginBottom: 8 }}>How this was generated</div>
            <div style={{ fontSize: 12, color: "#6b7280", lineHeight: 1.6 }}>
              Your readiness score of <strong>{Math.round(score)}</strong> was computed from 5 subjective inputs + 3 biometric readings.
              Combined with a <strong>{trend}</strong> trend over your last 7 check-ins, the system recommended <strong>{INTENSITY_CONFIG[intensity].label}</strong> intensity for today.
            </div>
          </div>
        </div>
      )}

      {/* HISTORY VIEW */}
      {view === "history" && (
        <div>
          <div style={{ background: "#fff", borderRadius: 16, padding: 20, border: "1px solid #e5e7eb", marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#374151" }}>Last 7 Days</div>
              <div style={{ fontSize: 12, color: "#9ca3af" }}>Trend: <strong style={{ color: trend === "improving" ? "#22c55e" : trend === "declining" ? "#ef4444" : "#f59e0b" }}>{trend}</strong></div>
            </div>
            <MiniBar history={MOCK_HISTORY} />
          </div>

          <div style={{ background: "#fff", borderRadius: 16, padding: 20, border: "1px solid #e5e7eb" }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#374151", marginBottom: 12 }}>Session Log</div>
            {MOCK_HISTORY.map((d, i) => <HistoryRow key={i} day={d} />)}
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ textAlign: "center", marginTop: 32, fontSize: 11, color: "#d1d5db" }}>
        FastAPI + PostgreSQL · Railway Deploy · GitHub CI/CD
      </div>
    </div>
  );
}
