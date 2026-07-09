/**
 * WeeklyRecapCard.jsx
 *
 * Displays a summary "recap" card for the past 7 days:
 *  - Total screen time for the week
 *  - Daily average
 *  - Busiest day
 *  - Trend direction (up/down/flat vs prior week placeholder)
 *  - Mini sparkline bar chart
 */
import { Calendar, TrendingDown, TrendingUp, Minus } from "lucide-react";

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function formatMinutes(minutes) {
  if (minutes <= 0) return "0 min";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const rem = Math.round(minutes % 60);
  return rem === 0 ? `${hours}h` : `${hours}h ${rem}m`;
}

export default function WeeklyRecapCard({ weeklyTrend, accents }) {
  if (!weeklyTrend || weeklyTrend.length < 2) return null;

  const totalMinutes = weeklyTrend.reduce((sum, d) => sum + toNumber(d.minutes), 0);
  const avgMinutes = Math.round(totalMinutes / weeklyTrend.length);
  const maxDay = weeklyTrend.reduce((best, d) => (d.minutes > best.minutes ? d : best), weeklyTrend[0]);
  const maxMinutes = Math.max(...weeklyTrend.map((d) => d.minutes), 1);

  // Trend: compare first half vs second half
  const halfLen = Math.floor(weeklyTrend.length / 2);
  const firstHalf = weeklyTrend.slice(0, halfLen).reduce((s, d) => s + d.minutes, 0) / halfLen;
  const secondHalf = weeklyTrend.slice(halfLen).reduce((s, d) => s + d.minutes, 0) / (weeklyTrend.length - halfLen);
  const trendDelta = secondHalf - firstHalf;
  const trendLabel = trendDelta > 10 ? "Trending up" : trendDelta < -10 ? "Trending down" : "Stable";
  const TrendIcon = trendDelta > 10 ? TrendingUp : trendDelta < -10 ? TrendingDown : Minus;
  const trendColor = trendDelta > 10 ? accents.peach : trendDelta < -10 ? accents.mint : accents.yellow;

  return (
    <section className="hg-card mb-6 p-6">
      <div className="mb-4 flex items-center gap-2">
        <div
          className="flex h-7 w-7 items-center justify-center rounded-full"
          style={{ background: `${accents.mint}2A`, color: accents.mint }}
        >
          <Calendar size={14} />
        </div>
        <h3 className="hg-display text-base font-medium">Weekly Recap</h3>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {/* Total */}
        <div>
          <p className="text-[11px] uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
            Total
          </p>
          <p className="hg-mono mt-1 text-xl font-medium">{formatMinutes(totalMinutes)}</p>
        </div>

        {/* Daily Avg */}
        <div>
          <p className="text-[11px] uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
            Daily Avg
          </p>
          <p className="hg-mono mt-1 text-xl font-medium">{formatMinutes(avgMinutes)}</p>
        </div>

        {/* Busiest Day */}
        <div>
          <p className="text-[11px] uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
            Busiest Day
          </p>
          <p className="hg-mono mt-1 text-xl font-medium">
            {maxDay.day}{" "}
            <span className="text-sm font-normal" style={{ color: "var(--text-dim)" }}>
              ({formatMinutes(maxDay.minutes)})
            </span>
          </p>
        </div>

        {/* Trend */}
        <div>
          <p className="text-[11px] uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
            Trend
          </p>
          <div className="mt-1 flex items-center gap-1.5">
            <TrendIcon size={16} style={{ color: trendColor }} />
            <span className="hg-mono text-sm font-medium" style={{ color: trendColor }}>
              {trendLabel}
            </span>
          </div>
        </div>
      </div>

      {/* Mini sparkline bars */}
      <div className="mt-5 flex items-end gap-1.5" style={{ height: 48 }}>
        {weeklyTrend.map((d, i) => {
          const height = Math.max(4, (d.minutes / maxMinutes) * 48);
          const isMax = d === maxDay;
          return (
            <div key={i} className="flex flex-1 flex-col items-center gap-1">
              <div
                className="w-full rounded-t-md transition-all duration-300"
                style={{
                  height,
                  background: isMax ? accents.peach : accents.mint,
                  opacity: isMax ? 1 : 0.65,
                }}
                title={`${d.day}: ${formatMinutes(d.minutes)}`}
              />
              <span className="text-[9px]" style={{ color: "var(--text-dim)" }}>{d.day}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
