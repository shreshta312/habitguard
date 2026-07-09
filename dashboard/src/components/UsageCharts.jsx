/**
 * UsageCharts.jsx
 *
 * Contains the two main dashboard charts:
 *  1. Daily usage trend (AreaChart) — with baseline reference line
 *  2. Domain usage breakdown (horizontal BarChart) — with color-coded bars
 */
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";

function shade(hex, amount) {
  const color = parseInt(hex.slice(1), 16);
  let r = (color >> 16) + Math.round(255 * amount);
  let g = ((color >> 8) & 0xff) + Math.round(255 * amount);
  let b = (color & 0xff) + Math.round(255 * amount);
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

function EmptyState({ children }) {
  return (
    <div
      className="flex h-full min-h-[180px] items-center justify-center rounded-2xl border border-dashed px-4 text-center text-sm"
      style={{ borderColor: "var(--card-border)", color: "var(--text-dim)" }}
    >
      {children}
    </div>
  );
}

// Determine bar color: green-ish for under baseline, amber for near, red for over
function barColor(minutes, baseline, accents) {
  if (!baseline || baseline <= 0) return accents.mint;
  const ratio = minutes / baseline;
  if (ratio <= 0.85) return accents.mint;    // under baseline — good
  if (ratio <= 1.1)  return accents.peach;   // near baseline — caution
  return accents.yellow;                      // over baseline — alert
}

export default function UsageCharts({ weeklyTrend, domainBreakdown, accents, baselineMinutes }) {
  const avgMinutes =
    baselineMinutes ||
    (weeklyTrend.length > 0
      ? Math.round(weeklyTrend.reduce((s, d) => s + d.minutes, 0) / weeklyTrend.length)
      : 0);

  return (
    <section className="mb-6 grid gap-6 md:grid-cols-2">
      {/* ── Area Chart: Daily Usage Trend ── */}
      <div className="hg-card p-6">
        <h3 className="hg-display mb-4 text-lg font-medium">Daily usage trend</h3>

        <div style={{ width: "100%", height: 240 }}>
          {weeklyTrend.length === 0 ? (
            <EmptyState>
              No 7-day usage trend yet. Usage will appear after the extension saves snapshots.
            </EmptyState>
          ) : (
            <ResponsiveContainer>
              <AreaChart data={weeklyTrend} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accents.mint} stopOpacity={0.5} />
                    <stop offset="100%" stopColor={accents.mint} stopOpacity={0.02} />
                  </linearGradient>
                </defs>

                <CartesianGrid vertical={false} stroke="var(--card-border)" />

                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 12, fill: "var(--text-dim)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "var(--text-dim)" }}
                  axisLine={false}
                  tickLine={false}
                  width={36}
                />

                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--card-border)",
                    borderRadius: 10,
                    fontSize: 13,
                  }}
                  formatter={(value) => [`${value} min`, "Screen time"]}
                />

                {/* Baseline reference line */}
                {avgMinutes > 0 && (
                  <ReferenceLine
                    y={avgMinutes}
                    stroke={accents.peach}
                    strokeDasharray="6 4"
                    strokeWidth={1.5}
                    label={{
                      value: `Baseline ${avgMinutes}m`,
                      position: "insideTopRight",
                      fontSize: 10,
                      fill: accents.peach,
                    }}
                  />
                )}

                <Area
                  type="monotone"
                  dataKey="minutes"
                  stroke={accents.mint}
                  strokeWidth={2.5}
                  fill="url(#trendFill)"
                  dot={{ fill: accents.mint, r: 3, strokeWidth: 0 }}
                  activeDot={{ r: 5, stroke: accents.mint, strokeWidth: 2, fill: "var(--card)" }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Bar Chart: Domain Usage Breakdown ── */}
      <div className="hg-card p-6">
        <h3 className="hg-display mb-4 text-lg font-medium">Domain usage breakdown</h3>

        <div style={{ width: "100%", height: 240 }}>
          {domainBreakdown.length === 0 ? (
            <EmptyState>
              No domain usage yet. Browse a website with the extension active.
            </EmptyState>
          ) : (
            <ResponsiveContainer>
              <BarChart
                data={domainBreakdown}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 10, bottom: 0 }}
              >
                <CartesianGrid horizontal={false} stroke="var(--card-border)" />

                <XAxis
                  type="number"
                  tick={{ fontSize: 12, fill: "var(--text-dim)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  dataKey="app"
                  type="category"
                  tick={{ fontSize: 12, fill: "var(--text)" }}
                  axisLine={false}
                  tickLine={false}
                  width={90}
                />

                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--card-border)",
                    borderRadius: 10,
                    fontSize: 13,
                  }}
                  formatter={(value) => [`${value} min`, "Usage"]}
                />

                <Bar dataKey="minutes" radius={[0, 8, 8, 0]} barSize={16}>
                  {domainBreakdown.map((entry, index) => (
                    <Cell
                      key={entry.app}
                      fill={barColor(entry.minutes, avgMinutes / domainBreakdown.length, accents)}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </section>
  );
}
