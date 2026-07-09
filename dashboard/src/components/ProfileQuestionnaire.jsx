import { useState, useEffect, useCallback } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const STORAGE_KEY = "habitguard_profile";

const RISK_LABELS = {
  0: { label: "Low Risk", color: "#4ade80" },
  1: { label: "Moderate Risk", color: "#facc15" },
  2: { label: "High Risk", color: "#f87171" },
};

const SEGMENT_LABELS = {
  0: { label: "Casual User", color: "#60a5fa" },
  1: { label: "Productive Focused", color: "#4ade80" },
  2: { label: "Heavy Distracted", color: "#f87171" },
  3: { label: "Balanced", color: "#a78bfa" },
};

function getRiskLabel(prediction) {
  if (prediction === null || prediction === undefined) return null;
  return RISK_LABELS[prediction] || { label: `Class ${prediction}`, color: "#94a3b8" };
}

function getSegmentLabel(prediction) {
  if (prediction === null || prediction === undefined) return null;
  return SEGMENT_LABELS[prediction] || { label: `Cluster ${prediction}`, color: "#94a3b8" };
}

const DEFAULTS = {
  age: "",
  gender: "male",
  sleep_hours: "",
  stress_level: "",
  social_media_hours: "",
  gaming_hours: "",
  work_study_hours: "",
  notifications_per_day: "",
  app_opens_per_day: "",
  weekend_screen_time: "",
  academic_work_impact: "",
};

export default function ProfileQuestionnaire({ todayScreenTimeMinutes = 0, accentMint, accentPeach, accentYellow }) {
  const [form, setForm] = useState(DEFAULTS);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState(null); // { risk, segment }
  const [error, setError] = useState(null);

  // Load saved profile from localStorage on mount
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved) {
        setForm((prev) => ({ ...prev, ...saved }));
      }
    } catch {
      /* ignore */
    }
  }, []);

  // Auto-run predictions if profile is already saved
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const profile = JSON.parse(saved);
        if (profile.age) {
          runPredictions(profile);
        }
      } catch {
        /* ignore */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function buildPayload(profile, screenTimeMinutes) {
    const gender = profile.gender || "male";
    const daily_screen_time_hours = parseFloat(screenTimeMinutes) / 60 || 0;

    return {
      age: parseFloat(profile.age) || 22,
      daily_screen_time_hours,
      social_media_hours: parseFloat(profile.social_media_hours) || 0,
      gaming_hours: parseFloat(profile.gaming_hours) || 0,
      work_study_hours: parseFloat(profile.work_study_hours) || 0,
      sleep_hours: parseFloat(profile.sleep_hours) || 7,
      notifications_per_day: parseFloat(profile.notifications_per_day) || 50,
      app_opens_per_day: parseFloat(profile.app_opens_per_day) || 20,
      weekend_screen_time: parseFloat(profile.weekend_screen_time) || daily_screen_time_hours,
      stress_level: parseFloat(profile.stress_level) || 5,
      academic_work_impact: parseFloat(profile.academic_work_impact) || 5,
      gender_male: gender === "male" ? 1 : 0,
      gender_other: gender === "other" ? 1 : 0,
    };
  }

  const runPredictions = useCallback(
    async (profile) => {
      setError(null);
      const payload = buildPayload(profile, todayScreenTimeMinutes);

      try {
        const [riskRes, segRes] = await Promise.all([
          fetch(`${API_BASE_URL}/risk/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }),
          fetch(`${API_BASE_URL}/segment/predict`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }),
        ]);

        const riskData = await riskRes.json();
        const segData = await segRes.json();

        setResults({
          risk: riskData,
          segment: segData,
        });
      } catch (err) {
        setError("Could not reach backend. Make sure FastAPI is running.");
        console.error("[ProfileQuestionnaire] prediction error:", err);
      }
    },
    [todayScreenTimeMinutes]
  );

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
      await runPredictions(form);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  function handleClear() {
    localStorage.removeItem(STORAGE_KEY);
    setForm(DEFAULTS);
    setResults(null);
  }

  const riskLabel = results?.risk?.prediction !== undefined
    ? getRiskLabel(results.risk.prediction)
    : null;
  const segLabel = results?.segment?.cluster !== undefined
    ? getSegmentLabel(results.segment.cluster)
    : null;

  const hasSavedProfile = Boolean(localStorage.getItem(STORAGE_KEY));

  return (
    <section className="mb-6">
      {/* Results row — shown when we have predictions */}
      {(riskLabel || segLabel) && (
        <div className="hg-card mb-4 grid gap-5 p-5 md:grid-cols-2">
          {riskLabel && (
            <div className="flex flex-col justify-between">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
                  Addiction Risk Level
                </p>
                <span
                  className="inline-block rounded-full px-3 py-1 text-sm font-semibold"
                  style={{ background: `${riskLabel.color}22`, color: riskLabel.color }}
                >
                  {riskLabel.label}
                </span>
              </div>

              {/* Visual Risk Gauge Meter */}
              {results?.risk?.addicted_probability !== undefined && (
                <div className="mt-4">
                  <div className="flex justify-between text-[11px] mb-1">
                    <span style={{ color: "var(--text-dim)" }}>Probability Score</span>
                    <span className="font-semibold" style={{ color: riskLabel.color }}>
                      {Math.round(results.risk.addicted_probability)}%
                    </span>
                  </div>
                  <div className="relative h-2.5 w-full rounded-full" style={{ background: "linear-gradient(90deg, #4ade80, #facc15, #f87171)", opacity: 0.85 }}>
                    <div 
                      className="absolute top-1/2 -translate-y-1/2 h-4.5 w-2 rounded" 
                      style={{ 
                        left: `calc(${Math.min(98, Math.max(2, results.risk.addicted_probability))}% - 4px)`, 
                        background: "var(--text)",
                        boxShadow: "0 0 2px var(--card)",
                        border: "1px solid var(--card-border)"
                      }}
                    />
                  </div>
                  <div className="flex justify-between text-[9px] mt-1" style={{ color: "var(--text-dim)", opacity: 0.8 }}>
                    <span>Low Risk</span>
                    <span>Moderate</span>
                    <span>High Risk</span>
                  </div>
                </div>
              )}

              <p className="hg-mono mt-3 text-[10px]" style={{ color: "var(--text-dim)", opacity: 0.65 }}>
                Based on voluntarily declared demographic indicators.
              </p>
            </div>
          )}

          {segLabel && (
            <div className="flex flex-col justify-between">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
                  Usage Segment Profile
                </p>
                <span
                  className="inline-block rounded-full px-3 py-1 text-sm font-semibold"
                  style={{ background: `${segLabel.color}22`, color: segLabel.color }}
                >
                  {results.segment.segment_name || segLabel.label}
                </span>
              </div>

              {/* Visual mini-metrics display */}
              <div className="mt-4 grid grid-cols-3 gap-2 border-t pt-3" style={{ borderColor: "var(--card-border)" }}>
                <div>
                  <p className="text-[10px]" style={{ color: "var(--text-dim)" }}>Social Media</p>
                  <p className="font-semibold text-xs mt-0.5">{form.social_media_hours || 0} hrs</p>
                  <div className="h-1 w-full rounded-full mt-1" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, ((parseFloat(form.social_media_hours) || 0) / 10) * 100)}%`, background: segLabel.color }} />
                  </div>
                </div>

                <div>
                  <p className="text-[10px]" style={{ color: "var(--text-dim)" }}>Gaming</p>
                  <p className="font-semibold text-xs mt-0.5">{form.gaming_hours || 0} hrs</p>
                  <div className="h-1 w-full rounded-full mt-1" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, ((parseFloat(form.gaming_hours) || 0) / 10) * 100)}%`, background: segLabel.color }} />
                  </div>
                </div>

                <div>
                  <p className="text-[10px]" style={{ color: "var(--text-dim)" }}>Work/Study</p>
                  <p className="font-semibold text-xs mt-0.5">{form.work_study_hours || 0} hrs</p>
                  <div className="h-1 w-full rounded-full mt-1" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
                    <div className="h-full rounded-full" style={{ width: `${Math.min(100, ((parseFloat(form.work_study_hours) || 0) / 10) * 100)}%`, background: segLabel.color }} />
                  </div>
                </div>
              </div>

              <p className="hg-mono mt-3 text-[10px]" style={{ color: "var(--text-dim)", opacity: 0.65 }}>
                Exploratory behavioral grouping (KMeans Silhouette clusters).
              </p>
            </div>
          )}
        </div>
      )}

      {/* Toggle button */}
      <div className="flex items-center gap-3">
        <button
          id="profile-questionnaire-toggle"
          className="hg-btn-secondary text-sm"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Close Profile" : hasSavedProfile ? "Edit Profile" : "Set Up Profile"}
        </button>
        {hasSavedProfile && !open && (
          <button
            id="profile-clear-btn"
            className="text-xs"
            style={{ color: "var(--text-dim)" }}
            onClick={handleClear}
          >
            Clear saved profile
          </button>
        )}
      </div>

      {/* Questionnaire form */}
      {open && (
        <div className="hg-card mt-4 p-6">
          <h3 className="hg-display mb-1 text-base font-medium">
            Usage Profile
          </h3>
          <p className="mb-5 text-xs" style={{ color: "var(--text-dim)" }}>
            Voluntary. Saved locally — never sent without your action. Used to run the risk and segment models.
          </p>

          {error && (
            <p className="mb-4 text-sm" style={{ color: accentPeach || "#f87171" }}>
              {error}
            </p>
          )}

          <form id="profile-form" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Age" name="age" type="number" min={10} max={80} placeholder="e.g. 22" form={form} onChange={handleChange} />

              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>Gender</label>
                <select
                  id="profile-gender"
                  name="gender"
                  value={form.gender}
                  onChange={handleChange}
                  className="hg-input"
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <Field label="Sleep hours / night" name="sleep_hours" type="number" min={3} max={12} step={0.5} placeholder="e.g. 7" form={form} onChange={handleChange} />
              <Field label="Stress level (1–10)" name="stress_level" type="number" min={1} max={10} placeholder="e.g. 5" form={form} onChange={handleChange} />
              <Field label="Social media hours / day" name="social_media_hours" type="number" min={0} max={16} step={0.5} placeholder="e.g. 2" form={form} onChange={handleChange} />
              <Field label="Gaming hours / day" name="gaming_hours" type="number" min={0} max={16} step={0.5} placeholder="e.g. 1" form={form} onChange={handleChange} />
              <Field label="Work / study hours / day" name="work_study_hours" type="number" min={0} max={16} step={0.5} placeholder="e.g. 6" form={form} onChange={handleChange} />
              <Field label="Notifications / day" name="notifications_per_day" type="number" min={0} max={500} placeholder="e.g. 80" form={form} onChange={handleChange} />
              <Field label="App opens / day" name="app_opens_per_day" type="number" min={0} max={300} placeholder="e.g. 40" form={form} onChange={handleChange} />
              <Field label="Weekend screen time (hours)" name="weekend_screen_time" type="number" min={0} max={18} step={0.5} placeholder="e.g. 5" form={form} onChange={handleChange} />
              <Field label="Academic / work impact (1–10)" name="academic_work_impact" type="number" min={1} max={10} placeholder="e.g. 6" form={form} onChange={handleChange} />
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                id="profile-submit-btn"
                type="submit"
                className="hg-btn-primary text-sm"
                disabled={saving}
              >
                {saving ? "Running…" : "Save & Predict"}
              </button>
              <button
                type="button"
                className="text-xs"
                style={{ color: "var(--text-dim)" }}
                onClick={() => setOpen(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}

function Field({ label, name, type, min, max, step, placeholder, form, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={`profile-${name}`} className="text-xs font-medium" style={{ color: "var(--text-dim)" }}>
        {label}
      </label>
      <input
        id={`profile-${name}`}
        name={name}
        type={type}
        min={min}
        max={max}
        step={step}
        placeholder={placeholder}
        value={form[name]}
        onChange={onChange}
        className="hg-input"
      />
    </div>
  );
}
