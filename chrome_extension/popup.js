/**
 * HabitGuard popup.js
 *
 * Demo mode design:
 *   - "Enter Demo" stores a backup of real data under demoRealDataBackup,
 *     injects 10 days of simulated historical usage, sets demoModeActive=true,
 *     and runs analyzeUsage() against the fake data.
 *   - "Exit Demo" / "Refresh" restores demoRealDataBackup, clears the demo
 *     flag, and refreshes the live usage display.
 *   - "Refresh" always exits demo mode if active (user gets real data back).
 */

const API_URL = `${API_BASE_URL}/habitguard/custom/intervention`;
const USAGE_SNAPSHOT_URL = `${API_BASE_URL}/usage/snapshot`;
const USAGE_HISTORY_URL = `${API_BASE_URL}/usage/daily-history/local_user`;

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

const actionStatusEl = document.getElementById("actionStatus");
const startTimerBtn  = document.getElementById("startTimerBtn");
const breakBtn       = document.getElementById("breakBtn");
const stopTimerBtn   = document.getElementById("stopTimerBtn");

const categoryMessageEl = document.getElementById("categoryMessage");
const productiveBtn     = document.getElementById("productiveBtn");
const mixedBtn          = document.getElementById("mixedBtn");
const temptationBtn     = document.getElementById("temptationBtn");
const neutralBtn        = document.getElementById("neutralBtn");

const allButtons = [
  analyzeBtn, seedBtn, refreshBtn,
  startTimerBtn, breakBtn, stopTimerBtn,
  productiveBtn, mixedBtn, temptationBtn, neutralBtn
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

// ── Utilities ────────────────────────────────────────────────────────────────
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

// ── Theme toggle ─────────────────────────────────────────────────────────────
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

// ── Onboarding ───────────────────────────────────────────────────────────────
let onboardingStep = 1;
const ONBOARDING_TOTAL_STEPS = 3;

function updateOnboardingStep() {
  if (!onboardingOverlay) return;

  // Show/hide step content
  onboardingOverlay.querySelectorAll(".onboarding-step").forEach((el) => {
    el.style.display = Number(el.dataset.step) === onboardingStep ? "block" : "none";
  });

  // Update dot indicators
  onboardingOverlay.querySelectorAll(".onboarding-dot").forEach((el) => {
    if (Number(el.dataset.dot) === onboardingStep) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });

  // Update button text
  if (onboardingNextBtn) {
    onboardingNextBtn.textContent = onboardingStep === ONBOARDING_TOTAL_STEPS ? "Get Started" : "Next";
  }
}

async function handleOnboardingNext() {
  if (onboardingStep < ONBOARDING_TOTAL_STEPS) {
    onboardingStep++;
    updateOnboardingStep();
  } else {
    // Dismiss onboarding
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

// ── Storage helpers ──────────────────────────────────────────────────────────
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

// ── Demo mode UI state ───────────────────────────────────────────────────────
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

// ── Display helpers ──────────────────────────────────────────────────────────
async function getDailyUsageHistory() {
  const { dailyUsageMinutes } = await getStoredUsage();
  const mergedUsage = { ...dailyUsageMinutes };

  try {
    const response = await fetch(USAGE_HISTORY_URL);
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
  const minutes  = currentSession.sessionMinutes || 0;
  currentSessionEl.textContent = `${domain} | ${category} | ${minutes} min current session`;
}

function formatCheckedTime(timestamp) {
  if (!timestamp) return "No automatic check yet.";
  return `Last automatic JITAI check: ${new Date(timestamp).toLocaleTimeString()}`;
}

async function refreshUsageDisplay(showMessage = false) {
  const { dailyUsageMinutes, domainUsageMinutes, currentSession } = await getStoredUsage();
  const todayKey    = getTodayKey();
  const todayUsage  = dailyUsageMinutes[todayKey] || 0;
  const topDomain   = getTopDomainForToday(domainUsageMinutes);

  todayUsageEl.textContent = `${todayUsage} min`;
  topDomainEl.textContent  = topDomain;
  renderCurrentSession(currentSession);

  if (showMessage) {
    messageEl.textContent = "Usage display refreshed. Click Analyze Usage to update the intervention result.";
  }
}

// ── Intervention result rendering ────────────────────────────────────────────
function setLoading() {
  setButtonsEnabled(false);
  usageStatusEl.textContent  = "Loading...";
  frictionTypeEl.textContent = "Loading...";
  timerEl.textContent        = "Loading...";
  usageDetailsEl.textContent = "Sending tracked usage to backend...";
  messageEl.textContent      = "Checking HabitGuard backend...";
}

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

  if (data.mode === "CALIBRATION") {
    currentRecommendedTimerMinutes = null;
    usageStatusEl.textContent  = "CALIBRATING";
    frictionTypeEl.textContent = "Not active";
    timerEl.textContent        = "Not active";
    usageDetailsEl.textContent = "Baseline still being collected.";
    messageEl.textContent = `${data.message || "HabitGuard is still collecting baseline data."} ${formatCheckedTime(checkedAt)}`;
    return;
  }

  usageStatusEl.textContent  = data.usage_status || "UNKNOWN";
  frictionTypeEl.textContent = data.friction_type || "NONE";

  if (data.recommended_timer_minutes === null || data.recommended_timer_minutes === undefined) {
    currentRecommendedTimerMinutes = null;
    timerEl.textContent = "Not active";
  } else {
    currentRecommendedTimerMinutes = Number(data.recommended_timer_minutes);
    timerEl.textContent = `${currentRecommendedTimerMinutes} min`;
  }

  const baseline = data.baseline_usage_minutes;
  const recent   = data.recent_usage_minutes;
  const overuse  = data.overuse_gap_minutes;

  usageDetailsEl.textContent = (baseline !== undefined && recent !== undefined && overuse !== undefined)
    ? `Baseline: ${baseline} min | Recent: ${recent} min | Overuse: ${overuse} min`
    : "Baseline still being collected.";

  if (data.should_notify !== undefined || data.should_overlay !== undefined) {
    const notifyLabel   = data.should_notify   ? "🔔 Notify: Yes" : "🔕 Notify: No";
    const overlayLabel  = data.should_overlay  ? "📋 Overlay: Yes" : "📋 Overlay: No";
    const cooldownLabel = data.cooldown_minutes !== undefined ? ` | ⏳ Cooldown: ${data.cooldown_minutes} min` : "";
    deliveryDetailsEl.textContent = `${notifyLabel} | ${overlayLabel}${cooldownLabel}`;
    deliveryReasonEl.textContent  = data.delivery_reason || "";
    deliveryCardEl.style.display  = "block";
  } else {
    deliveryCardEl.style.display = "none";
  }

  messageEl.textContent = `${data.message || "No message returned."} ${formatCheckedTime(checkedAt)}`;
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

// ── Usage snapshot sync ──────────────────────────────────────────────────────
async function sendUsageSnapshotFromPopup(latestIntervention = null, options = {}) {
  const { source = "chrome_extension_popup" } = options;
  try {
    const todayKey = getTodayKey();
    const stored   = await chrome.storage.local.get([
      "dailyUsageMinutes", "domainUsageMinutes", "currentSession",
      "sessionHistory", "latestIntervention", "activeInterventionTimer"
    ]);
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
    const response = await fetch(USAGE_SNAPSHOT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await parseApiResponse(response);
    await chrome.storage.local.set({ lastPopupUsageSnapshotAt: Date.now(), lastPopupUsageSnapshotResult: data });
    return { success: response.ok, data };
  } catch (err) {
    console.error("HabitGuard popup usage snapshot failed:", err);
    await chrome.storage.local.set({ lastPopupUsageSnapshotError: err.message, lastPopupUsageSnapshotFailedAt: Date.now() });
    return { success: false, error: err.message };
  }
}

// ── Core analysis ────────────────────────────────────────────────────────────
async function analyzeUsage() {
  setLoading();
  try {
    const usageHistory = await getDailyUsageHistory();
    const stored       = await getStoredUsage();
    const todayKey     = getTodayKey();

    if (usageHistory.length === 0) {
      usageStatusEl.textContent  = "NO_DATA";
      frictionTypeEl.textContent = "-";
      timerEl.textContent        = "-";
      usageDetailsEl.textContent = "No tracked usage history found.";
      messageEl.textContent      = "Browse for a few minutes, then click Analyze Usage again.";
      return;
    }

    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usage_history_minutes: usageHistory,
        context: {
          current_domain:   stored.currentSession?.domain        || null,
          current_category: stored.currentSession?.category      || null,
          session_minutes:  stored.currentSession?.sessionMinutes || 0,
          top_domains:      stored.domainUsageMinutes[todayKey]  || {},
          timestamp:        Date.now()
        }
      })
    });

    if (!response.ok) throw new Error(`Backend returned ${response.status}`);

    const data      = await parseApiResponse(response);
    const checkedAt = Date.now();

    await chrome.storage.local.set({ latestIntervention: data, latestInterventionCheckedAt: checkedAt });
    await sendUsageSnapshotFromPopup(data);
    renderResult(data, checkedAt);
    await refreshUsageDisplay();
  } catch (err) {
    usageStatusEl.textContent  = "OFFLINE";
    frictionTypeEl.textContent = "-";
    timerEl.textContent        = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent      = "Could not connect to HabitGuard backend. Make sure FastAPI is running.";
    console.error(err);
  } finally {
    setButtonsEnabled(true);
  }
}

// ── Demo mode ────────────────────────────────────────────────────────────────
function buildDemoData() {
  const demoUsage = {};
  const demoDomainUsage = {};
  // 10 days of realistic demo baseline (day -10 … day -1)
  for (let i = 10; i >= 1; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = getTodayKey(d);
    demoUsage[key] = 30 + Math.round(Math.sin(i) * 12); // varies 18–42 min
    demoDomainUsage[key] = {
      "youtube.com":   12 + (i % 4),
      "instagram.com":  8 + (i % 3),
      "leetcode.com":   6 + (i % 2),
      "twitter.com":    4 + (i % 2)
    };
  }
  return { demoUsage, demoDomainUsage };
}

async function enterDemoMode() {
  // Back up current real data
  const stored = await getStoredUsage();
  await chrome.storage.local.set({
    demoRealDataBackup: {
      dailyUsageMinutes:  stored.dailyUsageMinutes,
      domainUsageMinutes: stored.domainUsageMinutes,
      latestIntervention: stored.latestIntervention,
      latestInterventionCheckedAt: stored.latestInterventionCheckedAt
    }
  });

  // Inject demo data (historical only — today's real data is overwritten
  // with a high-usage demo day so the ML sees "overuse today")
  const { demoUsage, demoDomainUsage } = buildDemoData();
  const todayKey = getTodayKey();
  demoUsage[todayKey]       = 75;  // simulate heavy overuse today
  demoDomainUsage[todayKey] = { "youtube.com": 45, "instagram.com": 20, "twitter.com": 10 };

  await chrome.storage.local.set({
    dailyUsageMinutes:  demoUsage,
    domainUsageMinutes: demoDomainUsage,
    demoModeActive:     true
  });

  applyDemoUI(true);
  await refreshUsageDisplay();
  await analyzeUsage();
}

async function exitDemoMode() {
  // Restore real data backup
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
  await refreshUsageDisplay(false);
  await loadLatestIntervention();
  messageEl.textContent = "Demo mode exited. Showing your real live tracking.";
}

async function toggleDemoMode() {
  const inDemo = await isDemoModeActive();
  if (inDemo) {
    await exitDemoMode();
  } else {
    await enterDemoMode();
  }
}

// ── Timer helpers ────────────────────────────────────────────────────────────
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

async function startRecommendedTimer() {
  if (!currentRecommendedTimerMinutes || currentRecommendedTimerMinutes <= 0) {
    actionStatusEl.textContent = "No recommended timer available yet. Click Analyze Usage first.";
    return;
  }
  await saveActiveTimer("timer", currentRecommendedTimerMinutes);
}

async function startBreakTimer()  { await saveActiveTimer("break", 5); }

async function stopActiveTimer() {
  if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
  await chrome.storage.local.remove(["activeInterventionTimer"]);
  await sendUsageSnapshotFromPopup(null, { source: "chrome_extension_timer_cleared" });
  actionStatusEl.textContent = "Timer stopped.";
}

// ── Site category ────────────────────────────────────────────────────────────
async function setCurrentDomainCategory(category) {
  const stored         = await getStoredUsage();
  const currentSession = stored.currentSession;
  if (!currentSession || !currentSession.domain) {
    categoryMessageEl.textContent = "No current site detected yet. Browse a website for a minute and refresh.";
    return;
  }
  const domain             = currentSession.domain;
  const updatedCategories  = { ...stored.userDomainCategories, [domain]: category };
  const updatedSession     = { ...currentSession, category };
  await chrome.storage.local.set({ userDomainCategories: updatedCategories, currentSession: updatedSession });
  await sendUsageSnapshotFromPopup(null, { source: "chrome_extension_category_updated" });
  renderCurrentSession(updatedSession);
  categoryMessageEl.textContent = `${domain} is now marked as ${category}. HabitGuard will remember this.`;
}

// ── Refresh: always exits demo mode first if active ──────────────────────────
async function handleRefresh() {
  const inDemo = await isDemoModeActive();
  if (inDemo) {
    await exitDemoMode();
  } else {
    await refreshUsageDisplay(true);
  }
}

// ── Init ─────────────────────────────────────────────────────────────────────
async function initializePopup() {
  // Load theme preference first (avoid flash of wrong theme)
  await loadThemePreference();

  // Restore demo UI state if demo was active when popup was last closed
  const inDemo = await isDemoModeActive();
  applyDemoUI(inDemo);

  await refreshUsageDisplay();
  await loadLatestIntervention();
  await loadActiveTimer();

  // Show onboarding if first run
  await checkAndShowOnboarding();
}

// ── Event listeners ──────────────────────────────────────────────────────────
analyzeBtn.addEventListener("click",  analyzeUsage);
seedBtn.addEventListener("click",     toggleDemoMode);
refreshBtn.addEventListener("click",  handleRefresh);

startTimerBtn.addEventListener("click", startRecommendedTimer);
breakBtn.addEventListener("click",      startBreakTimer);
stopTimerBtn.addEventListener("click",  stopActiveTimer);

productiveBtn.addEventListener("click",  () => setCurrentDomainCategory("productive"));
mixedBtn.addEventListener("click",       () => setCurrentDomainCategory("mixed"));
temptationBtn.addEventListener("click",  () => setCurrentDomainCategory("temptation"));
neutralBtn.addEventListener("click",     () => setCurrentDomainCategory("neutral"));

// Theme toggle
if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);

// Onboarding
if (onboardingNextBtn) onboardingNextBtn.addEventListener("click", handleOnboardingNext);

initializePopup();