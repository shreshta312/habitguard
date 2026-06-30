const HABITGUARD_OVERLAY_ID = "habitguard-jitai-overlay";

function removeHabitGuardOverlay() {
  const existingOverlay = document.getElementById(HABITGUARD_OVERLAY_ID);

  if (existingOverlay) {
    existingOverlay.remove();
  }
}

function createHabitGuardOverlay(payload) {
  removeHabitGuardOverlay();

  const overlay = document.createElement("div");
  overlay.id = HABITGUARD_OVERLAY_ID;

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

      <div class="habitguard-actions">
        <button id="habitguard-start-break">Take 5-min Break</button>
        <button id="habitguard-dismiss">Dismiss</button>
      </div>

      <p class="habitguard-note">
        This intervention appears because your current session matches a high-risk usage pattern.
      </p>
    </div>
  `;

  const style = document.createElement("style");
  style.textContent = `
    #habitguard-jitai-overlay {
      position: fixed;
      inset: 0;
      z-index: 2147483647;
      background: rgba(15, 23, 42, 0.72);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: Arial, sans-serif;
    }

    #habitguard-jitai-overlay .habitguard-modal {
      width: min(420px, calc(100vw - 32px));
      background: white;
      color: #111827;
      border-radius: 18px;
      padding: 22px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
      text-align: left;
    }

    #habitguard-jitai-overlay .habitguard-badge {
      display: inline-block;
      background: #2563eb;
      color: white;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: bold;
      margin-bottom: 10px;
    }

    #habitguard-jitai-overlay h2 {
      margin: 0 0 10px;
      font-size: 24px;
      color: #111827;
    }

    #habitguard-jitai-overlay .habitguard-main-message {
      font-size: 15px;
      line-height: 1.45;
      color: #374151;
      margin: 0 0 14px;
    }

    #habitguard-jitai-overlay .habitguard-details {
      background: #f3f4f6;
      border-radius: 12px;
      padding: 10px 12px;
      margin-bottom: 14px;
      font-size: 14px;
    }

    #habitguard-jitai-overlay .habitguard-details p {
      margin: 5px 0;
    }

    #habitguard-jitai-overlay .habitguard-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    #habitguard-jitai-overlay button {
      border: none;
      border-radius: 10px;
      padding: 10px;
      font-weight: bold;
      cursor: pointer;
      font-size: 14px;
    }

    #habitguard-start-break {
      background: #2563eb;
      color: white;
    }

    #habitguard-dismiss {
      background: #e5e7eb;
      color: #111827;
    }

    #habitguard-jitai-overlay .habitguard-note {
      margin: 12px 0 0;
      font-size: 12px;
      color: #6b7280;
      line-height: 1.4;
    }
  `;

  overlay.appendChild(style);
  document.body.appendChild(overlay);

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

      removeHabitGuardOverlay();
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
