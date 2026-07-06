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
} from "recharts";
import { fetchUsageSummary } from "../api/usageApi";

const MIND_BITES = [
  "Your thumb has done enough cardio for today.",
  "Almost everything works again if you unplug it for a few minutes, including you.",
  "Notifications act like tiny rewards, which is exactly why they're hard to ignore.",
  "Try one unlock-free hour today.",
  "Less scrolling, more existing.",
];

const GREETING_EMOJIS = [
  "🌼",
  "☀️",
  "🌱",
  "🍃",
  "🌤️",
  "🌸",
  "🌻",
  "🌾",
  "🌈",
  "🦋",
  "🍄",
  "🌙",
  "✨",
];

const MOOD_LIST = [
  "Balanced",
  "Happy",
  "Focused",
  "Immersed",
  "Drained",
  "Recovering",
];

const MOOD_META = {
  Happy: {
    note: "Light usage today — you're mostly off-screen.",
  },
  Balanced: {
    note: "Your usage looks steady right now.",
  },
  Focused: {
    note: "You seem to be in a focused mode.",
  },
  Immersed: {
    note: "Longer usage pattern detected — worth a check-in.",
  },
  Drained: {
    note: "Usage has been heavy for a while now.",
  },
  Recovering: {
    note: "You are moving back toward balance.",
  },
};

const THEME_ACCENTS = {
  light: {
    mint: "#85431E",
    peach: "#D39858",
    yellow: "#34150F",
  },
  dark: {
    mint: "#D39858",
    peach: "#85431E",
    yellow: "#EACEAA",
  },
};

function toNumber(value, fallback = 0) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : fallback;
}

function formatMinutes(value, emptyLabel = "0 min") {
  if (value === null || value === undefined || value === "") {
    return emptyLabel;
  }

  const minutes = Math.round(toNumber(value));

  if (minutes <= 0) {
    return "0 min";
  }

  if (minutes < 60) {
    return `${minutes} min`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (remainingMinutes === 0) {
    return `${hours}h`;
  }

  return `${hours}h ${remainingMinutes}m`;
}

function formatSignedMinutes(value) {
  const minutes = Math.round(toNumber(value));

  if (minutes <= 0) {
    return "0 min";
  }

  return `+${minutes} min`;
}

function shade(hex, amount) {
  const color = parseInt(hex.slice(1), 16);

  let red = (color >> 16) + Math.round(255 * amount);
  let green = ((color >> 8) & 0xff) + Math.round(255 * amount);
  let blue = (color & 0xff) + Math.round(255 * amount);

  red = Math.max(0, Math.min(255, red));
  green = Math.max(0, Math.min(255, green));
  blue = Math.max(0, Math.min(255, blue));

  return `#${((red << 16) | (green << 8) | blue)
    .toString(16)
    .padStart(6, "0")}`;
}

function getMoodFromUsage({ screenTimeMinutes, overuseGapMinutes, interventionsToday }) {
  if (screenTimeMinutes >= 420 || overuseGapMinutes >= 90) {
    return "Drained";
  }

  if (overuseGapMinutes >= 45 || interventionsToday >= 3) {
    return "Immersed";
  }

  if (screenTimeMinutes <= 180 && overuseGapMinutes <= 0) {
    return "Happy";
  }

  return "Balanced";
}

function moodCore(theme, mood) {
  const colors = THEME_ACCENTS[theme];

  if (theme === "light") {
    switch (mood) {
      case "Happy":
        return colors.peach;
      case "Focused":
        return colors.mint;
      case "Immersed":
        return colors.yellow;
      case "Drained":
        return "#A88F73";
      case "Recovering":
        return colors.mint;
      default:
        return colors.mint;
    }
  }

  switch (mood) {
    case "Happy":
      return colors.yellow;
    case "Focused":
      return colors.mint;
    case "Immersed":
      return colors.peach;
    case "Drained":
      return "#4E483F";
    case "Recovering":
      return colors.mint;
    default:
      return colors.mint;
  }
}

function moodBreatheSpeed(mood) {
  switch (mood) {
    case "Focused":
      return 3.2;
    case "Immersed":
      return 2.2;
    case "Drained":
      return 8;
    case "Happy":
      return 4.5;
    case "Recovering":
      return 5.2;
    default:
      return 6;
  }
}

function frictionAccent(accents, frictionType = "") {
  const friction = String(frictionType).toUpperCase();

  if (friction.includes("STRONG")) {
    return accents.yellow;
  }

  if (friction.includes("WARNING") || friction.includes("TIMER")) {
    return accents.peach;
  }

  return accents.mint;
}

function getDomainIcon(domain = "") {
  const value = domain.toLowerCase();

  if (value.includes("youtube")) return Video;
  if (
    value.includes("instagram") ||
    value.includes("discord") ||
    value.includes("reddit") ||
    value.includes("facebook") ||
    value.includes("twitter") ||
    value.includes("x.com")
  ) {
    return MessageCircle;
  }

  if (
    value.includes("github") ||
    value.includes("leetcode") ||
    value.includes("stackoverflow") ||
    value.includes("code")
  ) {
    return Code2;
  }

  if (
    value.includes("netflix") ||
    value.includes("hotstar") ||
    value.includes("primevideo")
  ) {
    return Film;
  }

  return Globe;
}

function formatWeekdayShort(dateKey) {
  if (!dateKey) return "";

  const parsedDate = new Date(dateKey);

  if (Number.isNaN(parsedDate.getTime())) {
    return dateKey;
  }

  return parsedDate.toLocaleDateString(undefined, {
    weekday: "short",
  });
}

function getInterventionCount(interventionStats) {
  const counts = interventionStats?.intervention_type_counts || {};

  return Object.values(counts).reduce((total, value) => {
    return total + toNumber(value);
  }, 0);
}

function MoodAvatar({ mood, accents, bodyColor }) {
  const line = "#2E1A10";
  const skin = "#F6E4CC";
  const badgeTint = `${bodyColor}22`;

  return (
    <svg
      viewBox="0 0 160 160"
      width="110"
      height="110"
      role="img"
      aria-label={`Mood avatar: ${mood}`}
    >
      <circle cx="80" cy="80" r="76" fill={badgeTint} />

      <path
        d="M22 152 Q22 101 80 101 Q138 101 138 152 Z"
        fill={bodyColor}
        stroke={line}
        strokeWidth="2.5"
      />

      <circle
        cx="80"
        cy="62"
        r="32"
        fill={skin}
        stroke={line}
        strokeWidth="2.5"
      />

      {mood === "Drained" ? (
        <path
          d="M48 52 Q46 20 80 18 Q114 20 112 52 Q108 40 96 56 Q100 34 80 30 Q60 34 64 56 Q52 40 48 52 Z"
          fill={bodyColor}
          stroke={line}
          strokeWidth="2.5"
        />
      ) : mood === "Immersed" ? (
        <path
          d="M48 50 Q44 18 80 16 Q116 18 112 50 Q112 36 100 44 Q104 26 80 24 Q56 26 60 44 Q48 36 48 50 Z"
          fill={bodyColor}
          stroke={line}
          strokeWidth="2.5"
        />
      ) : (
        <path
          d="M48 50 Q46 18 80 16 Q114 18 112 50 Q110 32 80 28 Q50 32 48 50 Z"
          fill={bodyColor}
          stroke={line}
          strokeWidth="2.5"
        />
      )}

      {mood === "Happy" && (
        <>
          <path
            d="M58 56 Q64 50 70 56"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M90 56 Q96 50 102 56"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M60 68 Q80 86 100 68"
            stroke={line}
            strokeWidth="3.5"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M24 30 L27 37 L34 39 L27 41 L24 48 L21 41 L14 39 L21 37 Z"
            fill={accents.peach}
          />
        </>
      )}

      {mood === "Focused" && (
        <>
          <circle cx="64" cy="61" r="8" fill="none" stroke={line} strokeWidth="2.2" />
          <circle cx="96" cy="61" r="8" fill="none" stroke={line} strokeWidth="2.2" />
          <line x1="72" y1="61" x2="88" y2="61" stroke={line} strokeWidth="2.2" />
          <line x1="70" y1="76" x2="90" y2="76" stroke={line} strokeWidth="3" strokeLinecap="round" />
        </>
      )}

      {mood === "Immersed" && (
        <>
          <circle cx="64" cy="59" r="5" fill={line} />
          <circle cx="96" cy="59" r="5" fill={line} />
          <circle cx="80" cy="76" r="3" fill="none" stroke={line} strokeWidth="2.2" />
          <rect
            x="108"
            y="78"
            width="20"
            height="18"
            rx="4"
            fill={skin}
            stroke={line}
            strokeWidth="2"
          />
          <line x1="112" y1="84" x2="124" y2="84" stroke={line} strokeWidth="1.5" />
          <line x1="112" y1="89" x2="121" y2="89" stroke={line} strokeWidth="1.5" />
        </>
      )}

      {mood === "Drained" && (
        <>
          <path d="M56 58 L71 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path d="M89 58 L104 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path
            d="M66 80 Q80 74 94 80"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <rect
            x="101"
            y="26"
            width="24"
            height="12"
            rx="3"
            fill={skin}
            stroke={line}
            strokeWidth="2"
          />
          <rect x="103.5" y="28.5" width="6" height="7" rx="1" fill="#C1521E" />
        </>
      )}

      {mood === "Recovering" && (
        <>
          <path
            d="M58 58 Q64 61 70 58"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M90 58 Q96 61 102 58"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M64 74 Q80 84 96 74"
            stroke={line}
            strokeWidth="3.2"
            strokeLinecap="round"
            fill="none"
          />
        </>
      )}

      {mood === "Balanced" && (
        <>
          <circle cx="65" cy="61" r="3.5" fill={line} />
          <circle cx="95" cy="61" r="3.5" fill={line} />
          <path
            d="M64 76 Q80 88 96 76"
            stroke={line}
            strokeWidth="3"
            strokeLinecap="round"
            fill="none"
          />
        </>
      )}
    </svg>
  );
}

function EmptyState({ children }) {
  return (
    <div
      className="flex h-full min-h-[180px] items-center justify-center rounded-2xl border border-dashed px-4 text-center text-sm"
      style={{
        borderColor: "var(--card-border)",
        color: "var(--text-dim)",
      }}
    >
      {children}
    </div>
  );
}

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="hg-card flex flex-col gap-2 p-4">
      <div
        className="flex items-center justify-center rounded-full"
        style={{
          width: 30,
          height: 30,
          background: `${accent}2A`,
          color: accent,
        }}
      >
        <Icon size={15} />
      </div>

      <p className="text-xs" style={{ color: "var(--text-dim)" }}>
        {label}
      </p>

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
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>
            {formatMinutes(item.minutes)}
          </p>
        </div>
      </div>

      <span className="hg-mono text-xs" style={{ color: "var(--text-dim)" }}>
        #{index + 1}
      </span>
    </div>
  );
}

export default function HabitGuardDashboard() {
  const [theme, setTheme] = useState("light");
  const [dashboardData, setDashboardData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [apiError, setApiError] = useState("");
  const [selectedMood, setSelectedMood] = useState(null);

  const [mindBite] = useState(() => {
    return MIND_BITES[Math.floor(Math.random() * MIND_BITES.length)];
  });

  const [greetingEmoji] = useState(() => {
    return GREETING_EMOJIS[Math.floor(Math.random() * GREETING_EMOJIS.length)];
  });

  useEffect(() => {
    let cancelled = false;

    async function loadLiveUsage() {
      try {
        setIsLoading(true);
        setApiError("");

        const summary = await fetchUsageSummary();

        if (!cancelled) {
          setDashboardData(summary);
        }
      } catch (error) {
        console.error("Failed to fetch HabitGuard usage summary:", error);

        if (!cancelled) {
          setApiError(
            "Could not connect to HabitGuard backend. Start FastAPI and refresh this page."
          );
          setDashboardData(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadLiveUsage();

    return () => {
      cancelled = true;
    };
  }, []);

  const accents = THEME_ACCENTS[theme];
  const raw = dashboardData?.raw || {};
  const dashboardReady = Boolean(dashboardData && raw.dashboard_ready !== false);

  const latestIntervention = dashboardData?.latestIntervention || {};
  const currentSession = dashboardData?.currentSession || null;

  const weeklyTrend = useMemo(() => {
    if (!dashboardReady || !dashboardData?.sevenDayTrend?.length) {
      return [];
    }

    return dashboardData.sevenDayTrend.map((item) => ({
      day: formatWeekdayShort(item.date),
      minutes: toNumber(item.minutes),
    }));
  }, [dashboardData, dashboardReady]);

  const domainBreakdown = useMemo(() => {
    if (!dashboardReady || !dashboardData?.topDomainsToday?.length) {
      return [];
    }

    return dashboardData.topDomainsToday.map((item) => ({
      app: item.domain,
      minutes: toNumber(item.minutes),
      icon: getDomainIcon(item.domain),
    }));
  }, [dashboardData, dashboardReady]);

  const totalInterventions = getInterventionCount(dashboardData?.interventionStats);

  const liveUsage = useMemo(() => {
    return {
      screenTimeMinutes: dashboardReady ? dashboardData?.todayTotalMinutes || 0 : 0,
      overuseGapMinutes: latestIntervention?.overuse_gap_minutes || 0,
      interventionsToday: totalInterventions,
    };
  }, [dashboardReady, dashboardData, latestIntervention, totalInterventions]);

  const autoMood = useMemo(() => {
    return getMoodFromUsage(liveUsage);
  }, [liveUsage]);

  const mood = selectedMood || autoMood;
  const moodColor = moodCore(theme, mood);
  const breatheSpeed = moodBreatheSpeed(mood);

  const recommendedTimer = latestIntervention?.recommended_timer_minutes;
  const overuseGap = latestIntervention?.overuse_gap_minutes || 0;
  const topDomain = domainBreakdown[0];

  const currentSessionText = currentSession?.domain
    ? `${currentSession.domain} · ${currentSession.category || "neutral"} · ${currentSession.sessionMinutes || 0
    } min`
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

        .hg-display {
          font-family: 'Fraunces', serif;
        }

        .hg-mono {
          font-family: 'IBM Plex Mono', monospace;
        }

        .hg-card {
          background: var(--card);
          border: 1px solid var(--card-border);
          border-radius: 20px;
          box-shadow: var(--shadow);
        }

        .hg-icon-btn {
          background: var(--card);
          border: 1px solid var(--card-border);
          color: var(--text);
        }

        .hg-icon-btn:hover {
          filter: brightness(0.97);
        }

        .hg-root[data-theme='dark'] .hg-icon-btn:hover {
          filter: brightness(1.15);
        }

        @keyframes hg-breathe {
          0%, 100% {
            transform: scale(1) translateY(0);
          }

          50% {
            transform: scale(1.03) translateY(-2px);
          }
        }

        .hg-avatar-pulse {
          animation: hg-breathe var(--breathe-duration, 6s) ease-in-out infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .hg-avatar-pulse {
            animation: none;
          }
        }
      `}</style>

      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="hg-display text-2xl font-medium md:text-3xl">
              Good morning, Shreshta {greetingEmoji}
            </h1>

            <p className="mt-1 text-sm" style={{ color: "var(--text-dim)" }}>
              Your live digital wellbeing dashboard.
            </p>
          </div>

          <div className="flex items-center gap-3">
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

        {(isLoading || apiError || !dashboardReady) && (
          <section
            className="hg-card mb-6 p-4 text-sm"
            style={{ color: "var(--text-dim)" }}
          >
            {isLoading && "Loading live HabitGuard backend data..."}

            {!isLoading && apiError && apiError}

            {!isLoading && !apiError && !dashboardReady && (
              <>
                No live usage snapshots found yet. Open the Chrome extension,
                browse for a few minutes, then click <strong>Analyze Usage</strong>{" "}
                or <strong>Seed Demo</strong>.
              </>
            )}
          </section>
        )}

        <section className="mb-6 flex flex-wrap items-center gap-6">
          <div
            className="hg-avatar-pulse shrink-0"
            style={{ "--breathe-duration": `${breatheSpeed}s` }}
          >
            <MoodAvatar mood={mood} accents={accents} bodyColor={moodColor} />
          </div>

          <div>
            <p
              className="text-xs font-medium uppercase tracking-widest"
              style={{ color: "var(--text-dim)" }}
            >
              Digital Mood
            </p>

            <h2 className="hg-display mt-1 text-3xl font-medium md:text-4xl">
              {mood}
            </h2>

            <p className="mt-2 text-sm" style={{ color: "var(--text-dim)" }}>
              {MOOD_META[mood].note}
            </p>

            <p className="mt-3 text-sm italic">“{mindBite}”</p>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSelectedMood(null)}
                className="rounded-full px-3 py-1.5 text-xs font-medium transition"
                style={
                  selectedMood === null
                    ? {
                      background: accents.mint,
                      color: theme === "light" ? "#FFF8EF" : "#2E1610",
                    }
                    : {
                      background: "var(--card)",
                      border: "1px solid var(--card-border)",
                      color: "var(--text-dim)",
                    }
                }
              >
                Auto
              </button>

              {MOOD_LIST.map((item) => (
                <button
                  type="button"
                  key={item}
                  onClick={() => setSelectedMood(item)}
                  className="rounded-full px-3 py-1.5 text-xs font-medium transition"
                  style={
                    selectedMood === item
                      ? {
                        background: accents.mint,
                        color: theme === "light" ? "#FFF8EF" : "#2E1610",
                      }
                      : {
                        background: "var(--card)",
                        border: "1px solid var(--card-border)",
                        color: "var(--text-dim)",
                      }
                  }
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard
            icon={Clock}
            label="Screen Time"
            value={formatMinutes(liveUsage.screenTimeMinutes)}
            accent={accents.mint}
          />

          <StatCard
            icon={TrendingUp}
            label="Overuse Gap"
            value={formatSignedMinutes(overuseGap)}
            accent={accents.mint}
          />

          <StatCard
            icon={Timer}
            label="Suggested Timer"
            value={formatMinutes(recommendedTimer, "Not active")}
            accent={accents.mint}
          />

          <StatCard
            icon={Activity}
            label="Interventions"
            value={String(totalInterventions)}
            accent={accents.mint}
          />
        </section>

        <section className="mb-6 grid gap-6 md:grid-cols-2">
          <div className="hg-card p-6">
            <h3 className="hg-display mb-4 text-lg font-medium">
              Daily usage trend
            </h3>

            <div style={{ width: "100%", height: 240 }}>
              {weeklyTrend.length === 0 ? (
                <EmptyState>
                  No 7-day usage trend yet. Usage will appear after the extension
                  saves snapshots.
                </EmptyState>
              ) : (
                <ResponsiveContainer>
                  <AreaChart
                    data={weeklyTrend}
                    margin={{ top: 5, right: 5, left: -20, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="0%"
                          stopColor={accents.mint}
                          stopOpacity={0.5}
                        />
                        <stop
                          offset="100%"
                          stopColor={accents.mint}
                          stopOpacity={0.02}
                        />
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

                    <Area
                      type="monotone"
                      dataKey="minutes"
                      stroke={accents.mint}
                      strokeWidth={2.5}
                      fill="url(#trendFill)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="hg-card p-6">
            <h3 className="hg-display mb-4 text-lg font-medium">
              Domain usage breakdown
            </h3>

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
                          fill={shade(accents.mint, 0.24 - index * 0.08)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </section>

        <section className="mb-6 grid gap-6 md:grid-cols-[1.4fr_0.8fr]">
          <div className="hg-card flex flex-col justify-between gap-6 p-6 md:p-8">
            <div>
              <p
                className="mb-2 text-xs font-medium uppercase tracking-widest"
                style={{ color: "var(--text-dim)" }}
              >
                Recommended Action
              </p>

              <p className="max-w-2xl text-base leading-relaxed">
                {!latestIntervention?.usage_status ? (
                  <>
                    No intervention decision yet. Open the Chrome extension and
                    click <strong>Analyze Usage</strong>, or wait for the
                    automatic JITAI check.
                  </>
                ) : overuseGap > 0 ? (
                  <>
                    Your recent usage is{" "}
                    <strong>{formatSignedMinutes(overuseGap)}</strong> above
                    baseline. Keep a{" "}
                    <strong>{formatMinutes(recommendedTimer, "short")}</strong>{" "}
                    timer ready
                    {topDomain?.app ? (
                      <>
                        {" "}
                        for <strong>{topDomain.app}</strong>.
                      </>
                    ) : (
                      "."
                    )}
                  </>
                ) : (
                  <>
                    Your usage pattern looks stable right now. No strong
                    intervention is needed.
                  </>
                )}
              </p>

              <div
                className="hg-mono mt-4 flex flex-wrap items-center gap-3 text-sm"
                style={{ color: "var(--text-dim)" }}
              >
                <span>
                  Status:{" "}
                  <strong style={{ color: "var(--text)" }}>
                    {latestIntervention?.usage_status || "WAITING"}
                  </strong>
                </span>

                <span>·</span>

                <span>
                  Current:{" "}
                  <strong style={{ color: "var(--text)" }}>
                    {currentSessionText}
                  </strong>
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
            <h3 className="hg-display mb-4 text-lg font-medium">
              Top domains today
            </h3>

            {domainBreakdown.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--text-dim)" }}>
                No domain data available yet.
              </p>
            ) : (
              <div className="space-y-2">
                {domainBreakdown.slice(0, 5).map((item, index) => (
                  <DomainRow
                    key={item.app}
                    item={item}
                    index={index}
                    accents={accents}
                  />
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="hg-card mb-6 p-6 md:p-8">
          <h3 className="hg-display mb-4 text-lg font-medium">
            Latest intervention
          </h3>

          {!latestIntervention?.usage_status ? (
            <p className="text-sm" style={{ color: "var(--text-dim)" }}>
              No latest intervention yet. This will update after the extension
              sends an intervention result to the backend.
            </p>
          ) : (
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm">
                  <strong>{latestIntervention.usage_status}</strong>
                  {latestIntervention.message ? (
                    <> · {latestIntervention.message}</>
                  ) : null}
                </p>

                {latestIntervention.decision_reason && (
                  <p
                    className="hg-mono mt-2 text-xs leading-relaxed"
                    style={{ color: "var(--text-dim)" }}
                  >
                    {latestIntervention.decision_reason}
                  </p>
                )}

                <div
                  className="mt-3 grid gap-2 text-xs md:grid-cols-3"
                  style={{ color: "var(--text-dim)" }}
                >
                  <span>
                    Baseline:{" "}
                    <strong style={{ color: "var(--text)" }}>
                      {formatMinutes(
                        latestIntervention.baseline_usage_minutes,
                        "Not available"
                      )}
                    </strong>
                  </span>

                  <span>
                    Recent:{" "}
                    <strong style={{ color: "var(--text)" }}>
                      {formatMinutes(
                        latestIntervention.recent_usage_minutes,
                        "Not available"
                      )}
                    </strong>
                  </span>

                  <span>
                    Rho:{" "}
                    <strong style={{ color: "var(--text)" }}>
                      {latestIntervention.rho_user ?? "Not available"}
                    </strong>
                  </span>
                </div>
              </div>

              {latestIntervention.friction_type && (
                <span
                  className="shrink-0 rounded-full px-2.5 py-1 text-xs font-medium"
                  style={{
                    background: `${frictionAccent(
                      accents,
                      latestIntervention.friction_type
                    )}2A`,
                    color: frictionAccent(accents, latestIntervention.friction_type),
                  }}
                >
                  {latestIntervention.friction_type}
                </span>
              )}
            </div>
          )}
        </section>

        <p
          className="hg-mono mt-8 text-center text-xs"
          style={{ color: "var(--text-dim)" }}
        >
          HabitGuard · JITAI-based intervention · live backend dashboard
        </p>
      </div>
    </div>
  );
}