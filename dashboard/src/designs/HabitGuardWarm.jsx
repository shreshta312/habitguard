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
      case "Happy": return c.peach;      // Mimosa — cheerful warm
      case "Focused": return c.mint;     // Azul — cool, calm concentration
      case "Immersed": return c.yellow;  // Aperol — intense, worth a check-in
      case "Drained": return "#B7AF9A";
      case "Recovering": return c.mint;
      default: return c.mint;            // Balanced — calm Azul
    }
  }
  switch (mood) {
    case "Happy": return c.yellow;       // Champagne — bright
    case "Focused": return c.mint;       // Whiskey Sour
    case "Immersed": return c.peach;     // Honey Garlic — deep, heavy
    case "Drained": return "#4E483F";
    case "Recovering": return c.mint;
    default: return c.mint;              // Balanced
  }
}

function moodOrbBackground(theme, mood) {
  const core = moodCore(theme, mood);
  const highlight = shade(core, theme === "light" ? 0.42 : 0.28);
  const outer = shade(core, -0.16);
  return `radial-gradient(circle at 32% 28%, ${highlight} 0%, ${core} 55%, ${outer} 100%)`;
}

function frictionAccent(accents, friction) {
  switch (friction) {
    case "Moderate": return accents.peach;
    case "Strong": return accents.yellow;
    default: return accents.mint; // Gentle
  }
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
  const mood = "Balanced";

  const orbBackground = useMemo(() => moodOrbBackground(theme, mood), [theme, mood]);
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
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.06); }
        }
        @keyframes hg-morph {
          0%   { border-radius: 42% 58% 63% 37% / 41% 44% 56% 59%; }
          33%  { border-radius: 63% 37% 45% 55% / 55% 62% 38% 45%; }
          66%  { border-radius: 46% 54% 58% 42% / 60% 40% 60% 40%; }
          100% { border-radius: 42% 58% 63% 37% / 41% 44% 56% 59%; }
        }
        .hg-orb-shape {
          animation: hg-morph 11s ease-in-out infinite;
        }
        .hg-orb-pulse {
          animation: hg-breathe var(--breathe-dur, 6s) ease-in-out infinite;
        }

        @media (prefers-reduced-motion: reduce) {
          .hg-orb-shape, .hg-orb-pulse { animation: none; }
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
          className="hg-orb-pulse flex-shrink-0"
          style={{ "--breathe-dur": `${breatheSpeed}s` }}
        >
          <div
            className="hg-orb-shape"
            style={{
              width: 120,
              height: 120,
              background: orbBackground,
              boxShadow: `0 0 45px ${moodCoreColor}40`,
            }}
          />
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