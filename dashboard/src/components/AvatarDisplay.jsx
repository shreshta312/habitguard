/**
 * AvatarDisplay.jsx
 *
 * Self-contained avatar component with:
 *  - Mood-based SVG face expressions
 *  - CSS idle animations (breathing, blinking)
 *  - Smooth crossfade between mood states
 *  - Reactive micro-animations (flinch on overuse, nod on normal)
 */
import { useEffect, useRef, useState } from "react";

// ── Mood face definitions ────────────────────────────────────────────────────
function MoodFace({ mood, line, skin, accents, bodyColor }) {
  const badgeTint = `${bodyColor}22`;

  return (
    <svg
      viewBox="0 0 160 160"
      width="110"
      height="110"
      role="img"
      aria-label={`Mood avatar: ${mood}`}
      style={{ overflow: "visible" }}
    >
      {/* Background circle */}
      <circle cx="80" cy="80" r="76" fill={badgeTint} />

      {/* Body */}
      <path
        d="M22 152 Q22 101 80 101 Q138 101 138 152 Z"
        fill={bodyColor}
        stroke={line}
        strokeWidth="2.5"
      />

      {/* Head */}
      <circle cx="80" cy="62" r="32" fill={skin} stroke={line} strokeWidth="2.5" />

      {/* Hair — varies by mood */}
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

      {/* Eyelids for blinking — animated via CSS */}
      <rect
        className="hg-blink-lid"
        x="54"
        y="48"
        width="22"
        height="20"
        rx="3"
        fill={skin}
        style={{ transformOrigin: "65px 58px" }}
      />
      <rect
        className="hg-blink-lid"
        x="84"
        y="48"
        width="22"
        height="20"
        rx="3"
        fill={skin}
        style={{ transformOrigin: "95px 58px" }}
      />

      {/* Face expressions per mood */}
      {mood === "Happy" && (
        <>
          <path d="M58 56 Q64 50 70 56" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M90 56 Q96 50 102 56" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M60 68 Q80 86 100 68" stroke={line} strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M24 30 L27 37 L34 39 L27 41 L24 48 L21 41 L14 39 L21 37 Z" fill={accents.peach} className="hg-sparkle" />
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
          <rect x="108" y="78" width="20" height="18" rx="4" fill={skin} stroke={line} strokeWidth="2" />
          <line x1="112" y1="84" x2="124" y2="84" stroke={line} strokeWidth="1.5" />
          <line x1="112" y1="89" x2="121" y2="89" stroke={line} strokeWidth="1.5" />
        </>
      )}

      {mood === "Drained" && (
        <>
          <path d="M56 58 L71 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path d="M89 58 L104 58" stroke={line} strokeWidth="3" strokeLinecap="round" />
          <path d="M66 80 Q80 74 94 80" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <rect x="101" y="26" width="24" height="12" rx="3" fill={skin} stroke={line} strokeWidth="2" />
          <rect x="103.5" y="28.5" width="6" height="7" rx="1" fill="#C1521E" />
        </>
      )}

      {mood === "Recovering" && (
        <>
          <path d="M58 58 Q64 61 70 58" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M90 58 Q96 61 102 58" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M64 74 Q80 84 96 74" stroke={line} strokeWidth="3.2" strokeLinecap="round" fill="none" />
        </>
      )}

      {mood === "Balanced" && (
        <>
          <circle cx="65" cy="61" r="3.5" fill={line} />
          <circle cx="95" cy="61" r="3.5" fill={line} />
          <path d="M64 76 Q80 88 96 76" stroke={line} strokeWidth="3" strokeLinecap="round" fill="none" />
        </>
      )}
    </svg>
  );
}

// ── Main exported component ──────────────────────────────────────────────────
export default function AvatarDisplay({ mood, accents, bodyColor, breatheSpeed }) {
  const line = "#2E1A10";
  const skin = "#F6E4CC";
  const containerRef = useRef(null);
  const [prevMood, setPrevMood] = useState(mood);
  const [transitioning, setTransitioning] = useState(false);
  const [reactionClass, setReactionClass] = useState("");

  // Smooth crossfade when mood changes
  useEffect(() => {
    if (mood !== prevMood) {
      setTransitioning(true);

      // Trigger reactive micro-animation
      if (mood === "Drained" || mood === "Immersed") {
        setReactionClass("hg-avatar-flinch");
      } else if (mood === "Happy" || mood === "Balanced") {
        setReactionClass("hg-avatar-nod");
      } else {
        setReactionClass("");
      }

      const timer = setTimeout(() => {
        setPrevMood(mood);
        setTransitioning(false);
        // Clear reaction class after animation plays
        setTimeout(() => setReactionClass(""), 500);
      }, 300);

      return () => clearTimeout(timer);
    }
  }, [mood, prevMood]);

  return (
    <>
      <style>{`
        /* ── Blink animation ── */
        @keyframes hg-blink {
          0%, 92%, 100% { transform: scaleY(1); }
          95% { transform: scaleY(0.05); }
        }

        .hg-blink-lid {
          animation: hg-blink 4.5s ease-in-out infinite;
          pointer-events: none;
        }

        /* Stagger the second eye slightly */
        .hg-blink-lid:nth-of-type(2) {
          animation-delay: 0.06s;
        }

        /* ── Sparkle twinkle (Happy mood star) ── */
        @keyframes hg-twinkle {
          0%, 100% { opacity: 1; transform: scale(1) rotate(0deg); }
          50% { opacity: 0.5; transform: scale(0.7) rotate(15deg); }
        }

        .hg-sparkle {
          animation: hg-twinkle 2.5s ease-in-out infinite;
          transform-origin: 24px 39px;
        }

        /* ── Breathe (idle float) ── */
        @keyframes hg-breathe {
          0%, 100% { transform: scale(1) translateY(0); }
          50% { transform: scale(1.03) translateY(-3px); }
        }

        .hg-avatar-breathe {
          animation: hg-breathe var(--breathe-duration, 6s) ease-in-out infinite;
        }

        /* ── Reactive: flinch on overuse detection ── */
        @keyframes hg-flinch {
          0% { transform: scale(1); }
          20% { transform: scale(0.92) rotate(-2deg); }
          50% { transform: scale(1.05) rotate(1deg); }
          100% { transform: scale(1); }
        }

        .hg-avatar-flinch {
          animation: hg-flinch 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        }

        /* ── Reactive: nod on normal/happy ── */
        @keyframes hg-nod {
          0% { transform: translateY(0); }
          30% { transform: translateY(-4px); }
          60% { transform: translateY(2px); }
          100% { transform: translateY(0); }
        }

        .hg-avatar-nod {
          animation: hg-nod 0.6s ease-out forwards;
        }

        /* ── Mood crossfade ── */
        .hg-mood-layer {
          transition: opacity 0.35s ease-in-out;
          position: absolute;
          top: 0;
          left: 0;
        }

        /* ── Hover interaction ── */
        .hg-avatar-container:hover .hg-avatar-breathe {
          animation-play-state: paused;
          transform: scale(1.06) rotate(1.5deg);
          transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        @media (prefers-reduced-motion: reduce) {
          .hg-avatar-breathe,
          .hg-blink-lid,
          .hg-sparkle {
            animation: none;
          }
        }
      `}</style>

      <div
        ref={containerRef}
        className={`hg-avatar-container ${reactionClass}`}
        style={{ position: "relative", width: 110, height: 110, flexShrink: 0 }}
      >
        {/* Previous mood — fades out */}
        {transitioning && prevMood !== mood && (
          <div className="hg-mood-layer" style={{ opacity: 0 }}>
            <div className="hg-avatar-breathe" style={{ "--breathe-duration": `${breatheSpeed}s` }}>
              <MoodFace mood={prevMood} line={line} skin={skin} accents={accents} bodyColor={bodyColor} />
            </div>
          </div>
        )}

        {/* Current mood — fades in */}
        <div
          className="hg-mood-layer"
          style={{ opacity: 1, position: transitioning ? "absolute" : "relative" }}
        >
          <div className="hg-avatar-breathe" style={{ "--breathe-duration": `${breatheSpeed}s` }}>
            <MoodFace mood={mood} line={line} skin={skin} accents={accents} bodyColor={bodyColor} />
          </div>
        </div>
      </div>
    </>
  );
}
