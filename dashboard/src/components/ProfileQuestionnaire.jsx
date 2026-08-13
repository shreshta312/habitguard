import { useCallback, useEffect, useState } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const STORAGE_KEY = "habitguard_profile";

const RISK_LABELS = {
  0: { label: "Low Risk", color: "#4ade80" },
  1: { label: "High Risk", color: "#f87171" },
};

const SEGMENT_LABELS = {
  0: { label: "Casual User", color: "#60a5fa" },
  1: { label: "Productive Focused", color: "#4ade80" },
  2: { label: "Heavy Distracted", color: "#f87171" },
  3: { label: "Balanced", color: "#a78bfa" },
};

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

function getRiskLabel(prediction) {
  if (prediction === null || prediction === undefined) {
    return null;
  }

  return (
    RISK_LABELS[prediction] || {
      label: `Class ${prediction}`,
      color: "#94a3b8",
    }
  );
}

function getSegmentLabel(prediction) {
  if (prediction === null || prediction === undefined) {
    return null;
  }

  return (
    SEGMENT_LABELS[prediction] || {
      label: `Cluster ${prediction}`,
      color: "#94a3b8",
    }
  );
}

function buildPayload(profile, screenTimeMinutes) {
  const gender = profile.gender || "male";

  const dailyScreenTimeHours =
    Number.parseFloat(screenTimeMinutes) / 60 || 0;

  return {
    age: Number.parseFloat(profile.age) || 22,
    daily_screen_time_hours: dailyScreenTimeHours,
    social_media_hours:
      Number.parseFloat(profile.social_media_hours) || 0,
    gaming_hours: Number.parseFloat(profile.gaming_hours) || 0,
    work_study_hours:
      Number.parseFloat(profile.work_study_hours) || 0,
    sleep_hours: Number.parseFloat(profile.sleep_hours) || 7,
    notifications_per_day:
      Number.parseFloat(profile.notifications_per_day) || 50,
    app_opens_per_day:
      Number.parseFloat(profile.app_opens_per_day) || 20,
    weekend_screen_time:
      Number.parseFloat(profile.weekend_screen_time) ||
      dailyScreenTimeHours,
    stress_level: Number.parseFloat(profile.stress_level) || 5,
    academic_work_impact:
      Number.parseFloat(profile.academic_work_impact) || 5,
    gender_male: gender === "male" ? 1 : 0,
    gender_other: gender === "other" ? 1 : 0,
  };
}

export default function ProfileQuestionnaire({
  todayScreenTimeMinutes = 0,
  accentPeach,
}) {
  const [form, setForm] = useState(DEFAULTS);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const savedProfile = JSON.parse(
        localStorage.getItem(STORAGE_KEY) || "null",
      );

      if (savedProfile) {
        setForm((previous) => ({
          ...previous,
          ...savedProfile,
        }));
      }
    } catch (loadError) {
      console.error(
        "[ProfileQuestionnaire] Failed to load profile:",
        loadError,
      );
    }
  }, []);

  const runPredictions = useCallback(
    async (profile) => {
      setError("");

      const payload = buildPayload(
        profile,
        todayScreenTimeMinutes,
      );

      try {
        const [riskResponse, segmentResponse] =
          await Promise.all([
            fetch(`${API_BASE_URL}/risk/predict`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(payload),
            }),
            fetch(`${API_BASE_URL}/segment/predict`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify(payload),
            }),
          ]);

        const riskData = await riskResponse.json();
        const segmentData = await segmentResponse.json();

        if (!riskResponse.ok) {
          throw new Error(
            riskData?.detail ||
            riskData?.error ||
            "Risk prediction failed.",
          );
        }

        if (!segmentResponse.ok) {
          throw new Error(
            segmentData?.detail ||
            segmentData?.error ||
            "Segmentation prediction failed.",
          );
        }

        setResults({
          risk: riskData,
          segment: segmentData,
        });
      } catch (predictionError) {
        console.error(
          "[ProfileQuestionnaire] Prediction error:",
          predictionError,
        );

        setError(
          predictionError instanceof Error
            ? predictionError.message
            : "Could not reach the backend.",
        );
      }
    },
    [todayScreenTimeMinutes],
  );

  useEffect(() => {
    try {
      const savedProfile = JSON.parse(
        localStorage.getItem(STORAGE_KEY) || "null",
      );

      if (savedProfile?.age) {
        runPredictions(savedProfile);
      }
    } catch (predictionError) {
      console.error(
        "[ProfileQuestionnaire] Automatic prediction failed:",
        predictionError,
      );
    }
  }, [runPredictions]);

  function handleChange(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setSaving(true);
    setError("");

    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(form),
      );

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
    setError("");
  }

  const riskLabel =
    results?.risk?.prediction !== undefined
      ? getRiskLabel(results.risk.prediction)
      : null;

  const segmentLabel =
    results?.segment?.cluster !== undefined
      ? getSegmentLabel(results.segment.cluster)
      : null;

  const hasSavedProfile = Boolean(
    localStorage.getItem(STORAGE_KEY),
  );

  return (
    <section className="mb-6">
      {(riskLabel || segmentLabel) && (
        <div className="hg-card mb-4 grid gap-5 p-5 md:grid-cols-2">
          {riskLabel && (
            <div className="flex flex-col justify-between">
              <div>
                <p
                  className="mb-1 text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--text-dim)" }}
                >
                  Habit Risk Category
                </p>

                <span
                  className="inline-block rounded-full px-3 py-1 text-sm font-semibold"
                  style={{
                    background: `${riskLabel.color}22`,
                    color: riskLabel.color,
                  }}
                >
                  {riskLabel.label}
                </span>
              </div>

              {results?.risk?.addicted_probability !==
                undefined && (
                  <div className="mt-4">
                    <div className="mb-1 flex justify-between text-[11px]">
                      <span
                        style={{
                          color: "var(--text-dim)",
                        }}
                      >
                        Probability Score
                      </span>

                      <span
                        className="font-semibold"
                        style={{ color: riskLabel.color }}
                      >
                        {Math.round(
                          results.risk.addicted_probability,
                        )}
                        %
                      </span>
                    </div>

                    <div
                      className="relative h-2.5 w-full rounded-full"
                      style={{
                        background:
                          "linear-gradient(90deg, #4ade80, #facc15, #f87171)",
                        opacity: 0.85,
                      }}
                    >
                      <div
                        className="absolute top-1/2 h-4.5 w-2 -translate-y-1/2 rounded"
                        style={{
                          left: `calc(${Math.min(
                            98,
                            Math.max(
                              2,
                              results.risk
                                .addicted_probability,
                            ),
                          )}% - 4px)`,
                          background: "var(--text)",
                          boxShadow:
                            "0 0 2px var(--card)",
                          border:
                            "1px solid var(--card-border)",
                        }}
                      />
                    </div>

                    <div
                      className="mt-1 flex justify-between text-[9px]"
                      style={{
                        color: "var(--text-dim)",
                        opacity: 0.8,
                      }}
                    >
                      <span>Low Risk</span>
                      <span>Moderate</span>
                      <span>High Risk</span>
                    </div>
                  </div>
                )}

              <p
                className="hg-mono mt-3 text-[10px]"
                style={{
                  color: "var(--text-dim)",
                  opacity: 0.65,
                }}
              >
                Based on voluntarily declared demographic
                and behavioural indicators.
              </p>
            </div>
          )}

          {segmentLabel && (
            <div className="flex flex-col justify-between">
              <div>
                <p
                  className="mb-1 text-xs font-semibold uppercase tracking-wider"
                  style={{ color: "var(--text-dim)" }}
                >
                  Usage Segment Profile
                </p>

                <span
                  className="inline-block rounded-full px-3 py-1 text-sm font-semibold"
                  style={{
                    background: `${segmentLabel.color}22`,
                    color: segmentLabel.color,
                  }}
                >
                  {results.segment.segment_name ||
                    segmentLabel.label}
                </span>
              </div>

              <div
                className="mt-4 grid grid-cols-3 gap-2 border-t pt-3"
                style={{
                  borderColor: "var(--card-border)",
                }}
              >
                <MiniMetric
                  label="Social Media"
                  value={form.social_media_hours}
                  color={segmentLabel.color}
                />

                <MiniMetric
                  label="Gaming"
                  value={form.gaming_hours}
                  color={segmentLabel.color}
                />

                <MiniMetric
                  label="Work/Study"
                  value={form.work_study_hours}
                  color={segmentLabel.color}
                />
              </div>

              <p
                className="hg-mono mt-3 text-[10px]"
                style={{
                  color: "var(--text-dim)",
                  opacity: 0.65,
                }}
              >
                Exploratory behavioural grouping using
                KMeans clustering.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          id="profile-questionnaire-toggle"
          type="button"
          className="hg-btn-secondary text-sm"
          onClick={() =>
            setOpen((previous) => !previous)
          }
        >
          {open
            ? "Close Profile"
            : hasSavedProfile
              ? "Edit Profile"
              : "Set Up Profile"}
        </button>

        {hasSavedProfile && !open && (
          <button
            id="profile-clear-btn"
            type="button"
            className="text-xs"
            style={{ color: "var(--text-dim)" }}
            onClick={handleClear}
          >
            Clear saved profile
          </button>
        )}
      </div>

      {open && (
        <div className="hg-card mt-4 p-6">
          <h3 className="hg-display mb-1 text-base font-medium">
            Usage Profile
          </h3>

          <p
            className="mb-5 text-xs"
            style={{ color: "var(--text-dim)" }}
          >
            Voluntary and saved locally. Submitted data is
            used to run the risk and experimental segment
            models.
          </p>

          {error && (
            <p
              className="mb-4 text-sm"
              style={{
                color: accentPeach || "#f87171",
              }}
            >
              {error}
            </p>
          )}

          <form
            id="profile-form"
            onSubmit={handleSubmit}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field
                label="Age"
                name="age"
                type="number"
                min={10}
                max={80}
                placeholder="e.g. 22"
                form={form}
                onChange={handleChange}
              />

              <div className="flex flex-col gap-1">
                <label
                  htmlFor="profile-gender"
                  className="text-xs font-medium"
                  style={{
                    color: "var(--text-dim)",
                  }}
                >
                  Gender
                </label>

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

              <Field
                label="Sleep hours / night"
                name="sleep_hours"
                type="number"
                min={3}
                max={12}
                step={0.5}
                placeholder="e.g. 7"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Stress level (1–10)"
                name="stress_level"
                type="number"
                min={1}
                max={10}
                placeholder="e.g. 5"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Social media hours / day"
                name="social_media_hours"
                type="number"
                min={0}
                max={16}
                step={0.5}
                placeholder="e.g. 2"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Gaming hours / day"
                name="gaming_hours"
                type="number"
                min={0}
                max={16}
                step={0.5}
                placeholder="e.g. 1"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Work / study hours / day"
                name="work_study_hours"
                type="number"
                min={0}
                max={16}
                step={0.5}
                placeholder="e.g. 6"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Notifications / day"
                name="notifications_per_day"
                type="number"
                min={0}
                max={500}
                placeholder="e.g. 80"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="App opens / day"
                name="app_opens_per_day"
                type="number"
                min={0}
                max={300}
                placeholder="e.g. 40"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Weekend screen time (hours)"
                name="weekend_screen_time"
                type="number"
                min={0}
                max={18}
                step={0.5}
                placeholder="e.g. 5"
                form={form}
                onChange={handleChange}
              />

              <Field
                label="Academic / work impact (1–10)"
                name="academic_work_impact"
                type="number"
                min={1}
                max={10}
                placeholder="e.g. 6"
                form={form}
                onChange={handleChange}
              />
            </div>

            <div className="mt-5 flex items-center gap-3">
              <button
                id="profile-submit-btn"
                type="submit"
                className="hg-btn-primary text-sm"
                disabled={saving}
              >
                {saving
                  ? "Running…"
                  : "Save & Predict"}
              </button>

              <button
                type="button"
                className="text-xs"
                style={{
                  color: "var(--text-dim)",
                }}
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

function MiniMetric({ label, value, color }) {
  const numericValue = Number.parseFloat(value) || 0;
  const width = Math.min(
    100,
    (numericValue / 10) * 100,
  );

  return (
    <div>
      <p
        className="text-[10px]"
        style={{ color: "var(--text-dim)" }}
      >
        {label}
      </p>

      <p className="mt-0.5 text-xs font-semibold">
        {numericValue} hrs
      </p>

      <div
        className="mt-1 h-1 w-full rounded-full"
        style={{
          background: "rgba(148, 163, 184, 0.12)",
        }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${width}%`,
            background: color,
          }}
        />
      </div>
    </div>
  );
}

function Field({
  label,
  name,
  type,
  min,
  max,
  step,
  placeholder,
  form,
  onChange,
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={`profile-${name}`}
        className="text-xs font-medium"
        style={{ color: "var(--text-dim)" }}
      >
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