/**
 * InterventionCard.jsx
 *
 * Displays the latest intervention decision:
 *  - Usage status + message
 *  - Decision reason
 *  - Limit usage tracker progress bar
 *  - JITAI delivery policy (notify, overlay, cooldown)
 *  - Friction type badge
 */
import {
  Play,
  Bell,
  BellOff,
  Layers,
  Timer,
} from "lucide-react";

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

function formatSignedMinutes(value) {
  const minutes = Math.round(toNumber(value));
  return minutes <= 0 ? "0 min" : `+${minutes} min`;
}

function frictionAccent(accents, frictionType = "") {
  const friction = String(frictionType).toUpperCase();
  if (friction.includes("STRONG")) return accents.yellow;
  if (friction.includes("WARNING") || friction.includes("TIMER")) return accents.peach;
  return accents.mint;
}

export default function InterventionCard({
  latestIntervention,
  overuseGap,
  recommendedTimer,
  topDomain,
  currentSessionText,
  accents,
  theme,
}) {
  return (
    <section className="hg-card mb-6 p-6 md:p-8">
      <h3 className="hg-display mb-4 text-lg font-medium">Latest intervention</h3>

      {!latestIntervention?.usage_status ? (
        <p className="text-sm" style={{ color: "var(--text-dim)" }}>
          No latest intervention yet. This will update after the extension sends an
          intervention result to the backend.
        </p>
      ) : (
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm">
              <strong>{latestIntervention.usage_status}</strong>
              {latestIntervention.message ? <> · {latestIntervention.message}</> : null}
            </p>

            {latestIntervention.decision_reason && (
              <p className="hg-mono mt-2 text-xs leading-relaxed" style={{ color: "var(--text-dim)" }}>
                {latestIntervention.decision_reason}
              </p>
            )}

            {/* ── Limit Usage Tracker ── */}
            {(() => {
              const recent = toNumber(latestIntervention.recent_usage_minutes, 0);
              const baseline = toNumber(latestIntervention.baseline_usage_minutes, 0);
              const maxVal = Math.max(recent, baseline, 1);
              const recentPct = Math.round((recent / maxVal) * 100);
              const baselinePct = Math.round((baseline / maxVal) * 100);
              const isOverLimit = recent > baseline;

              return (
                <div className="mt-4 border-y py-3 space-y-2" style={{ borderColor: "var(--card-border)" }}>
                  <div className="flex justify-between text-xs" style={{ color: "var(--text-dim)" }}>
                    <span>Limit Usage Tracker</span>
                    <span className="font-semibold" style={{ color: isOverLimit ? accents.peach : "var(--text)" }}>
                      {recent} min / {baseline} min limit
                    </span>
                  </div>

                  <div
                    className="relative h-4 w-full rounded-full overflow-hidden"
                    style={{ background: "rgba(148, 163, 184, 0.12)" }}
                  >
                    <div
                      className="absolute top-0 bottom-0 w-0.5 z-10"
                      style={{
                        left: `${baselinePct}%`,
                        background: "var(--text)",
                        boxShadow: "0 0 2px var(--card)",
                      }}
                      title={`Baseline Limit: ${baseline} min`}
                    />
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${recentPct}%`,
                        background: isOverLimit
                          ? `linear-gradient(90deg, ${accents.mint}, ${accents.peach})`
                          : accents.mint,
                      }}
                    />
                  </div>

                  <div className="flex justify-between text-[11px]" style={{ color: "var(--text-dim)" }}>
                    <span>Recent: {recent} min</span>
                    <span>Rho calibration: {latestIntervention.rho_user ?? "Not available"}</span>
                    <span>Baseline: {baseline} min</span>
                  </div>

                  {isOverLimit && (
                    <p className="text-[11px] leading-snug mt-1" style={{ color: accents.peach }}>
                      ⚠️ Overuse detected: You are {Math.round(recent - baseline)} min above your
                      behavioral baseline target.
                    </p>
                  )}
                </div>
              );
            })()}

            {/* ── JITAI Delivery Policy ── */}
            <div
              className="mt-4 flex flex-wrap items-center gap-3 border-t pt-3 text-xs"
              style={{ borderColor: "var(--card-border)", color: "var(--text-dim)" }}
            >
              <div className="flex items-center gap-1.5">
                {latestIntervention.should_notify ? (
                  <Bell size={12} style={{ color: accents.peach }} />
                ) : (
                  <BellOff size={12} />
                )}
                <span>
                  Notify:{" "}
                  <strong style={{ color: latestIntervention.should_notify ? accents.peach : "var(--text)" }}>
                    {latestIntervention.should_notify ? "Yes" : "No"}
                  </strong>
                </span>
              </div>

              <div className="flex items-center gap-1.5">
                <Layers size={12} />
                <span>
                  Overlay:{" "}
                  <strong style={{ color: latestIntervention.should_overlay ? accents.peach : "var(--text)" }}>
                    {latestIntervention.should_overlay ? "Yes" : "No"}
                  </strong>
                </span>
              </div>

              {latestIntervention.cooldown_minutes !== undefined && (
                <div className="flex items-center gap-1.5">
                  <Timer size={12} />
                  <span>
                    Cooldown:{" "}
                    <strong style={{ color: "var(--text)" }}>
                      {latestIntervention.cooldown_minutes} min
                    </strong>
                  </span>
                </div>
              )}

              {latestIntervention.delivery_reason && (
                <p className="mt-1 w-full leading-relaxed" style={{ opacity: 0.75 }}>
                  {latestIntervention.delivery_reason}
                </p>
              )}
            </div>
          </div>

          {latestIntervention.friction_type && (
            <span
              className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
              style={{
                background: `${frictionAccent(accents, latestIntervention.friction_type)}2A`,
                color: frictionAccent(accents, latestIntervention.friction_type),
              }}
            >
              {latestIntervention.friction_type}
            </span>
          )}
        </div>
      )}
    </section>
  );
}
