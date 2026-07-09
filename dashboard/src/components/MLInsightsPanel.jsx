/**
 * MLInsightsPanel.jsx
 *
 * Displays the two ML model output cards:
 *  1. Usage Anomaly — IsolationForest result with feature progress bars
 *  2. Tomorrow's Forecast — RandomForest prediction with confidence badge and comparison bars
 */
import { AlertTriangle, Cpu, BarChart2 } from "lucide-react";

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatMinutes(value, emptyLabel = "0 min") {
  if (value === null || value === undefined || value === "") return emptyLabel;
  const minutes = Math.round(toNumber(value));
  if (minutes <= 0) return "0 min";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem === 0 ? `${hours}h` : `${hours}h ${rem}m`;
}

function ProgressBar({ label, value, maxValue, accent, unit = "" }) {
  const pct = Math.min(100, (toNumber(value) / Math.max(1, maxValue)) * 100);
  return (
    <div>
      <div className="flex justify-between text-[11px]" style={{ color: "var(--text-dim)" }}>
        <span>{label}</span>
        <span className="font-medium" style={{ color: "var(--text)" }}>
          {value}{unit}
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: accent }}
        />
      </div>
    </div>
  );
}

export default function MLInsightsPanel({ anomalyData, forecastData, liveUsage, accents }) {
  if (!anomalyData?.result && !forecastData?.success) return null;

  const anomalyAccent = anomalyData?.result === "ANOMALY" ? accents.peach : accents.mint;

  return (
    <section className="mb-6 grid gap-4 md:grid-cols-2">
      {/* ── Anomaly Card ── */}
      <div className="hg-card p-5">
        <div className="mb-3 flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-full"
            style={{
              background: `${anomalyAccent}2A`,
              color: anomalyAccent,
            }}
          >
            {anomalyData?.result === "ANOMALY" ? <AlertTriangle size={14} /> : <Cpu size={14} />}
          </div>
          <h3 className="hg-display text-base font-medium">Usage Anomaly</h3>
        </div>

        {!anomalyData?.result ? (
          <p className="text-sm" style={{ color: "var(--text-dim)" }}>No anomaly data yet.</p>
        ) : (
          <>
            <p className="hg-mono text-sm font-medium" style={{ color: anomalyAccent }}>
              {anomalyData.result}
            </p>
            <p className="mt-1 text-sm" style={{ color: "var(--text-dim)" }}>
                {anomalyData.result === "ANOMALY"
                  ? "Unusual compared to training data, not necessarily harmful."
                  : anomalyData.message || "Pattern analysis complete."}
            </p>

            <div className="mt-4 space-y-2.5 border-t pt-3" style={{ borderColor: "var(--card-border)" }}>
              <ProgressBar
                label="Screen Time"
                value={anomalyData.screen_time_min || 0}
                maxValue={180}
                accent={anomalyAccent}
                unit=" min"
              />
              <ProgressBar
                label="Launches (estimated)"
                value={anomalyData.launches || 0}
                maxValue={60}
                accent={anomalyAccent}
              />
              <ProgressBar
                label="Interactions (estimated)"
                value={anomalyData.interactions || 0}
                maxValue={1500}
                accent={anomalyAccent}
              />
            </div>

            {anomalyData.disclosures?.note && (
              <p
                className="hg-mono mt-3 text-[10px] leading-relaxed"
                style={{ color: "var(--text-dim)", opacity: 0.7 }}
              >
                ⚠ {anomalyData.disclosures.note}
              </p>
            )}
          </>
        )}
      </div>

      {/* ── Forecast Card ── */}
      <div className="hg-card p-5">
        <div className="mb-3 flex items-center gap-2">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-full"
            style={{ background: `${accents.mint}2A`, color: accents.mint }}
          >
            <BarChart2 size={14} />
          </div>
          <h3 className="hg-display text-base font-medium">Tomorrow's Forecast</h3>
        </div>

        {!forecastData?.success ? (
          <p className="text-sm" style={{ color: "var(--text-dim)" }}>
            {forecastData?.error || "Need at least 3 days of usage history for a forecast."}
          </p>
        ) : (
          <>
            <p className="hg-mono text-2xl font-medium">
              {formatMinutes(forecastData.forecast_minutes)}
            </p>

            <div className="mt-2 flex items-center gap-2">
              <span
                className="rounded-full px-2 py-0.5 text-xs font-medium"
                style={{
                  background:
                    forecastData.confidence === "HIGH"
                      ? `${accents.mint}2A`
                      : forecastData.confidence === "MEDIUM"
                      ? `${accents.peach}2A`
                      : `${accents.yellow}2A`,
                  color:
                    forecastData.confidence === "HIGH"
                      ? accents.mint
                      : forecastData.confidence === "MEDIUM"
                      ? accents.peach
                      : accents.yellow,
                }}
              >
                {forecastData.confidence} confidence
              </span>
            </div>

            {/* Today vs Forecast comparison bars */}
            <div className="mt-4 space-y-3 border-t pt-3" style={{ borderColor: "var(--card-border)" }}>
              <div>
                <div className="flex justify-between text-[11px]" style={{ color: "var(--text-dim)" }}>
                  <span>Today's Total Screen Time</span>
                  <span className="font-medium" style={{ color: "var(--text)" }}>
                    {liveUsage.screenTimeMinutes} min
                  </span>
                </div>
                <div className="h-2 w-full rounded-full" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, (liveUsage.screenTimeMinutes / Math.max(1, liveUsage.screenTimeMinutes, forecastData.forecast_minutes)) * 100)}%`,
                      background: accents.mint,
                    }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px]" style={{ color: "var(--text-dim)" }}>
                  <span>Tomorrow's Predicted Forecast</span>
                  <span className="font-medium" style={{ color: "var(--text)" }}>
                    {Math.round(forecastData.forecast_minutes)} min
                  </span>
                </div>
                <div className="h-2 w-full rounded-full" style={{ background: "rgba(148, 163, 184, 0.12)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${Math.min(100, (forecastData.forecast_minutes / Math.max(1, liveUsage.screenTimeMinutes, forecastData.forecast_minutes)) * 100)}%`,
                      background: accents.yellow,
                    }}
                  />
                </div>
              </div>
            </div>

            <p className="hg-mono mt-3 text-[10px]" style={{ color: "var(--text-dim)", opacity: 0.7 }}>
              Powered by RandomForest trained on 7-day lag features.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
