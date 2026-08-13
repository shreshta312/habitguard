/**
 * HabitGuard popup.js
 */

// ── DOM refs ────────────────────────────────────────────────────────────────
const todayUsageEl      = document.getElementById("todayUsage");
const topDomainEl       = document.getElementById("topDomain");
const currentSessionEl  = document.getElementById("currentSession");
const usageStatusEl     = document.getElementById("usageStatus");
const frictionTypeEl    = document.getElementById("frictionType");
const timerEl           = document.getElementById("timer");
const usageDetailsEl    = document.getElementById("usageDetails");
const messageEl         = document.getElementById("message");
const deliveryCardEl    = document.getElementById("deliveryCard");
const deliveryDetailsEl = document.getElementById("deliveryDetails");
const deliveryReasonEl  = document.getElementById("deliveryReason");
const demoBannerEl      = document.getElementById("demoBanner");

const analyzeBtn   = document.getElementById("analyzeBtn");
const seedBtn      = document.getElementById("seedBtn");
const refreshBtn   = document.getElementById("refreshBtn");

const actionStatusEl   = document.getElementById("actionStatus");
const extend5Btn       = document.getElementById("extend5Btn");
const notFinishedBtn   = document.getElementById("notFinishedBtn");
const finishBtn        = document.getElementById("finishBtn");
const stopRemindersBtn = document.getElementById("stopRemindersBtn");

const categoryMessageEl = document.getElementById("categoryMessage");
const productiveBtn     = document.getElementById("productiveBtn");
const mixedBtn          = document.getElementById("mixedBtn");
const temptationBtn     = document.getElementById("temptationBtn");
const neutralBtn        = document.getElementById("neutralBtn");

// ── Intent control refs ──────────────────────────────────────────────────────
const intentPurposeEl  = document.getElementById("intentPurpose");
const intentMinutesEl  = document.getElementById("intentMinutes");
const setIntentBtn     = document.getElementById("setIntentBtn");
const intentStatusEl   = document.getElementById("intentStatus");

const allButtons = [
  analyzeBtn, seedBtn, refreshBtn,
  extend5Btn, notFinishedBtn, finishBtn, stopRemindersBtn,
  productiveBtn, mixedBtn, temptationBtn, neutralBtn,
  setIntentBtn
].filter(Boolean);

// ── Theme toggle refs ────────────────────────────────────────────────────────
const themeToggleBtn  = document.getElementById("themeToggleBtn");
const themeIconSun    = themeToggleBtn ? themeToggleBtn.querySelector(".theme-icon-sun") : null;
const themeIconMoon   = themeToggleBtn ? themeToggleBtn.querySelector(".theme-icon-moon") : null;

// ── Onboarding refs ──────────────────────────────────────────────────────────
const onboardingOverlay = document.getElementById("onboardingOverlay");
const onboardingNextBtn = document.getElementById("onboardingNextBtn");

let currentRecommendedTimerMinutes = null;
let countdownInterval = null;

// Purpose label map: maps backend intent purpose enum to display labels
const PURPOSE_LABELS = {
  "work_study":        "Study (Focus)",
  "necessary":         "Necessary (Focus)",
  "entertainment":     "Entertainment (Temptation)",
  "habitual_browsing": "Browsing (Mixed)",
  "no_timer":          "No Timer (Passive)",
  "unknown":           "Unknown"
};

function getTodayKey(date = new Date()) {
  const year  = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day   = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function setButtonsEnabled(enabled) {
  allButtons.forEach((btn) => { btn.disabled = !enabled; });
}

async function parseApiResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { raw_response: text }; }
}

// Theme management
function applyTheme(theme) {
  if (theme === "dark") {
    document.body.setAttribute("data-theme", "dark");
    if (themeIconSun)  themeIconSun.style.display  = "none";
    if (themeIconMoon) themeIconMoon.style.display = "inline";
  } else {
    document.body.removeAttribute("data-theme");
    if (themeIconSun)  themeIconSun.style.display  = "inline";
    if (themeIconMoon) themeIconMoon.style.display = "none";
  }
}

async function loadThemePreference() {
  const { themePreference } = await chrome.storage.local.get(["themePreference"]);
  applyTheme(themePreference || "light");
}

async function toggleTheme() {
  const isDark = document.body.getAttribute("data-theme") === "dark";
  const newTheme = isDark ? "light" : "dark";
  applyTheme(newTheme);
  await chrome.storage.local.set({ themePreference: newTheme });
}

// Onboarding
let onboardingStep = 1;
const ONBOARDING_TOTAL_STEPS = 3;

function updateOnboardingStep() {
  if (!onboardingOverlay) return;
  onboardingOverlay.querySelectorAll(".onboarding-step").forEach((el) => {
    el.style.display = Number(el.dataset.step) === onboardingStep ? "block" : "none";
  });
  onboardingOverlay.querySelectorAll(".onboarding-dot").forEach((el) => {
    if (Number(el.dataset.dot) === onboardingStep) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });
  if (onboardingNextBtn) {
    onboardingNextBtn.textContent = onboardingStep === ONBOARDING_TOTAL_STEPS ? "Get Started" : "Next";
  }
}

async function handleOnboardingNext() {
  if (onboardingStep < ONBOARDING_TOTAL_STEPS) {
    onboardingStep++;
    updateOnboardingStep();
  } else {
    if (onboardingOverlay) onboardingOverlay.style.display = "none";
    await chrome.storage.local.set({ onboardingComplete: true });
  }
}

async function checkAndShowOnboarding() {
  const { onboardingComplete } = await chrome.storage.local.get(["onboardingComplete"]);
  if (!onboardingComplete && onboardingOverlay) {
    onboardingStep = 1;
    updateOnboardingStep();
    onboardingOverlay.style.display = "flex";
  }
}

// Storage helpers
async function getStoredUsage() {
  const stored = await chrome.storage.local.get([
    "dailyUsageMinutes",
    "domainUsageMinutes",
    "latestIntervention",
    "latestInterventionCheckedAt",
    "activeInterventionTimer",
    "currentSession",
    "sessionHistory",
    "userDomainCategories",
    "demoModeActive",
    "demoRealDataBackup"
  ]);
  return {
    dailyUsageMinutes:           stored.dailyUsageMinutes           || {},
    domainUsageMinutes:          stored.domainUsageMinutes          || {},
    latestIntervention:          stored.latestIntervention          || null,
    latestInterventionCheckedAt: stored.latestInterventionCheckedAt || null,
    activeInterventionTimer:     stored.activeInterventionTimer     || null,
    currentSession:              stored.currentSession              || null,
    sessionHistory:              stored.sessionHistory              || [],
    userDomainCategories:        stored.userDomainCategories        || {},
    demoModeActive:              stored.demoModeActive              || false,
    demoRealDataBackup:          stored.demoRealDataBackup          || null
  };
}

async function isDemoModeActive() {
  const { demoModeActive } = await getStoredUsage();
  return !!demoModeActive;
}

function applyDemoUI(active) {
  if (active) {
    demoBannerEl.style.display = "block";
    seedBtn.textContent = "Exit Demo";
    seedBtn.classList.add("demo-active");
  } else {
    demoBannerEl.style.display = "none";
    seedBtn.textContent = "Enter Demo";
    seedBtn.classList.remove("demo-active");
  }
}

async function getDailyUsageHistory() {
  const { dailyUsageMinutes } = await getStoredUsage();
  const mergedUsage = { ...dailyUsageMinutes };
  try {
    const apiBase = await getApiBaseUrl();
    const response = await fetch(`${apiBase}/usage/daily-history/local_user`);
    if (response.ok) {
      const backendHistory = await parseApiResponse(response);
      const dailyHistory   = backendHistory.daily_usage_history || [];
      dailyHistory.forEach((item) => {
        if (item.date) mergedUsage[item.date] = Number(item.minutes || 0);
      });
    }
  } catch (err) {
    console.warn("Could not load backend usage history. Using local history only.", err);
  }
  return Object.keys(mergedUsage).sort().map((date) => mergedUsage[date]);
}

function getTopDomainForToday(domainUsageMinutes) {
  const todayKey    = getTodayKey();
  const todayDomains = domainUsageMinutes[todayKey] || {};
  const entries     = Object.entries(todayDomains);
  if (entries.length === 0) return "No data";
  entries.sort((a, b) => b[1] - a[1]);
  const [domain, minutes] = entries[0];
  return `${domain} (${minutes} min)`;
}

function renderCurrentSession(currentSession) {
  if (!currentSessionEl) return;
  if (!currentSession) { currentSessionEl.textContent = "No active session."; return; }
  const domain   = currentSession.domain        || "unknown";
  const category = currentSession.category      || "neutral";
  const minutes  = currentSession.episodeFocusedMinutes ?? currentSession.sessionMinutes ?? 0;
  
  const purpose = currentSession.intent?.purpose || currentSession.intentPurpose;
  const plannedMins = currentSession.intent?.effective_planned_minutes ?? currentSession.intent?.original_intended_minutes ?? currentSession.intendedMinutes;

  let purposeLabel = "";
  if (purpose && purpose !== "unknown" && purpose !== "no_timer") {
    const label = PURPOSE_LABELS[purpose] || purpose;
    const minPart = (plannedMins !== null && plannedMins !== undefined) ? ` (${plannedMins} min)` : "";
    purposeLabel = ` | intent: ${label}${minPart}`;
  }
  currentSessionEl.textContent = `${domain} | ${category} | ${minutes} min${purposeLabel}`;
}

function formatCheckedTime(timestamp) {
  if (!timestamp) return "No automatic check yet.";
  return `Last automatic JITAI check: ${new Date(timestamp).toLocaleTimeString()}`;
}

/**
 * Authoritative session reconciliation request to background worker.
 */
async function requestActiveSessionReconciliation() {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "RECONCILE_ACTIVE_SESSION" }, (response) => {
      if (response && response.session) {
        resolve(response.session);
      } else {
        resolve(null);
      }
    });
  });
}

async function refreshUsageDisplay(showMessage = false) {
  const reconciledSession = await requestActiveSessionReconciliation();
  const { dailyUsageMinutes, domainUsageMinutes } = await getStoredUsage();
  const todayKey    = getTodayKey();
  const todayUsage  = dailyUsageMinutes[todayKey] || 0;
  const topDomain   = getTopDomainForToday(domainUsageMinutes);

  todayUsageEl.textContent = `${todayUsage} min`;
  topDomainEl.textContent  = topDomain;
  renderCurrentSession(reconciledSession);

  if (showMessage) {
    messageEl.textContent = "Active session reconciled & usage display refreshed.";
  }
}

// Result rendering with strict separation of session status vs optimization status
function renderResult(data, checkedAt = null) {
  if (data.error) {
    currentRecommendedTimerMinutes = null;
    usageStatusEl.textContent  = "ERROR";
    frictionTypeEl.textContent = "-";
    timerEl.textContent        = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent      = data.error;
    return;
  }

  if (data.mode === "CALIBRATION" || data.usage_status === "INSUFFICIENT_DATA") {
    currentRecommendedTimerMinutes = null;
    usageStatusEl.textContent  = "CALIBRATING";
    frictionTypeEl.textContent = "Not active";
    timerEl.textContent        = "Not active";
    usageDetailsEl.textContent = "Baseline still being collected.";
    messageEl.textContent = `${data.message || "HabitGuard is still collecting baseline data."} ${formatCheckedTime(checkedAt)}`;
    return;
  }

  const sessionStatus = data.session_status || "UNKNOWN";
  if (sessionStatus === "OVER_PLAN") {
    usageStatusEl.textContent = "OVER PLAN";
  } else if (sessionStatus === "NO_PLAN") {
    usageStatusEl.textContent = "NO PLAN";
  } else {
    usageStatusEl.textContent = sessionStatus;
  }

  if (frictionTypeEl) frictionTypeEl.textContent = data.friction_type || "NONE";

  const recRemaining = data.recommended_remaining ?? data.recommended_remaining_minutes ?? data.recommended_timer_minutes;

  if (sessionStatus === "NO_PLAN" || recRemaining === null || recRemaining === undefined) {
    currentRecommendedTimerMinutes = null;
    timerEl.textContent = "Not active";
  } else {
    currentRecommendedTimerMinutes = Number(recRemaining);
    timerEl.textContent = `${currentRecommendedTimerMinutes} min`;
  }

  const used = data.used_minutes ?? data.focused_minutes ?? data.recent_usage_minutes ?? 0;
  const planned = data.planned_minutes;
  const planStr = (planned !== null && planned !== undefined) ? `${planned} min` : "No plan";
  const remStr = (sessionStatus !== "NO_PLAN" && recRemaining !== null && recRemaining !== undefined) ? `${recRemaining} min` : "Not active";
  const overuse = (sessionStatus !== "NO_PLAN" && data.overuse_gap_minutes !== null && data.overuse_gap_minutes !== undefined) ? data.overuse_gap_minutes : 0;

  usageDetailsEl.textContent = `Used: ${used} min | Planned: ${planStr} | Remaining: ${remStr} | Over: ${overuse} min`;

  // Section 5 Button Visibility Rules
  if (sessionStatus === "NO_PLAN") {
    if (extend5Btn) extend5Btn.style.display = "none";
    if (notFinishedBtn) notFinishedBtn.style.display = "none";
  } else {
    if (extend5Btn) extend5Btn.style.display = "inline-block";
    if (notFinishedBtn) notFinishedBtn.style.display = "inline-block";
  }

  if (data.should_notify !== undefined || data.should_overlay !== undefined || data.delivery_status) {
    let notifyLabel = "🔕 Notify: No";
    if (data.delivery_status === "API_ACCEPTED") {
      notifyLabel = "🔔 Notification sent";
    } else if (data.delivery_status === "PERMISSION_DENIED") {
      notifyLabel = "🚫 Notifications disabled in Chrome";
    } else if (data.delivery_status === "FAILED") {
      notifyLabel = "⚠️ Notification failed";
    } else if (data.suppression_reason === "cooldown_active" || data.delivery_status === "SUPPRESSED") {
      notifyLabel = "⏳ Reminder recently sent";
    } else if (data.should_notify) {
      notifyLabel = "⌛ Notification pending";
    }

    const overlayLabel  = data.should_overlay  ? " | 📋 Overlay: Yes" : " | 📋 Overlay: No";
    const cooldownLabel = data.cooldown_minutes !== undefined ? ` | ⏳ Cooldown: ${data.cooldown_minutes} min` : "";
    deliveryDetailsEl.textContent = `${notifyLabel}${overlayLabel}${cooldownLabel}`;
    deliveryReasonEl.textContent  = data.failure_reason || data.delivery_reason || "";
    deliveryCardEl.style.display  = "block";
  } else {
    deliveryCardEl.style.display = "none";
  }

  let finalMessage = data.message || "Analysis complete.";
  if (sessionStatus === "NO_PLAN") {
    finalMessage = "No plan set. Active usage is being tracked.";
  } else if (sessionStatus === "OVER_PLAN") {
    if (data.should_intervene === false && data.suppression_reason) {
      finalMessage = `Over plan by ${overuse} min (Intervention suppressed: ${data.suppression_reason}).`;
    } else {
      finalMessage = `Over plan by ${overuse} min.`;
    }
  }

  messageEl.textContent = `${finalMessage} ${formatCheckedTime(checkedAt)}`;

  const epMins = data.episode_focused_minutes ?? data.focused_minutes ?? data.used_minutes;
  if (epMins !== undefined && typeof chrome !== "undefined" && chrome.storage?.local) {
    chrome.storage.local.get(["currentSession"], (stored) => {
      if (stored && stored.currentSession) {
        const updatedSess = { ...stored.currentSession, episodeFocusedMinutes: epMins };
        chrome.storage.local.set({ currentSession: updatedSess });
        renderCurrentSession(updatedSess);
      }
    });
  }
}

async function loadLatestIntervention() {
  const { latestIntervention, latestInterventionCheckedAt } = await getStoredUsage();
  if (!latestIntervention) {
    usageStatusEl.textContent  = "Waiting...";
    frictionTypeEl.textContent = "Waiting...";
    timerEl.textContent        = "Waiting...";
    usageDetailsEl.textContent = "Waiting for analysis...";
    messageEl.textContent      = "No automatic JITAI result yet. Click Analyze Usage or wait for background check.";
    return;
  }
  renderResult(latestIntervention, latestInterventionCheckedAt);
}

async function sendUsageSnapshotFromPopup(latestIntervention = null, options = {}) {
  const { source = "chrome_extension_popup" } = options;
  try {
    const todayKey = getTodayKey();
    const stored   = await getStoredUsage();
    const apiBase  = await getApiBaseUrl();
    const body = {
      user_id: "local_user",
      date: todayKey,
      daily_usage_minutes:     stored.dailyUsageMinutes    || {},
      domain_usage_minutes:    stored.domainUsageMinutes   || {},
      current_session:         stored.currentSession       || null,
      session_history:         stored.sessionHistory       || [],
      latest_intervention:     latestIntervention || stored.latestIntervention || null,
      active_intervention_timer: stored.activeInterventionTimer || null,
      source
    };
    const response = await fetch(`${apiBase}/usage/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await parseApiResponse(response);
    await chrome.storage.local.set({ lastPopupUsageSnapshotAt: Date.now(), lastPopupUsageSnapshotResult: data });
    return { success: response.ok, data };
  } catch (err) {
    console.error("HabitGuard popup usage snapshot failed:", err);
    return { success: false, error: err.message };
  }
}

/**
 * Core analysis function:
 * Reconciles active session first, sends canonical activity batch, validates response, renders result.
 */
async function analyzeUsage() {
  setButtonsEnabled(false);
  usageStatusEl.textContent  = "Analyzing…";
  frictionTypeEl.textContent = "…";
  timerEl.textContent        = "…";
  usageDetailsEl.textContent = "Reconciling active session…";
  messageEl.textContent      = "Contacting HabitGuard optimization backend…";

  try {
    const currentSess = await requestActiveSessionReconciliation();
    const apiBase = await getApiBaseUrl();
    let data = null;

    if (currentSess && currentSess.session_id) {
      console.log("[HabitGuard] Analyze: sending batch for session", currentSess.session_id);
      let canonicalResponse;
      try {
        canonicalResponse = await fetch(`${apiBase}/sessions/${currentSess.session_id}/activity/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ activities: [] })
        });
      } catch (netErr) {
        throw new Error(`Network error reaching ${apiBase}: ${netErr.message}`);
      }

      if (canonicalResponse.ok) {
        data = await parseApiResponse(canonicalResponse);
        // Identity check: verify response session_id and domain match reconciled active session
        if (data.session_id && data.session_id !== currentSess.session_id || (data.domain && data.domain !== currentSess.domain)) {
          console.warn("[HabitGuard] STALE_SESSION_RESPONSE detected: response does not match active session identity", { responseSession: data.session_id, activeSession: currentSess.session_id });
          await chrome.storage.local.remove(["currentSession"]);
          const freshSession = await requestActiveSessionReconciliation();
          if (freshSession && freshSession.session_id) {
            const retryRes = await fetch(`${apiBase}/sessions/${freshSession.session_id}/activity/batch`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ activities: [] })
            });
            if (retryRes.ok) {
              data = await parseApiResponse(retryRes);
            } else {
              throw new Error("STALE_SESSION_RESPONSE: active session identity mismatch after reconciliation retry.");
            }
          } else {
            throw new Error("STALE_SESSION_RESPONSE: unable to reconcile fresh active session.");
          }
        }
      } else if (canonicalResponse.status === 404) {
        console.warn("[HabitGuard] Session 404 on backend — reconciling and starting new session");
        await chrome.storage.local.remove(["currentSession"]);
        const freshSession = await requestActiveSessionReconciliation();
        if (freshSession && freshSession.session_id) {
          const retryRes = await fetch(`${apiBase}/sessions/${freshSession.session_id}/activity/batch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ activities: [] })
          });
          if (retryRes.ok) data = await parseApiResponse(retryRes);
        }
      } else {
        const errBody = await parseApiResponse(canonicalResponse);
        const detail  = errBody.detail || JSON.stringify(errBody);
        throw new Error(`Backend error ${canonicalResponse.status}: ${detail}`);
      }
    }

    if (!data) {
      usageStatusEl.textContent  = "NO ACTIVE SITE";
      frictionTypeEl.textContent = "Not active";
      timerEl.textContent        = "Not active";
      usageDetailsEl.textContent = "Browse to a website to begin tracking.";
      messageEl.textContent      = "No active session on this tab. Chrome internal pages (like chrome://) cannot be tracked.";
      return;
    }

    const checkedAt = Date.now();
    await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "HANDLE_CANONICAL_RESPONSE", data }, (res) => resolve(res));
    });
    const latestIntervention = (await chrome.storage.local.get(["latestIntervention"])).latestIntervention || data;
    await sendUsageSnapshotFromPopup(latestIntervention, { source: "chrome_extension_popup_analysis" });
    renderResult(latestIntervention, checkedAt);
    await refreshUsageDisplay();

  } catch (err) {
    console.error("[HabitGuard] analyzeUsage failed:", err);
    usageStatusEl.textContent  = "ERROR";
    frictionTypeEl.textContent = "—";
    timerEl.textContent        = "—";
    usageDetailsEl.textContent = "—";
    messageEl.textContent      = err.message.includes("Network error")
      ? "Cannot reach backend. Is FastAPI backend running on port 8000?"
      : `Analysis error: ${err.message}`;
  } finally {
    setButtonsEnabled(true);
  }
}

// Actions
async function sendCanonicalAction(actionName, payload = {}) {
  const currentSession = await requestActiveSessionReconciliation();
  if (!currentSession || !currentSession.session_id) {
    if (actionStatusEl) actionStatusEl.textContent = "No active session found.";
    return;
  }
  const sessionId = currentSession.session_id;
  const apiBase = await getApiBaseUrl();

  try {
    setButtonsEnabled(false);
    if (actionStatusEl) actionStatusEl.textContent = `Sending ${actionName}...`;
    const response = await fetch(`${apiBase}/sessions/${sessionId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: actionName,
        ...payload
      })
    });
    if (response.ok) {
      if (actionStatusEl) actionStatusEl.textContent = `✓ Action recorded: ${actionName}`;
      await analyzeUsage();
    } else {
      if (actionStatusEl) actionStatusEl.textContent = `Error ${response.status} recording action.`;
    }
  } catch (err) {
    console.error("Action request failed:", err);
    if (actionStatusEl) actionStatusEl.textContent = "Network error recording action.";
  } finally {
    setButtonsEnabled(true);
  }
}

function formatRemainingTime(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

async function saveActiveTimer(type, durationMinutes) {
  const endAt = Date.now() + durationMinutes * 60 * 1000;
  await chrome.storage.local.set({ activeInterventionTimer: { type, durationMinutes, endAt } });
  await sendUsageSnapshotFromPopup(null, { source: "chrome_extension_timer_started" });
  startCountdown(endAt, type);
}

function startCountdown(endAt, type) {
  if (countdownInterval) clearInterval(countdownInterval);

  function updateCountdown() {
    const remaining = endAt - Date.now();
    if (remaining <= 0) {
      clearInterval(countdownInterval);
      countdownInterval = null;
      actionStatusEl.textContent = type === "break"
        ? "Break complete. You can return mindfully."
        : "Timer complete. Consider stopping or taking a short break.";
      chrome.storage.local.remove(["activeInterventionTimer"]).then(() =>
        sendUsageSnapshotFromPopup(null, { source: "chrome_extension_timer_cleared" })
      );
      return;
    }
    const label = type === "break" ? "Break time left" : "Timer time left";
    actionStatusEl.textContent = `${label}: ${formatRemainingTime(remaining)}`;
  }
  updateCountdown();
  countdownInterval = setInterval(updateCountdown, 1000);
}

async function loadActiveTimer() {
  const stored      = await chrome.storage.local.get(["activeInterventionTimer"]);
  const activeTimer = stored.activeInterventionTimer;
  if (!activeTimer) { actionStatusEl.textContent = "No active timer."; return; }
  if (activeTimer.endAt <= Date.now()) {
    await chrome.storage.local.remove(["activeInterventionTimer"]);
    await sendUsageSnapshotFromPopup(null, { source: "chrome_extension_timer_cleared" });
    actionStatusEl.textContent = "No active timer.";
    return;
  }
  startCountdown(activeTimer.endAt, activeTimer.type);
}

// Session Intent Validation
async function setSessionIntent() {
  const currentSession = await requestActiveSessionReconciliation();

  if (!currentSession || !currentSession.session_id) {
    if (intentStatusEl) intentStatusEl.textContent = "No active session. Browse a website first.";
    return;
  }

  const rawPurpose = intentPurposeEl ? intentPurposeEl.value : "";
  const isNoTimer  = rawPurpose === "no_timer";
  const purpose    = (rawPurpose === "" || rawPurpose === "no_timer") ? "unknown" : rawPurpose;

  const rawMinutes = intentMinutesEl ? intentMinutesEl.value.trim() : "";

  let intendedMinutes = null;
  let timerMode = "no_timer";

  if (isNoTimer) {
    intendedMinutes = null;
    timerMode = "no_timer";
  } else {
    if (rawMinutes === "" || rawMinutes === null) {
      if (intentStatusEl) intentStatusEl.textContent = "Enter intended minutes (1–480).";
      return;
    }
    const parsed = Number(rawMinutes);
    if (!Number.isFinite(parsed) || parsed < 1 || parsed > 480 || !Number.isInteger(parsed)) {
      if (intentStatusEl) intentStatusEl.textContent = "Enter a whole number between 1 and 480.";
      return;
    }
    intendedMinutes = parsed;
    timerMode = "planned";
  }

  try {
    if (setIntentBtn) setIntentBtn.disabled = true;
    const apiBase = await getApiBaseUrl();
    const response = await fetch(
      `${apiBase}/sessions/${currentSession.session_id}/intent`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          purpose,
          intended_minutes: intendedMinutes,
          timer_mode: timerMode
        })
      }
    );

    if (response.ok) {
      await parseApiResponse(response);
      const updatedSession = {
        ...currentSession,
        intentPurpose: rawPurpose,
        intendedMinutes
      };
      await chrome.storage.local.set({ currentSession: updatedSession });
      renderCurrentSession(updatedSession);
      const purposeLabel = PURPOSE_LABELS[rawPurpose] || rawPurpose || "Unknown";
      const label = intendedMinutes ? `${purposeLabel}, ${intendedMinutes} min` : purposeLabel;
      if (intentStatusEl) intentStatusEl.textContent = `✓ Intent set: ${label}`;
      if (intentMinutesEl) intentMinutesEl.value = "";
    } else {
      if (intentStatusEl) intentStatusEl.textContent = `Backend error ${response.status}. Is backend running?`;
    }
  } catch (err) {
    console.error("HabitGuard set intent failed:", err);
    if (intentStatusEl) intentStatusEl.textContent = "Could not reach backend. Intent stored locally.";
    const updatedSession = {
      ...currentSession,
      intentPurpose: rawPurpose,
      intendedMinutes
    };
    await chrome.storage.local.set({ currentSession: updatedSession });
    renderCurrentSession(updatedSession);
  } finally {
    if (setIntentBtn) setIntentBtn.disabled = false;
  }
}

// Site category
async function setCurrentDomainCategory(category) {
  const currentSession = await requestActiveSessionReconciliation();
  if (!currentSession || !currentSession.domain) {
    categoryMessageEl.textContent = "No active site detected. Browse a website first.";
    return;
  }
  const stored            = await getStoredUsage();
  const domain            = currentSession.domain;
  const updatedCategories = { ...stored.userDomainCategories, [domain]: category };
  const updatedSession    = { ...currentSession, category };
  await chrome.storage.local.set({ userDomainCategories: updatedCategories, currentSession: updatedSession });
  await sendUsageSnapshotFromPopup(null, { source: "chrome_extension_category_updated" });
  renderCurrentSession(updatedSession);
  categoryMessageEl.textContent = `${domain} is now marked as ${category}. HabitGuard will remember this.`;
}

// Refresh
async function handleRefresh() {
  const inDemo = await isDemoModeActive();
  if (inDemo) {
    const { demoRealDataBackup } = await getStoredUsage();
    if (demoRealDataBackup) {
      await chrome.storage.local.set({
        dailyUsageMinutes:           demoRealDataBackup.dailyUsageMinutes  || {},
        domainUsageMinutes:          demoRealDataBackup.domainUsageMinutes || {},
        latestIntervention:          demoRealDataBackup.latestIntervention || null,
        latestInterventionCheckedAt: demoRealDataBackup.latestInterventionCheckedAt || null
      });
    }
    await chrome.storage.local.remove(["demoModeActive", "demoRealDataBackup"]);
    applyDemoUI(false);
  }
  await refreshUsageDisplay(true);
  await loadLatestIntervention();
}

async function initializePopup() {
  await logRuntimeDiagnostics("Popup Initialized");
  await loadThemePreference();
  const inDemo = await isDemoModeActive();
  applyDemoUI(inDemo);
  await refreshUsageDisplay();
  await loadLatestIntervention();
  await loadActiveTimer();
  await checkAndShowOnboarding();
}

// Event listeners
analyzeBtn.addEventListener("click",  analyzeUsage);
seedBtn.addEventListener("click",     async () => {
  const inDemo = await isDemoModeActive();
  if (inDemo) {
    await handleRefresh();
  } else {
    // Enter demo mode
    const stored = await getStoredUsage();
    await chrome.storage.local.set({
      demoRealDataBackup: {
        dailyUsageMinutes:  stored.dailyUsageMinutes,
        domainUsageMinutes: stored.domainUsageMinutes,
        latestIntervention: stored.latestIntervention,
        latestInterventionCheckedAt: stored.latestInterventionCheckedAt
      }
    });
    const demoUsage = {};
    const demoDomainUsage = {};
    for (let i = 10; i >= 1; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const key = getTodayKey(d);
      demoUsage[key] = 30 + Math.round(Math.sin(i) * 12);
      demoDomainUsage[key] = { "youtube.com": 15, "instagram.com": 10, "leetcode.com": 5 };
    }
    const todayKey = getTodayKey();
    demoUsage[todayKey] = 75;
    demoDomainUsage[todayKey] = { "youtube.com": 45, "instagram.com": 20, "twitter.com": 10 };

    await chrome.storage.local.set({ dailyUsageMinutes: demoUsage, domainUsageMinutes: demoDomainUsage, demoModeActive: true });
    applyDemoUI(true);
    await refreshUsageDisplay();
    await analyzeUsage();
  }
});
refreshBtn.addEventListener("click",  handleRefresh);

if (extend5Btn)       extend5Btn.addEventListener("click",       () => sendCanonicalAction("extend_5"));
if (notFinishedBtn)   notFinishedBtn.addEventListener("click",   () => sendCanonicalAction("task_not_finished", { task_completion: "not_completed", time_sufficient: "insufficient" }));
if (finishBtn)        finishBtn.addEventListener("click",        () => sendCanonicalAction("finish", { task_completion: "unknown", time_sufficient: "unknown" }));
if (stopRemindersBtn) stopRemindersBtn.addEventListener("click", () => sendCanonicalAction("stop_reminders"));

productiveBtn.addEventListener("click",  () => setCurrentDomainCategory("productive"));
mixedBtn.addEventListener("click",       () => setCurrentDomainCategory("mixed"));
temptationBtn.addEventListener("click",  () => setCurrentDomainCategory("temptation"));
neutralBtn.addEventListener("click",     () => setCurrentDomainCategory("neutral"));

if (setIntentBtn) setIntentBtn.addEventListener("click", setSessionIntent);
if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);
if (onboardingNextBtn) onboardingNextBtn.addEventListener("click", handleOnboardingNext);

initializePopup();