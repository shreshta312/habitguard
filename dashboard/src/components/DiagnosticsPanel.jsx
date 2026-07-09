import { useState, useEffect, useCallback } from "react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function Badge({ label, ok }) {
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        background: ok ? "rgba(74,222,128,0.15)" : "rgba(248,113,113,0.15)",
        color: ok ? "#4ade80" : "#f87171",
      }}
    >
      {label}
    </span>
  );
}

function ModelSection({ title, data }) {
  if (!data) return null;

  return (
    <div className="mb-4">
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <div className="grid gap-1 text-xs" style={{ color: "var(--text-dim)" }}>
        {Object.entries(data).map(([key, value]) => {
          if (key === "top_features" && Array.isArray(value)) {
            return (
              <div key={key}>
                <span className="font-medium">Top features:</span>
                <ul className="ml-4 mt-1" style={{ listStyle: "disc" }}>
                  {value.map((f, i) => (
                    <li key={i}>
                      <span className="hg-mono">{f.name}</span>{" "}
                      <span style={{ color: "var(--text)" }}>
                        ({(f.importance * 100).toFixed(1)}%)
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          }

          let display;
          if (Array.isArray(value)) {
            display = value.map((v) => (typeof v === "number" ? v.toFixed(4) : String(v))).join(", ");
          } else if (typeof value === "object" && value !== null) {
            display = JSON.stringify(value);
          } else {
            display = String(value);
          }

          return (
            <div key={key} className="flex justify-between gap-4">
              <span>{key.replace(/_/g, " ")}</span>
              <span className="hg-mono text-right" style={{ color: "var(--text)" }}>
                {display}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DiagnosticsPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchDiagnostics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/diagnostics`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && !data) {
      fetchDiagnostics();
    }
  }, [open, data, fetchDiagnostics]);

  const loaded = data?.models_loaded || {};

  return (
    <section className="mb-6">
      <button
        id="diagnostics-toggle"
        className="hg-btn-secondary text-sm"
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "Hide Diagnostics" : "Model Diagnostics"}
      </button>

      {open && (
        <div className="hg-card mt-4 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="hg-display text-base font-medium">
              ML Model Diagnostics
            </h3>
            <button
              className="hg-btn-secondary text-xs"
              onClick={fetchDiagnostics}
              disabled={loading}
            >
              {loading ? "Loading…" : "Refresh"}
            </button>
          </div>

          {error && (
            <p className="mb-3 text-sm" style={{ color: "#f87171" }}>
              {error}
            </p>
          )}

          {data && (
            <>
              {/* Load status badges */}
              <div className="mb-5 flex flex-wrap gap-2">
                <Badge label="Anomaly Detector" ok={loaded.anomaly_detector} />
                <Badge label="Anomaly Scaler" ok={loaded.anomaly_scaler} />
                <Badge label="Risk Classifier" ok={loaded.risk_classifier} />
                <Badge label="Usage Forecaster" ok={loaded.usage_forecaster} />
                <Badge label="User Segmentation" ok={loaded.user_segmentation} />
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <ModelSection title="Anomaly Detector" data={data.anomaly_detector} />
                <ModelSection title="Risk Classifier" data={data.risk_classifier} />
                <ModelSection title="Usage Forecaster" data={data.usage_forecaster} />
                <ModelSection title="User Segmentation" data={data.user_segmentation} />
              </div>

              <p
                className="hg-mono mt-4 text-xs"
                style={{ color: "var(--text-dim)", opacity: 0.6 }}
              >
                Diagnostics are read-only introspections of model attributes. No
                live data is used.
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
