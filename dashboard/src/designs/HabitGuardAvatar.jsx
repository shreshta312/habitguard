/**
 * HabitGuardDashboard.jsx  (refactored orchestrator)
 *
 * Slim coordinator that:
 *  - Fetches live usage data from the backend
 *  - Derives mood from usage metrics
 *  - Renders the four extracted components:
 *      AvatarDisplay, UsageCharts, MLInsightsPanel, InterventionCard
 *  - Retains header, stat cards, recommended-action, top-domains, and footer
 */
import { useEffect, useMemo, useState } from "react";
import {
  Sun,
  Moon,
  Clock,
  TrendingUp,
  Timer,
  Globe,
  Video,
  MessageCircle,
  Code2,
  Film,
  Activity,
  Play,
} from "lucide-react";
import { fetchUsageSummary } from "../api/usageApi";
import ProfileQuestionnaire from "../components/ProfileQuestionnaire";
import DiagnosticsPanel from "../components/DiagnosticsPanel";
import AvatarDisplay from "../components/AvatarDisplay";
import UsageCharts from "../components/UsageCharts";
import MLInsightsPanel from "../components/MLInsightsPanel";
import InterventionCard from "../components/InterventionCard";
import WeeklyRecapCard from "../components/WeeklyRecapCard";
import CsvExportButton from "../components/CsvExportButton";

// ── Constants ────────────────────────────────────────────────────────────────

const MIND_BITES = [
  "Your thumb has done enough cardio for today.",
  "Almost everything works again if you unplug it for a few minutes, including you.",
  "Notifications act like tiny rewards, which is exactly why they're hard to ignore.",
  "Try one unlock-free hour today.",
  "Less scrolling, more existing.",
];

const GREETING_EMOJIS = [
  "🌼", "☀️", "🌱", "🍃", "🌤️", "🌸", "🌻",
  "🌾", "🌈", "🦋", "🍄", "🌙", "✨",
];

const MOOD_LIST = [
  "Balanced", "Happy", "Focused", "Immersed", "Drained", "Recovering",
];

const MOOD_META = {
  Happy:      { note: "Light usage today — you're mostly off-screen." },
  Balanced:   { note: "Your usage looks steady right now." },
  Focused:    { note: "You seem to be in a focused mode." },
  Immersed:   { note: "Longer usage pattern detected — worth a check-in." },
  Drained:    { note: "Usage has been heavy for a while now." },
  Recovering: { note: "You are moving back toward balance." },
};

const THEME_ACCENTS = {
  light: { mint: "#85431E", peach: "#D39858", yellow: "#34150F" },
  dark:  { mint: "#D39858", peach: "#85431E", yellow: "#EACEAA" },
};

// ── Utility functions ────────────────────────────────────────────────────────

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

function getMoodFromUsage({ screenTimeMinutes, overuseGapMinutes, interventionsToday, isProductive }) {
  if (screenTimeMinutes >= 420 || overuseGapMinutes >= 90) return "Drained";
  if (overuseGapMinutes >= 45) return "Immersed";
  if (interventionsToday >= 3 && overuseGapMinutes > 0) return "Immersed";

  // Stable low usage should look calm, not intense/focused.
  if (screenTimeMinutes <= 180 && overuseGapMinutes <= 0) return "Happy";

  // Productive only becomes Focused when usage is not very low.
  if (isProductive && overuseGapMinutes <= 15) return "Focused";

  return "Balanced";
}

function moodCore(theme, mood) {
  const colors = THEME_ACCENTS[theme];
  if (theme === "light") {
    switch (mood) {
      case "Happy":      return colors.peach;
      case "Focused":    return colors.mint;
      case "Immersed":   return colors.yellow;
      case "Drained":    return "#A88F73";
      case "Recovering": return colors.mint;
      default:           return colors.mint;
    }
  }
  switch (mood) {
    case "Happy":      return colors.yellow;
    case "Focused":    return colors.mint;
    case "Immersed":   return colors.peach;
    case "Drained":    return "#4E483F";
    case "Recovering": return colors.mint;
    default:           return colors.mint;
  }
}

function moodBreatheSpeed(mood) {
  switch (mood) {
    case "Focused":    return 3.2;
    case "Immersed":   return 2.2;
    case "Drained":    return 8;
    case "Happy":      return 4.5;
    case "Recovering": return 5.2;
    default:           return 6;
  }
}

function frictionAccent(accents, frictionType = "") {
  const friction = String(frictionType).toUpperCase();
  if (friction.includes("STRONG")) return accents.yellow;
  if (friction.includes("WARNING") || friction.includes("TIMER")) return accents.peach;
  return accents.mint;
}

function getDomainIcon(domain = "") {
  const value = domain.toLowerCase();
  if (value.includes("youtube")) return Video;
  if (value.includes("instagram") || value.includes("discord") || value.includes("reddit") ||
      value.includes("facebook") || value.includes("twitter") || value.includes("x.com")) return MessageCircle;
  if (value.includes("github") || value.includes("leetcode") || value.includes("stackoverflow") ||
      value.includes("code")) return Code2;
  if (value.includes("netflix") || value.includes("hotstar") || value.includes("primevideo")) return Film;
  return Globe;
}

function formatWeekdayShort(dateKey) {
  if (!dateKey) return "";
  const parsedDate = new Date(dateKey);
  if (Number.isNaN(parsedDate.getTime())) return dateKey;
  return parsedDate.toLocaleDateString(undefined, { weekday: "short" });
}

function getInterventionCount(interventionStats) {
  const counts = interventionStats?.intervention_type_counts || {};
  return Object.values(counts).reduce((total, value) => total + toNumber(value), 0);
}

function toTitleCaseName(name) {
  if (!name) return "there";
  return name.trim().split(" ").filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function getTimeBasedGreeting() {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 21) return "Good evening";
  return "Good night";
}

function getDisplayName() {
  const savedName = localStorage.getItem("habitguard_display_name");
  const envName = import.meta.env.VITE_USER_DISPLAY_NAME;
  return toTitleCaseName(savedName || envName || "there");
}

// ── Small internal components ────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="hg-card flex flex-col gap-2 p-4">
      <div
        className="flex items-center justify-center rounded-full"
        style={{ width: 30, height: 30, background: `${accent}2A`, color: accent }}
      >
        <Icon size={15} />
      </div>
      <p className="text-xs" style={{ color: "var(--text-dim)" }}>{label}</p>
      <p className="hg-mono text-lg font-medium">{value}</p>
    </div>
  );
}

function DomainRow({ item, index, accents }) {
  const Icon = item.icon;
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl px-3 py-2">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
          style={{
            background: `${shade(accents.mint, 0.12 - index * 0.04)}33`,
            color: shade(accents.mint, 0.1 - index * 0.04),
          }}
        >
          <Icon size={15} />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{item.app}</p>
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>{formatMinutes(item.minutes)}</p>
        </div>
      </div>
      <span className="hg-mono text-xs" style={{ color: "var(--text-dim)" }}>#{index + 1}</span>
    </div>
  );
}

// ── Main exported dashboard ──────────────────────────────────────────────────

export default function HabitGuardDashboard() {
  const [theme, setTheme] = useState("light");
  const [dashboardData, setDashboardData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState("");

  const [mindBite] = useState(() => MIND_BITES[Math.floor(Math.random() * MIND_BITES.length)]);
  const [greetingEmoji] = useState(() => GREETING_EMOJIS[Math.floor(Math.random() * GREETING_EMOJIS.length)]);

  const greeting = getTimeBasedGreeting();
  const displayName = getDisplayName();

  useEffect(() => {
    let cancelled = false;

    async function loadLiveUsage() {
      try {
        setIsLoading(true);
        setApiError("");
        const summary = await fetchUsageSummary();
        if (!cancelled) setDashboardData(summary);
      } catch (error) {
        console.error("Failed to fetch HabitGuard usage summary:", error);
        if (!cancelled) {
          setApiError("Could not connect to HabitGuard backend. Start FastAPI and refresh this page.");
          setDashboardData(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadLiveUsage();
    return () => { cancelled = true; };
  }, []);

  const accents = THEME_ACCENTS[theme];
  const raw = dashboardData?.raw || {};
  const dashboardReady = Boolean(dashboardData && raw.dashboard_ready !== false);

  const latestIntervention = dashboardData?.latestIntervention || {};
  const currentSession = dashboardData?.currentSession || null;
  const anomalyData = dashboardData?.anomaly || {};
  const forecastData = dashboardData?.forecast || {};

  const weeklyTrend = useMemo(() => {
    if (!dashboardReady || !dashboardData?.sevenDayTrend?.length) return [];
    return dashboardData.sevenDayTrend.map((item) => ({
      day: formatWeekdayShort(item.date),
      minutes: toNumber(item.minutes),
    }));
  }, [dashboardData, dashboardReady]);

  const domainBreakdown = useMemo(() => {
    if (!dashboardReady || !dashboardData?.topDomainsToday?.length) return [];
    return dashboardData.topDomainsToday.map((item) => ({
      app: item.domain,
      minutes: toNumber(item.minutes),
      icon: getDomainIcon(item.domain),
    }));
  }, [dashboardData, dashboardReady]);

  const totalInterventions = getInterventionCount(dashboardData?.interventionStats);

  const liveUsage = useMemo(() => ({
    screenTimeMinutes: dashboardReady ? dashboardData?.todayTotalMinutes || 0 : 0,
    overuseGapMinutes: latestIntervention?.overuse_gap_minutes || 0,
    interventionsToday: totalInterventions,
    isProductive: dashboardReady ? (dashboardData?.raw?.anomaly?.is_productive === 1) : false,
  }), [dashboardReady, dashboardData, latestIntervention, totalInterventions]);

  const autoMood = useMemo(() => getMoodFromUsage(liveUsage), [liveUsage]);
  const mood = autoMood;
  const moodColor = moodCore(theme, mood);
  const breatheSpeed = moodBreatheSpeed(mood);

  const recommendedTimer = latestIntervention?.recommended_timer_minutes;
  const overuseGap = latestIntervention?.overuse_gap_minutes || 0;
  const topDomain = domainBreakdown[0];

  const currentSessionText = currentSession?.domain
    ? `${currentSession.domain} · ${currentSession.category || "neutral"} · ${currentSession.sessionMinutes || 0} min`
    : "No active session";

  return (
    <div className="hg-root" data-theme={theme}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

        .hg-root {
          --bg: #EACEAA;
          --card: #F8ECDB;
          --card-border: #D9B98C;
          --text: #34150F;
          --text-dim: #7A4A28;
          --shadow: 0 1px 2px rgba(52,21,15,0.08), 0 8px 24px rgba(52,21,15,0.1);
          min-height: 100vh;
          padding: 32px;
          background: var(--bg);
          color: var(--text);
          font-family: 'Inter', sans-serif;
          transition: background 0.4s ease, color 0.4s ease;
        }

        .hg-root[data-theme='dark'] {
          --bg: #150C0C;
          --card: #2E1610;
          --card-border: #4A2A1C;
          --text: #EACEAA;
          --text-dim: #B08A63;
          --shadow: 0 1px 2px rgba(0,0,0,0.35), 0 8px 24px rgba(0,0,0,0.4);
        }

        .hg-display { font-family: 'Fraunces', serif; }
        .hg-mono { font-family: 'IBM Plex Mono', monospace; }

        .hg-card {
          background: var(--card);
          border: 1px solid var(--card-border);
          border-radius: 20px;
          box-shadow: var(--shadow);
          transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease;
        }
        .hg-card:hover {
          transform: translateY(-2px);
          border-color: var(--text-dim);
          box-shadow: 0 4px 6px rgba(0,0,0,0.03), 0 10px 20px rgba(0,0,0,0.08);
        }
        .hg-root[data-theme='dark'] .hg-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.3), 0 16px 32px rgba(0,0,0,0.4);
        }

        .hg-icon-btn {
          background: var(--card);
          border: 1px solid var(--card-border);
          color: var(--text);
          transition: filter 0.15s, transform 0.15s;
        }
        .hg-icon-btn:hover { filter: brightness(0.97); transform: scale(1.05); }
        .hg-root[data-theme='dark'] .hg-icon-btn:hover { filter: brightness(1.15); }

        .hg-btn-primary {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 8px 18px; border-radius: 12px; font-weight: 600; font-size: 0.85rem;
          cursor: pointer; border: none; background: var(--text); color: var(--card);
          transition: opacity 0.15s;
        }
        .hg-btn-primary:hover { opacity: 0.85; }
        .hg-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

        .hg-btn-secondary {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 7px 16px; border-radius: 12px; font-weight: 600; font-size: 0.85rem;
          cursor: pointer; border: 1px solid var(--card-border); background: var(--card);
          color: var(--text); transition: filter 0.15s;
        }
        .hg-btn-secondary:hover { filter: brightness(0.96); }

        .hg-input {
          padding: 8px 12px; border-radius: 10px;
          border: 1px solid var(--card-border); background: var(--bg); color: var(--text);
          font-family: inherit; font-size: 0.85rem; outline: none;
          transition: border-color 0.15s;
        }
        .hg-input:focus { border-color: var(--text-dim); }
        .hg-input::placeholder { color: var(--text-dim); opacity: 0.55; }
      `}</style>

      <div className="mx-auto max-w-6xl">
        {/* ── Header ── */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="hg-display text-2xl font-medium md:text-3xl">
              {greeting}, {displayName} {greetingEmoji}
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text-dim)" }}>
              Your live digital wellbeing dashboard.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <CsvExportButton
              weeklyTrend={weeklyTrend}
              domainBreakdown={domainBreakdown}
              liveUsage={liveUsage}
              latestIntervention={latestIntervention}
              accents={accents}
            />

            <button
              type="button"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              className="hg-icon-btn flex h-10 w-10 items-center justify-center rounded-full transition"
              aria-label="Toggle theme"
            >
              {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
            </button>

            <div
              className="hg-display flex h-10 w-10 items-center justify-center rounded-full text-sm font-medium"
              style={{
                background: `linear-gradient(135deg, ${accents.peach}, ${accents.yellow})`,
                color: theme === "light" ? "#FFF8EF" : "#2E1610",
              }}
            >
              S
            </div>
          </div>
        </header>

        {/* ── Loading / Error / Not-Ready banner ── */}
        {(isLoading || apiError || !dashboardReady) && (
          <section className="hg-card mb-6 p-4 text-sm" style={{ color: "var(--text-dim)" }}>
            {isLoading && "Loading live HabitGuard backend data..."}
            {!isLoading && apiError && apiError}
            {!isLoading && !apiError && !dashboardReady && (
              <>
                No live usage snapshots found yet. Open the Chrome extension,
                browse for a few minutes, then click <strong>Analyze Usage</strong>{" "}
                or <strong>Seed History</strong>.
              </>
            )}
          </section>
        )}

        {/* ── Avatar + Mood ── */}
        <section className="mb-6 flex flex-wrap items-center gap-6">
          <AvatarDisplay
            mood={mood}
            accents={accents}
            bodyColor={moodColor}
            breatheSpeed={breatheSpeed}
          />

          <div>
            <p className="text-xs font-medium uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
              Digital Mood
            </p>
            <h2 className="hg-display mt-1 text-3xl font-medium md:text-4xl">{mood}</h2>
            <p className="mt-2 text-sm" style={{ color: "var(--text-dim)" }}>{MOOD_META[mood].note}</p>
            <p className="mt-3 text-sm italic">"{mindBite}"</p>
          </div>
        </section>

        {/* ── Stat Cards ── */}
        <section className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard icon={Clock} label="Screen Time" value={formatMinutes(liveUsage.screenTimeMinutes)} accent={accents.mint} />
          <StatCard icon={TrendingUp} label="Overuse Gap" value={formatSignedMinutes(overuseGap)} accent={accents.mint} />
          <StatCard icon={Timer} label="Suggested Timer" value={formatMinutes(recommendedTimer, "Not active")} accent={accents.mint} />
          <StatCard icon={Activity} label="Decision Checks" value={String(totalInterventions)} accent={accents.mint} />
        </section>

        {/* ── Charts ── */}
        <UsageCharts
          weeklyTrend={weeklyTrend}
          domainBreakdown={domainBreakdown}
          accents={accents}
          baselineMinutes={toNumber(latestIntervention?.baseline_usage_minutes)}
        />

        {/* ── ML Insights ── */}
        {dashboardReady && (
          <MLInsightsPanel
            anomalyData={anomalyData}
            forecastData={forecastData}
            liveUsage={liveUsage}
            accents={accents}
          />
        )}

        {/* ── Profile Questionnaire ── */}
        <ProfileQuestionnaire
          todayScreenTimeMinutes={liveUsage.screenTimeMinutes}
          accentMint={accents.mint}
          accentPeach={accents.peach}
          accentYellow={accents.yellow}
        />

        {/* ── Recommended Action + Top Domains ── */}
        <section className="mb-6 grid gap-6 md:grid-cols-[1.4fr_0.8fr]">
          <div className="hg-card flex flex-col justify-between gap-6 p-6 md:p-8">
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
                Recommended Action
              </p>
              <p className="max-w-2xl text-base leading-relaxed">
                {!latestIntervention?.usage_status ? (
                  <>
                    No intervention decision yet. Open the Chrome extension and
                    click <strong>Analyze Usage</strong>, or wait for the automatic JITAI check.
                  </>
                ) : overuseGap > 0 ? (
                  <>
                    Your recent usage is{" "}
                    <strong>{formatSignedMinutes(overuseGap)}</strong> above baseline. Keep a{" "}
                    <strong>{formatMinutes(recommendedTimer, "short")}</strong> timer ready
                    {topDomain?.app ? <> for <strong>{topDomain.app}</strong>.</> : "."}
                  </>
                ) : (
                  <>Your usage pattern looks stable right now. No strong intervention is needed.</>
                )}
              </p>

              <div className="hg-mono mt-4 flex flex-wrap items-center gap-3 text-sm" style={{ color: "var(--text-dim)" }}>
                <span>
                  Status: <strong style={{ color: "var(--text)" }}>{latestIntervention?.usage_status || "WAITING"}</strong>
                </span>
                <span>·</span>
                <span>
                  Current: <strong style={{ color: "var(--text)" }}>{currentSessionText}</strong>
                </span>
              </div>
            </div>

            <button
              type="button"
              disabled
              title="Start timers from the Chrome extension popup for now."
              className="flex w-fit cursor-not-allowed items-center gap-2 rounded-full px-6 py-3 text-sm font-medium opacity-70"
              style={{
                background: `linear-gradient(135deg, ${accents.peach}, ${accents.yellow})`,
                color: theme === "light" ? "#FFF8EF" : "#2E1610",
              }}
            >
              <Play size={15} fill="currentColor" />
              Start from Extension
            </button>
          </div>

          <div className="hg-card p-6">
            <h3 className="hg-display mb-4 text-lg font-medium">Top domains today</h3>
            {domainBreakdown.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-dim)" }}>No domain data available yet.</p>
            ) : (
              <div className="space-y-2">
                {domainBreakdown.slice(0, 5).map((item, index) => (
                  <DomainRow key={item.app} item={item} index={index} accents={accents} />
                ))}
              </div>
            )}
          </div>
        </section>

        {/* ── Latest Intervention ── */}
        <InterventionCard
          latestIntervention={latestIntervention}
          overuseGap={overuseGap}
          recommendedTimer={recommendedTimer}
          topDomain={topDomain}
          currentSessionText={currentSessionText}
          accents={accents}
          theme={theme}
        />

        {/* ── Weekly Recap ── */}
        <WeeklyRecapCard weeklyTrend={weeklyTrend} accents={accents} />

        {/* ── Model Diagnostics ── */}
        <DiagnosticsPanel />

        <p className="hg-mono mt-8 text-center text-xs" style={{ color: "var(--text-dim)" }}>
          HabitGuard · JITAI-based intervention · live backend dashboard
        </p>
      </div>
    </div>
  );
}