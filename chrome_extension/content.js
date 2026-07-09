const HABITGUARD_OVERLAY_ID = "habitguard-jitai-overlay";
let habitGuardBreakInterval = null;

function removeHabitGuardOverlay() {
  if (habitGuardBreakInterval) {
    clearInterval(habitGuardBreakInterval);
    habitGuardBreakInterval = null;
  }

  const existingOverlay = document.getElementById(HABITGUARD_OVERLAY_ID);

  if (existingOverlay) {
    existingOverlay.remove();
  }
}

function startHabitGuardBreak(payload = {}, durationMinutes = 5) {
  removeHabitGuardOverlay();

  const overlay = document.createElement("div");
  overlay.id = HABITGUARD_OVERLAY_ID;

  let remainingSeconds = durationMinutes * 60;

  overlay.innerHTML = `
    <div class="habitguard-modal">
      <div class="habitguard-badge">HabitGuard Break</div>

      <h2>Break started</h2>

      <p class="habitguard-main-message">
        Step away from this site for a few minutes. Stretch, drink water, or rest your eyes.
      </p>

      <div class="habitguard-countdown" id="habitguard-break-countdown">
        ${formatHabitGuardTime(remainingSeconds)}
      </div>

      <p class="habitguard-note">
        This break helps interrupt the current high-risk usage pattern.
      </p>

      <div class="habitguard-actions single">
        <button id="habitguard-end-break">End Break Early</button>
      </div>
    </div>
  `;

  const style = document.createElement("style");
  style.textContent = `
    @keyframes habitguard-slide-in {
      from { opacity: 0; transform: translateY(-40px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    @keyframes habitguard-backdrop-in {
      from { opacity: 0; }
      to   { opacity: 1; }
    }

    #habitguard-jitai-overlay {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      background: rgba(52, 21, 15, 0.78);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', Arial, sans-serif;
      animation: habitguard-backdrop-in 0.3s ease;
    }

    #habitguard-jitai-overlay .habitguard-modal {
      width: min(420px, calc(100vw - 32px));
      background: #F8ECDB;
      color: #34150F;
      border: 1.5px solid #D9B98C;
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 60px rgba(52, 21, 15, 0.4);
      text-align: center;
      animation: habitguard-slide-in 0.4s ease;
    }

    #habitguard-jitai-overlay .habitguard-badge {
      display: inline-block;
      background: #34150F;
      color: #F8ECDB;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: bold;
      margin-bottom: 10px;
      letter-spacing: 0.02em;
    }

    #habitguard-jitai-overlay h2 {
      margin: 0 0 10px;
      font-size: 24px;
      color: #34150F;
    }

    #habitguard-jitai-overlay .habitguard-main-message {
      font-size: 15px;
      line-height: 1.45;
      color: #7A4A28;
      margin: 0 0 18px;
    }

    #habitguard-jitai-overlay .habitguard-countdown {
      font-size: 44px;
      font-weight: bold;
      color: #34150F;
      background: #EACEAA;
      border: 1px solid #D9B98C;
      border-radius: 16px;
      padding: 18px;
      margin: 14px 0;
      letter-spacing: 1px;
    }

    #habitguard-jitai-overlay .habitguard-actions.single {
      display: grid;
      grid-template-columns: 1fr;
      margin-top: 14px;
    }

    #habitguard-jitai-overlay button {
      border: none;
      border-radius: 12px;
      padding: 11px;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
      background: #EACEAA;
      color: #34150F;
      border: 1px solid #D9B98C;
      transition: transform 0.15s ease, background 0.15s ease;
    }

    #habitguard-jitai-overlay button:hover {
      background: #D9B98C;
      transform: translateY(-1px);
    }

    #habitguard-jitai-overlay .habitguard-note {
      margin: 14px 0 0;
      font-size: 12px;
      color: #B08A63;
      line-height: 1.4;
    }
  `;

  overlay.appendChild(style);
  document.body.appendChild(overlay);

  const countdownElement = overlay.querySelector("#habitguard-break-countdown");

  habitGuardBreakInterval = setInterval(() => {
    remainingSeconds -= 1;

    if (countdownElement) {
      countdownElement.textContent = formatHabitGuardTime(remainingSeconds);
    }

    if (remainingSeconds <= 0) {
      sendHabitGuardFeedback("break_completed", {
        ...payload,
        decision: "break_completed_by_user",
        reason: "user_completed_intervention_break"
      });

      removeHabitGuardOverlay();
    }
  }, 1000);

  overlay
    .querySelector("#habitguard-end-break")
    .addEventListener("click", () => {
      sendHabitGuardFeedback("break_skipped", {
        ...payload,
        decision: "break_ended_early_by_user",
        reason: "user_ended_break_before_completion"
      });

      removeHabitGuardOverlay();
    });
}

function formatHabitGuardTime(totalSeconds) {
  const safeSeconds = Math.max(0, totalSeconds);
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;

  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function createHabitGuardOverlay(payload) {
  removeHabitGuardOverlay();

  const overlay = document.createElement("div");
  overlay.id = HABITGUARD_OVERLAY_ID;

  const frictionLevel = String(
    payload.frictionLevel ||
    payload.frictionType ||
    payload.friction_type ||
    ""
  ).toUpperCase();

  const isHard =
    frictionLevel.includes("HARD") ||
    frictionLevel.includes("STRONG");

  const hardFrictionHTML = isHard ? `
      <div class="habitguard-hard-friction">
        <label class="habitguard-confirm-label">Type <strong>I want to continue</strong> to dismiss:</label>
        <input type="text" id="habitguard-confirm-input" class="habitguard-confirm-input" placeholder="I want to continue" autocomplete="off" spellcheck="false" />
      </div>
  ` : "";

  overlay.innerHTML = `
    <div class="habitguard-modal">
      <div class="habitguard-badge">HabitGuard</div>

      <h2>Pause for a moment</h2>

      <p class="habitguard-main-message">
        ${payload.message || "Your usage is above your usual pattern."}
      </p>

      <div class="habitguard-details">
        <p><strong>Current site:</strong> ${payload.domain || "this site"}</p>
        <p><strong>Category:</strong> ${payload.category || "temptation"}</p>
        <p><strong>Session:</strong> ${payload.sessionMinutes || 0} min</p>
        <p><strong>Recommended timer:</strong> ${payload.timerMinutes || "Not active"} min</p>
      </div>

      ${hardFrictionHTML}

      <div class="habitguard-actions">
        <button id="habitguard-start-break">Take 5-min Break</button>
        <button id="habitguard-dismiss"${isHard ? " disabled" : ""}>Dismiss</button>
      </div>

      <p class="habitguard-note">
        This intervention appears because your current session matches a high-risk usage pattern.
      </p>
    </div>
  `;

  const style = document.createElement("style");
  style.textContent = `
    @keyframes habitguard-slide-in {
      from { opacity: 0; transform: translateY(-40px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    @keyframes habitguard-backdrop-in {
      from { opacity: 0; }
      to   { opacity: 1; }
    }

    #habitguard-jitai-overlay {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      background: rgba(52, 21, 15, 0.78);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', Arial, sans-serif;
      animation: habitguard-backdrop-in 0.3s ease;
    }

    #habitguard-jitai-overlay .habitguard-modal {
      width: min(420px, calc(100vw - 32px));
      background: #F8ECDB;
      color: #34150F;
      border: 1.5px solid #D9B98C;
      border-radius: 20px;
      padding: 22px;
      box-shadow: 0 20px 60px rgba(52, 21, 15, 0.4);
      text-align: left;
      animation: habitguard-slide-in 0.4s ease;
    }

    #habitguard-jitai-overlay .habitguard-badge {
      display: inline-block;
      background: #34150F;
      color: #F8ECDB;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: bold;
      margin-bottom: 10px;
      letter-spacing: 0.02em;
    }

    #habitguard-jitai-overlay h2 {
      margin: 0 0 10px;
      font-size: 24px;
      color: #34150F;
    }

    #habitguard-jitai-overlay .habitguard-main-message {
      font-size: 15px;
      line-height: 1.45;
      color: #7A4A28;
      margin: 0 0 14px;
    }

    #habitguard-jitai-overlay .habitguard-details {
      background: #EACEAA;
      border: 1px solid #D9B98C;
      border-radius: 14px;
      padding: 10px 14px;
      margin-bottom: 14px;
      font-size: 14px;
      color: #34150F;
    }

    #habitguard-jitai-overlay .habitguard-details p {
      margin: 5px 0;
    }

    #habitguard-jitai-overlay .habitguard-hard-friction {
      margin-bottom: 14px;
    }

    #habitguard-jitai-overlay .habitguard-confirm-label {
      display: block;
      font-size: 13px;
      color: #7A4A28;
      margin-bottom: 6px;
    }

    #habitguard-jitai-overlay .habitguard-confirm-input {
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      border: 1.5px solid #D9B98C;
      border-radius: 10px;
      font-size: 14px;
      background: #EACEAA;
      color: #34150F;
      outline: none;
      transition: border-color 0.2s ease;
    }

    #habitguard-jitai-overlay .habitguard-confirm-input:focus {
      border-color: #7A4A28;
    }

    #habitguard-jitai-overlay .habitguard-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    #habitguard-jitai-overlay button {
      border: none;
      border-radius: 12px;
      padding: 11px;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
      transition: transform 0.15s ease, background 0.15s ease, opacity 0.15s ease;
    }

    #habitguard-start-break {
      background: #34150F;
      color: #F8ECDB;
    }

    #habitguard-start-break:hover {
      background: #4e2219;
      transform: translateY(-1px);
    }

    #habitguard-dismiss {
      background: #EACEAA;
      color: #34150F;
      border: 1px solid #D9B98C;
    }

    #habitguard-dismiss:hover:not(:disabled) {
      background: #D9B98C;
      transform: translateY(-1px);
    }

    #habitguard-dismiss:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    #habitguard-jitai-overlay .habitguard-note {
      margin: 14px 0 0;
      font-size: 12px;
      color: #B08A63;
      line-height: 1.4;
    }
  `;

  overlay.appendChild(style);
  document.body.appendChild(overlay);

  // HARD friction: enable dismiss button only when user types the confirmation phrase
  if (isHard) {
    const confirmInput = overlay.querySelector("#habitguard-confirm-input");
    const dismissBtn   = overlay.querySelector("#habitguard-dismiss");
    if (confirmInput && dismissBtn) {
      confirmInput.addEventListener("input", () => {
        const match = confirmInput.value.trim().toLowerCase() === "i want to continue";
        dismissBtn.disabled = !match;
      });
    }
  }

  overlay
    .querySelector("#habitguard-dismiss")
    .addEventListener("click", () => {
      sendHabitGuardFeedback("overlay_dismissed", {
        ...payload,
        decision: "overlay_dismissed_by_user",
        reason: "user_closed_intervention"
      });

      removeHabitGuardOverlay();
    });

  overlay
    .querySelector("#habitguard-start-break")
    .addEventListener("click", () => {
      sendHabitGuardFeedback("break_accepted", {
        ...payload,
        decision: "break_accepted_by_user",
        reason: "user_accepted_intervention"
      });

      startHabitGuardBreak(payload, 5);
    });
}

function sendHabitGuardFeedback(eventType, payload = {}) {
  try {
    chrome.runtime.sendMessage({
      type: "HABITGUARD_FEEDBACK_EVENT",
      eventType: eventType,
      payload: {
        user_id: "local_user",

        site: payload.domain || window.location.hostname.replace("www.", ""),
        category: payload.category || "unknown",
        overlay_id: payload.overlay_id || HABITGUARD_OVERLAY_ID,

        decision: payload.decision || null,
        reason: payload.reason || null,

        context: {
          page_origin: window.location.origin,
          page_title: document.title,
          session_minutes: payload.sessionMinutes || 0,
          timer_minutes: payload.timerMinutes || null,
          message: payload.message || null,
          original_payload: payload
        }
      }
    });
  } catch (err) {
    console.error("HabitGuard: failed to send feedback event:", err);
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (!message || !message.type) {
    return;
  }

  if (message.type === "SHOW_HABITGUARD_OVERLAY") {
    createHabitGuardOverlay(message.payload || {});
  }

  if (message.type === "REMOVE_HABITGUARD_OVERLAY") {
    removeHabitGuardOverlay();
  }
});
