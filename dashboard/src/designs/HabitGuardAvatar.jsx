import { useState, useMemo } from "react";
import {
  Sun, Moon, Clock, Target, AlertTriangle, TrendingUp, Timer,
  Play, Video, MessageCircle, Code2, Globe, Film,
} from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";

// ---------------------------------------------------------------------------
// Mock data — swap for live API data later. Shapes mirror the FastAPI
// response contract sketched in the blueprint (screen_time, focus_score, etc).
// ---------------------------------------------------------------------------

const WEEKLY_TREND = [
  { day: "Mon", minutes: 195 },
  { day: "Tue", minutes: 240 },
  { day: "Wed", minutes: 180 },
  { day: "Thu", minutes: 260 },
  { day: "Fri", minutes: 310 },
  { day: "Sat", minutes: 340 },
  { day: "Sun", minutes: 260 },
];

const APP_BREAKDOWN = [
  { app: "YouTube", minutes: 95, icon: Video },
  { app: "Instagram", minutes: 80, icon: MessageCircle },
  { app: "VS Code", minutes: 70, icon: Code2 },
  { app: "Chrome", minutes: 60, icon: Globe },
  { app: "Netflix", minutes: 45, icon: Film },
];

const MIND_BITES = [
  "Your thumb has done enough cardio for today.",
  "Almost everything works again if you unplug it for a few minutes, including you. — Anne Lamott",
  "Notifications act like tiny rewards, which is exactly why they're hard to ignore.",
  "Try one unlock-free hour today.",
  "The moon saw your screen time and raised an eyebrow.",
  "Less scrolling, more existing.",
];

const GREETING_EMOJIS = [
  "🌼", "☀️", "🌱", "🍃", "🌤️", "🌸", "🌻", "🌾", "🌈", "🦋", "🍄", "🌙", "✨", "🌊", "🍂",
];


const INTERVENTION_LOG = [
  { app: "YouTube", icon: Video, message: "Crossed usual pattern by 32 min", friction: "Gentle", outcome: "Took the break", time: "Today, 2:14 PM" },
  { app: "Instagram", icon: MessageCircle, message: "15 min continuous scroll detected", friction: "Gentle", outcome: "Snoozed 10 min", time: "Today, 11:02 AM" },
  { app: "Chrome", icon: Globe, message: "Late-night browsing past usual window", friction: "Moderate", outcome: "Session ended", time: "Yesterday, 11:48 PM" },
  { app: "Netflix", icon: Film, message: "3rd episode back-to-back", friction: "Moderate", outcome: "Overridden after 5 min", time: "Yesterday, 9:20 PM" },
  { app: "Instagram", icon: MessageCircle, message: "Opened app 6th time this hour", friction: "Strong", outcome: "Took the break", time: "Yesterday, 4:37 PM" },
  { app: "YouTube", icon: Video, message: "Usage 40% above 7-day average", friction: "Gentle", outcome: "Took the break", time: "2 days ago, 8:05 PM" },
];

const MOOD_META = {
  Happy: { note: "Light usage today — you're mostly off-screen.", weight: 0.9 },
  Balanced: { note: "You're using your screen mindfully today.", weight: 1 },
  Focused: { note: "Deep work detected. Distracting apps are staying quiet.", weight: 1.15 },
  Immersed: { note: "Long continuous session — worth a check-in soon.", weight: 1.35 },
  Drained: { note: "Usage has been heavy for a while now.", weight: 0.6 },
  Recovering: { note: "Better than yesterday. Keep the streak going.", weight: 1.05 },
};

const MOOD_LIST = ["Balanced", "Happy", "Focused", "Immersed", "Drained", "Recovering"];

const THEME_ACCENTS = {
  // Light mode — same "Graphic Alchemy" family as dark mode, roles inverted
  light: { mint: "#85431E", peach: "#D39858", yellow: "#34150F" },
  // Dark mode — Whiskey Sour / Honey Garlic / Champagne
  dark: { mint: "#D39858", peach: "#85431E", yellow: "#EACEAA" },
};

// Lighten/darken a hex color by a fraction (-1 to 1) without crossing into
// muddy in-between hues — used to make the orb read as one lit sphere
// per mood instead of a blend between two unrelated accent colors.
function shade(hex, amt) {
  const num = parseInt(hex.slice(1), 16);
  let r = (num >> 16) + Math.round(255 * amt);
  let g = ((num >> 8) & 0xff) + Math.round(255 * amt);
  let b = (num & 0xff) + Math.round(255 * amt);
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}

function moodCore(theme, mood) {
  const c = THEME_ACCENTS[theme];
  if (theme === "light") {
    switch (mood) {
      case "Happy": return c.peach;       // Whiskey Sour — warmest available
      case "Focused": return c.mint;      // Honey Garlic — steady, serious
      case "Immersed": return c.yellow;   // Burnt Coffee — deep, intense
      case "Drained": return "#A88F73";
      case "Recovering": return c.mint;
      default: return c.mint;             // Balanced
    }
  }
  switch (mood) {
    case "Happy": return c.yellow;        // Champagne — bright
    case "Focused": return c.mint;        // Whiskey Sour
    case "Immersed": return c.peach;      // Honey Garlic — deep, heavy
    case "Drained": return "#4E483F";
    case "Recovering": return c.mint;
    default: return c.mint;               // Balanced
  }
}

function frictionAccent(accents, friction) {
  switch (friction) {
    case "Moderate": return accents.peach;
    case "Strong": return accents.yellow;
    default: return accents.mint; // Gentle
  }
}

// ---------------------------------------------------------------------------
// Illustrated mood avatar — bust-style icon (head + hair + shoulders), in
// the spirit of the flat "person icon" reference: consistent construction,
// dark linework, one accent color for hair/shirt, expression carries the mood.
// ---------------------------------------------------------------------------
function MoodAvatar({ mood, theme, accents, bodyColor }) {
  const line = "#2E1A10";
  const skin = "#F6E4CC";
  const badgeTint = `${bodyColor}22`;
  const lowBattery = "#C1521E";

  return (
    <svg viewBox="0 0 160 160" width="110" height="110" role="img" aria-label={`Mood avatar: ${mood}`}>
      {/* soft circular badge behind the bust, ties into the app's icon-circle language */}
      <circle cx="80" cy="80" r="76" fill={badgeTint} />

      {/* Shoulders / shirt */}
      <path d="M22 152 Q22 100 80 100 Q138 100 138 152 Z" fill={bodyColor} stroke={line} strokeWidth="2.5" />
      <path d="M64 100 Q80 114 96 100" fill="none" stroke={line} strokeWidth="2.5" opacity="0.5" />

      {/* Head */}
      <circle cx="80" cy="62" r="32" fill={skin} stroke={line} strokeWidth="2.5" />

      {/* Hair — shape varies slightly per mood for a bit of life */}
      {mood === "Drained" ? (
        <path d="M48 52 Q46 20 80 18 Q114 20 112 52 Q108 40 96 56 Q100 34 80 30 Q60 34 64 56 Q52 40 48 52 Z" fill={bodyColor} stroke={line} strokeWidth="2.5" />
      ) : mood === "Immersed" ? (
        <path d="M48 50 Q44 18 80 16 Q116 18 112 50 Q112 36 100 44 Q104 26 80 24 Q56 26 60 44 Q48 36 48 50 Z" fill={bodyColor} stroke={line} strokeWidth="2.5" />
      ) : (
        <path d="M48 50 Q46 18 80 16 Q114 18 112 50 Q110 32 80 28 Q50 32 48 50 Z" fill={bodyColor} stroke={line} strokeWidth="2.5" />
      )}

      {/* Face */}
      {mood === "Happy" && (
        <>
          <path d="M58 56 Q64 50 70 56" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M90 56 Q96 50 102 56" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M60 68 Q80 86 100 68" stroke={line} strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M24 30 L27 37 L34 39 L27 41 L24 48 L21 41 L14 39 L21 37 Z" fill={accents.peach} />
          <path d="M126 42 L128 47 L133 49 L128 51 L126 56 L124 51 L119 49 L124 47 Z" fill={accents.peach} opacity="0.85" />
        </>
      )}

      {mood === "Focused" && (
        <>
          <path d="M56 55 Q63 51 71 55" stroke={line} strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M89 55 Q97 51 104 55" stroke={line} strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <circle cx="64" cy="61" r="8" fill="none" stroke={line} strokeWidth="2.2" />
          <circle cx="96" cy="61" r="8" fill="none" stroke={line} strokeWidth="2.2" />
          <line x1="72" y1="61" x2="88" y2="61" stroke={line} strokeWidth="2.2" />
          <line x1="52" y1="59" x2="56" y2="58" stroke={line} strokeWidth="2.2" />
          <line x1="104" y1="59" x2="108" y2="58" stroke={line} strokeWidth="2.2" />
          <line x1="70" y1="76" x2="90" y2="76" stroke={line} strokeWidth="3" strokeLinecap="round" />
        </>
      )}

      {mood === "Immersed" && (
        <>
          <circle cx="64" cy="59" r="5" fill={line} />
          <circle cx="96" cy="59" r="5" fill={line} />
          <circle cx="80" cy="76" r="3" fill="none" stroke={line} strokeWidth="2.2" />
          <g>
            <circle cx="118" cy="86" r="16" fill={accents.yellow} opacity="0.25" />
            <rect x="109" y="78" width="18" height="16" rx="3" fill={skin} stroke={line} strokeWidth="2" />
            <line x1="112" y1="83" x2="124" y2="83" stroke={line} strokeWidth="1.5" opacity="0.5" />
            <line x1="112" y1="88" x2="120" y2="88" stroke={line} strokeWidth="1.5" opacity="0.5" />
          </g>
        </>
      )}

      {mood === "Drained" && (
        <>
          <path d="M56 58 L71 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path d="M89 58 L104 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path d="M58 65 Q64 68 70 65" stroke={line} strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
          <path d="M90 65 Q96 68 102 65" stroke={line} strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
          <path d="M66 80 Q80 74 94 80" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <g>
            <rect x="100" y="26" width="24" height="12" rx="3" fill={skin} stroke={line} strokeWidth="2" />
            <rect x="124" y="30" width="3.5" height="4.5" rx="1" fill={line} />
            <rect x="102.5" y="28.5" width="6" height="7" rx="1" fill={lowBattery} />
          </g>
        </>
      )}

      {mood === "Recovering" && (
        <>
          <path d="M58 58 Q64 61 70 58" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M90 58 Q96 61 102 58" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M64 74 Q80 84 96 74" stroke={line} strokeWidth="3.2" strokeLinecap="round" fill="none" />
          <path d="M118 30 Q124 26 122 20" stroke={line} strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.5" />
          <path d="M128 38 Q136 34 133 26" stroke={line} strokeWidth="2" strokeLinecap="round" fill="none" opacity="0.4" />
        </>
      )}

      {mood === "Balanced" && (
        <>
          <path d="M56 55 Q63 52 71 55" stroke={line} strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M89 55 Q97 52 104 55" stroke={line} strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <circle cx="65" cy="61" r="3.5" fill={line} />
          <circle cx="95" cy="61" r="3.5" fill={line} />
          <path d="M64 76 Q80 88 96 76" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
        </>
      )}
    </svg>
  );
}

function moodBreatheSpeed(mood) {
  switch (mood) {
    case "Focused": return 3.2;
    case "Immersed": return 2.2;
    case "Drained": return 8;
    case "Happy": return 4.5;
    case "Recovering": return 5.2;
    default: return 6; // Balanced
  }
}

export default function HabitGuardDashboard() {
  const [theme, setTheme] = useState("light");
  // Picked once per load, so it's fresh every time the page/artifact refreshes.
  const [mindBite] = useState(() => MIND_BITES[Math.floor(Math.random() * MIND_BITES.length)]);
  const [greetingEmoji] = useState(() => GREETING_EMOJIS[Math.floor(Math.random() * GREETING_EMOJIS.length)]);
  const [mood, setMood] = useState("Balanced");

  const moodCoreColor = useMemo(() => moodCore(theme, mood), [theme, mood]);
  const breatheSpeed = moodBreatheSpeed(mood);
  const accents = THEME_ACCENTS[theme];

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
          font-family: 'Inter', sans-serif;
          background: var(--bg);
          color: var(--text);
          min-height: 100%;
          padding: 32px;
          border-radius: 24px;
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
        }

        .hg-icon-btn {
          background: var(--card);
          border: 1px solid var(--card-border);
          color: var(--text);
        }
        .hg-icon-btn:hover { filter: brightness(0.97); }
        .hg-root[data-theme='dark'] .hg-icon-btn:hover { filter: brightness(1.15); }

        @keyframes hg-breathe {
          0%, 100% { transform: scale(1) translateY(0); }
          50% { transform: scale(1.03) translateY(-2px); }
        }
        .hg-avatar-pulse {
          animation: hg-breathe var(--breathe-dur, 6s) ease-in-out infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .hg-avatar-pulse { animation: none; }
        }
      `}</style>

      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className="hg-display text-2xl md:text-3xl font-medium">
            Good morning, Shreshta {greetingEmoji}
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-dim)" }}>
            Your digital wellbeing summary is ready.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setTheme(theme === "light" ? "dark" : "light")}
            className="hg-icon-btn flex items-center justify-center rounded-full transition"
            style={{ width: 40, height: 40 }}
            aria-label="Toggle theme"
          >
            {theme === "light" ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <div
            className="hg-display flex items-center justify-center rounded-full text-sm font-medium"
            style={{
              width: 40, height: 40,
              background: `linear-gradient(135deg, ${accents.peach}, ${accents.yellow})`,
              color: theme === "light" ? "#FFF8EF" : "#2E1610",
            }}
          >
            S
          </div>
        </div>
      </div>

      {/* Mood avatar — free on the page background, sits right under the name */}
      <div className="flex items-center gap-6 mb-6 flex-wrap">
        <div
          className="hg-avatar-pulse flex-shrink-0"
          style={{ "--breathe-dur": `${breatheSpeed}s` }}
        >
          <MoodAvatar mood={mood} theme={theme} accents={accents} bodyColor={moodCoreColor} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-widest font-medium" style={{ color: "var(--text-dim)" }}>
            Digital Mood
          </p>
          <h2 className="hg-display text-3xl md:text-4xl font-medium mt-1">{mood}</h2>
          <p className="text-sm mt-2" style={{ color: "var(--text-dim)" }}>
            {MOOD_META[mood].note}
          </p>
          <p className="text-sm mt-3 italic" style={{ color: "var(--text)" }}>
            “{mindBite}”
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            {MOOD_LIST.map((m) => (
              <button
                key={m}
                onClick={() => setMood(m)}
                className="text-xs font-medium px-3 py-1.5 rounded-full transition"
                style={
                  m === mood
                    ? { background: accents.mint, color: theme === "light" ? "#FFF8EF" : "#2E1610" }
                    : { background: "var(--card)", border: "1px solid var(--card-border)", color: "var(--text-dim)" }
                }
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <StatCard icon={Clock} label="Screen Time" value="4h 20m" accent={accents.mint} theme={theme} />
        <StatCard icon={Target} label="Focus Score" value="72/100" accent={accents.mint} theme={theme} />
        <StatCard icon={AlertTriangle} label="Risk Level" value="Moderate" accent={accents.mint} theme={theme} />
        <StatCard icon={TrendingUp} label="Overuse Gap" value="+38 min" accent={accents.mint} theme={theme} />
        <StatCard icon={Timer} label="Suggested Timer" value="25 min" accent={accents.mint} theme={theme} />
      </div>

      {/* Charts */}
      <div className="grid md:grid-cols-2 gap-6 mb-6">
        <div className="hg-card p-6">
          <h3 className="hg-display text-lg font-medium mb-4">Daily usage trend</h3>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <AreaChart data={WEEKLY_TREND} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={accents.mint} stopOpacity={0.5} />
                    <stop offset="100%" stopColor={accents.mint} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid vertical={false} stroke="var(--card-border)" />
                <XAxis dataKey="day" tick={{ fontSize: 12, fill: "var(--text-dim)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: "var(--text-dim)" }} axisLine={false} tickLine={false} width={36} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 10, fontSize: 13 }}
                  formatter={(v) => [`${v} min`, "Screen time"]}
                />
                <Area type="monotone" dataKey="minutes" stroke={accents.mint} strokeWidth={2.5} fill="url(#trendFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="hg-card p-6">
          <h3 className="hg-display text-lg font-medium mb-4">App usage breakdown</h3>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={APP_BREAKDOWN} layout="vertical" margin={{ top: 5, right: 20, left: 10, bottom: 0 }}>
                <CartesianGrid horizontal={false} stroke="var(--card-border)" />
                <XAxis type="number" tick={{ fontSize: 12, fill: "var(--text-dim)" }} axisLine={false} tickLine={false} />
                <YAxis dataKey="app" type="category" tick={{ fontSize: 12, fill: "var(--text)" }} axisLine={false} tickLine={false} width={80} />
                <Tooltip
                  contentStyle={{ background: "var(--card)", border: "1px solid var(--card-border)", borderRadius: 10, fontSize: 13 }}
                  formatter={(v) => [`${v} min`, "Usage"]}
                />
                <Bar dataKey="minutes" radius={[0, 8, 8, 0]} barSize={16}>
                  {APP_BREAKDOWN.map((entry, i) => (
                    <Cell key={entry.app} fill={shade(accents.mint, 0.28 - i * 0.14)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Intervention card */}
      <div className="hg-card p-6 md:p-8 mb-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div>
          <p className="text-xs uppercase tracking-widest font-medium mb-2" style={{ color: "var(--text-dim)" }}>
            Recommended Action
          </p>
          <p className="text-base leading-relaxed max-w-lg">
            You've crossed your usual YouTube pattern by <strong>32 minutes</strong>. Take a 10-minute break before continuing.
          </p>
          <div className="flex items-center gap-4 mt-4 text-sm hg-mono" style={{ color: "var(--text-dim)" }}>
            <span>Friction: <strong style={{ color: "var(--text)" }}>Gentle</strong></span>
            <span>·</span>
            <span>Timer: <strong style={{ color: "var(--text)" }}>25 min</strong></span>
          </div>
        </div>
        <button
          className="flex items-center gap-2 rounded-full px-6 py-3 font-medium text-sm flex-shrink-0"
          style={{
            background: `linear-gradient(135deg, ${accents.peach}, ${accents.yellow})`,
            color: theme === "light" ? "#FFF8EF" : "#2E1610",
          }}
        >
          <Play size={15} fill="currentColor" />
          Start Focus Mode
        </button>
      </div>

      {/* Intervention history */}
      <div className="hg-card p-6 md:p-8 mb-6">
        <h3 className="hg-display text-lg font-medium mb-4">Intervention history</h3>
        <div className="flex flex-col">
          {INTERVENTION_LOG.map((entry, i) => {
            const Icon = entry.icon;
            const color = frictionAccent(accents, entry.friction);
            return (
              <div
                key={i}
                className="flex items-center justify-between gap-4 py-3"
                style={{ borderTop: i === 0 ? "none" : "1px solid var(--card-border)" }}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="flex items-center justify-center rounded-full flex-shrink-0"
                    style={{ width: 32, height: 32, background: `${color}2A`, color }}
                  >
                    <Icon size={15} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm truncate">
                      <strong>{entry.app}</strong> · {entry.message}
                    </p>
                    <p className="hg-mono text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                      {entry.time}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span
                    className="text-xs font-medium px-2.5 py-1 rounded-full"
                    style={{ background: `${color}2A`, color }}
                  >
                    {entry.friction}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-dim)" }}>
                    {entry.outcome}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <p className="hg-mono text-center text-xs mt-8" style={{ color: "var(--text-dim)" }}>
        HabitGuard · JITAI-based intervention · mock data
      </p>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, accent, theme }) {
  return (
    <div className="hg-card p-4 flex flex-col gap-2">
      <div
        className="flex items-center justify-center rounded-full"
        style={{
          width: 30, height: 30,
          background: `${accent}2A`,
          color: accent,
        }}
      >
        <Icon size={15} />
      </div>
      <p className="text-xs" style={{ color: "var(--text-dim)" }}>{label}</p>
      <p className="hg-mono text-lg font-medium">{value}</p>
    </div>
  );
}