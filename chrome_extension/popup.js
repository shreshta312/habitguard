const API_URL = "http://127.0.0.1:8000/habitguard/custom/intervention";

const todayUsageEl = document.getElementById("todayUsage");
const topDomainEl = document.getElementById("topDomain");
const currentSessionEl = document.getElementById("currentSession");
const usageStatusEl = document.getElementById("usageStatus");
const frictionTypeEl = document.getElementById("frictionType");
const timerEl = document.getElementById("timer");
const usageDetailsEl = document.getElementById("usageDetails");
const messageEl = document.getElementById("message");

const analyzeBtn = document.getElementById("analyzeBtn");
const seedBtn = document.getElementById("seedBtn");
const resetBtn = document.getElementById("resetBtn");
const refreshBtn = document.getElementById("refreshBtn");

const actionStatusEl = document.getElementById("actionStatus");
const startTimerBtn = document.getElementById("startTimerBtn");
const breakBtn = document.getElementById("breakBtn");
const stopTimerBtn = document.getElementById("stopTimerBtn");

const categoryMessageEl = document.getElementById("categoryMessage");
const productiveBtn = document.getElementById("productiveBtn");
const mixedBtn = document.getElementById("mixedBtn");
const temptationBtn = document.getElementById("temptationBtn");
const neutralBtn = document.getElementById("neutralBtn");

const allButtons = [
  analyzeBtn,
  seedBtn,
  resetBtn,
  refreshBtn,
  startTimerBtn,
  breakBtn,
  stopTimerBtn,
  productiveBtn,
  mixedBtn,
  temptationBtn,
  neutralBtn
].filter(Boolean);

let currentRecommendedTimerMinutes = null;
let countdownInterval = null;

function getTodayKey() {
  return new Date().toISOString().slice(0, 10);
}

function setButtonsEnabled(enabled) {
  allButtons.forEach((button) => {
    button.disabled = !enabled;
  });
}

async function getStoredUsage() {
  const stored = await chrome.storage.local.get([
    "dailyUsageMinutes",
    "domainUsageMinutes",
    "latestIntervention",
    "latestInterventionCheckedAt",
    "activeInterventionTimer",
    "currentSession",
    "sessionHistory",
    "userDomainCategories"
  ]);

  return {
    dailyUsageMinutes: stored.dailyUsageMinutes || {},
    domainUsageMinutes: stored.domainUsageMinutes || {},
    latestIntervention: stored.latestIntervention || null,
    latestInterventionCheckedAt: stored.latestInterventionCheckedAt || null,
    activeInterventionTimer: stored.activeInterventionTimer || null,
    currentSession: stored.currentSession || null,
    sessionHistory: stored.sessionHistory || [],
    userDomainCategories: stored.userDomainCategories || {}
  };
}

async function getDailyUsageHistory() {
  const { dailyUsageMinutes } = await getStoredUsage();

  const dates = Object.keys(dailyUsageMinutes).sort();

  return dates.map((date) => dailyUsageMinutes[date]);
}

function getTopDomainForToday(domainUsageMinutes) {
  const todayKey = getTodayKey();
  const todayDomains = domainUsageMinutes[todayKey] || {};

  const entries = Object.entries(todayDomains);

  if (entries.length === 0) {
    return "No data";
  }

  entries.sort((a, b) => b[1] - a[1]);

  const [domain, minutes] = entries[0];

  return `${domain} (${minutes} min)`;
}

function renderCurrentSession(currentSession) {
  if (!currentSessionEl) return;

  if (!currentSession) {
    currentSessionEl.textContent = "No active session.";
    return;
  }

  const domain = currentSession.domain || "unknown";
  const category = currentSession.category || "neutral";
  const minutes = currentSession.sessionMinutes || 0;

  currentSessionEl.textContent =
    `${domain} | ${category} | ${minutes} min current session`;
}

function formatCheckedTime(timestamp) {
  if (!timestamp) {
    return "No automatic check yet.";
  }

  const checkedDate = new Date(timestamp);
  return `Last automatic JITAI check: ${checkedDate.toLocaleTimeString()}`;
}

async function refreshUsageDisplay(showMessage = false) {
  const {
    dailyUsageMinutes,
    domainUsageMinutes,
    currentSession
  } = await getStoredUsage();

  const todayKey = getTodayKey();
  const todayUsage = dailyUsageMinutes[todayKey] || 0;
  const topDomain = getTopDomainForToday(domainUsageMinutes);

  todayUsageEl.textContent = `${todayUsage} min`;
  topDomainEl.textContent = topDomain;
  renderCurrentSession(currentSession);

  if (showMessage) {
    messageEl.textContent =
      "Usage display refreshed. Click Analyze Usage to update the intervention result.";
  }
}

function setLoading() {
  setButtonsEnabled(false);

  usageStatusEl.textContent = "Loading...";
  frictionTypeEl.textContent = "Loading...";
  timerEl.textContent = "Loading...";
  usageDetailsEl.textContent = "Sending tracked usage to backend...";
  messageEl.textContent = "Checking HabitGuard backend...";
}

function renderResult(data, checkedAt = null) {
  if (data.error) {
    currentRecommendedTimerMinutes = null;

    usageStatusEl.textContent = "ERROR";
    frictionTypeEl.textContent = "-";
    timerEl.textContent = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent = data.error;
    return;
  }

  if (data.mode === "CALIBRATION") {
    currentRecommendedTimerMinutes = null;

    usageStatusEl.textContent = "CALIBRATING";
    frictionTypeEl.textContent = "Not active";
    timerEl.textContent = "Not active";
    usageDetailsEl.textContent = "Baseline still being collected.";
    messageEl.textContent =
      `${data.message || "HabitGuard is still collecting baseline data."} ${formatCheckedTime(checkedAt)}`;
    return;
  }

  usageStatusEl.textContent = data.usage_status || "UNKNOWN";
  frictionTypeEl.textContent = data.friction_type || "NONE";

  if (
    data.recommended_timer_minutes === null ||
    data.recommended_timer_minutes === undefined
  ) {
    currentRecommendedTimerMinutes = null;
    timerEl.textContent = "Not active";
  } else {
    currentRecommendedTimerMinutes = Number(data.recommended_timer_minutes);
    timerEl.textContent = `${currentRecommendedTimerMinutes} min`;
  }

  const baseline = data.baseline_usage_minutes;
  const recent = data.recent_usage_minutes;
  const overuse = data.overuse_gap_minutes;

  if (
    baseline === undefined ||
    recent === undefined ||
    overuse === undefined
  ) {
    usageDetailsEl.textContent = "Baseline still being collected.";
  } else {
    usageDetailsEl.textContent =
      `Baseline: ${baseline} min | Recent: ${recent} min | Overuse: ${overuse} min`;
  }

  const backendMessage = data.message || "No message returned.";
  messageEl.textContent = `${backendMessage} ${formatCheckedTime(checkedAt)}`;
}

async function loadLatestIntervention() {
  const { latestIntervention, latestInterventionCheckedAt } =
    await getStoredUsage();

  if (!latestIntervention) {
    usageStatusEl.textContent = "Waiting...";
    frictionTypeEl.textContent = "Waiting...";
    timerEl.textContent = "Waiting...";
    usageDetailsEl.textContent = "Waiting for analysis...";
    messageEl.textContent =
      "No automatic JITAI result yet. Click Analyze Usage or wait for background check.";
    return;
  }

  renderResult(latestIntervention, latestInterventionCheckedAt);
}

async function analyzeUsage() {
  setLoading();

  try {
    const usageHistory = await getDailyUsageHistory();

    if (usageHistory.length === 0) {
      usageStatusEl.textContent = "NO_DATA";
      frictionTypeEl.textContent = "-";
      timerEl.textContent = "-";
      usageDetailsEl.textContent = "No tracked usage history found.";
      messageEl.textContent =
        "Browse for a few minutes, then click Analyze Usage again.";
      return;  // finally still runs — buttons will be re-enabled
    }

    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        // TODO: extend this payload to include per-domain and per-category
        // breakdown so the backend can weight temptation-site usage differently
        // from productive-site usage in the intervention decision.
        usage_history_minutes: usageHistory
      })
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    const checkedAt = Date.now();

    await chrome.storage.local.set({
      latestIntervention: data,
      latestInterventionCheckedAt: checkedAt
    });

    renderResult(data, checkedAt);
    await refreshUsageDisplay();
  } catch (error) {
    usageStatusEl.textContent = "OFFLINE";
    frictionTypeEl.textContent = "-";
    timerEl.textContent = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent =
      "Could not connect to HabitGuard backend. Make sure FastAPI is running.";

    console.error(error);
  } finally {
    setButtonsEnabled(true);
  }
}

async function seedDemoData() {
  const todayKey = getTodayKey();

  // Generate 10 days of demo baseline ending yesterday, so the seed is never
  // stale regardless of when it is run.
  const demoUsage = {};
  for (let i = 10; i >= 1; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    // Vary usage slightly so the baseline is not a flat line.
    demoUsage[key] = 20 + (i % 5);
  }

  const stored = await getStoredUsage();

  const realTodayUsage = stored.dailyUsageMinutes[todayKey] || 0;
  const demoTodayUsage = Math.max(realTodayUsage, 50);

  const demoDomainUsage = {
    [todayKey]: {
      "youtube.com": 35,
      "instagram.com": 10,
      "leetcode.com": 5
    }
  };

  await chrome.storage.local.set({
    dailyUsageMinutes: {
      ...demoUsage,
      ...stored.dailyUsageMinutes,
      [todayKey]: demoTodayUsage
    },
    domainUsageMinutes: {
      ...stored.domainUsageMinutes,
      ...demoDomainUsage
    }
  });

  await refreshUsageDisplay();
  await analyzeUsage();
}

function formatRemainingTime(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

async function saveActiveTimer(type, durationMinutes) {
  const endAt = Date.now() + durationMinutes * 60 * 1000;

  await chrome.storage.local.set({
    activeInterventionTimer: {
      type,
      durationMinutes,
      endAt
    }
  });

  startCountdown(endAt, type);
}

function startCountdown(endAt, type) {
  if (countdownInterval) {
    clearInterval(countdownInterval);
  }

  function updateCountdown() {
    const remaining = endAt - Date.now();

    if (remaining <= 0) {
      clearInterval(countdownInterval);
      countdownInterval = null;

      actionStatusEl.textContent =
        type === "break"
          ? "Break complete. You can return mindfully."
          : "Timer complete. Consider stopping or taking a short break.";

      chrome.storage.local.remove(["activeInterventionTimer"]);
      return;
    }

    const label = type === "break" ? "Break time left" : "Timer time left";
    actionStatusEl.textContent = `${label}: ${formatRemainingTime(remaining)}`;
  }

  updateCountdown();
  countdownInterval = setInterval(updateCountdown, 1000);
}

async function loadActiveTimer() {
  const stored = await chrome.storage.local.get(["activeInterventionTimer"]);
  const activeTimer = stored.activeInterventionTimer;

  if (!activeTimer) {
    actionStatusEl.textContent = "No active timer.";
    return;
  }

  if (activeTimer.endAt <= Date.now()) {
    await chrome.storage.local.remove(["activeInterventionTimer"]);
    actionStatusEl.textContent = "No active timer.";
    return;
  }

  startCountdown(activeTimer.endAt, activeTimer.type);
}

async function startRecommendedTimer() {
  if (!currentRecommendedTimerMinutes || currentRecommendedTimerMinutes <= 0) {
    actionStatusEl.textContent =
      "No recommended timer available yet. Click Analyze Usage first.";
    return;
  }

  await saveActiveTimer("timer", currentRecommendedTimerMinutes);
}

async function startBreakTimer() {
  await saveActiveTimer("break", 5);
}

async function stopActiveTimer() {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }

  await chrome.storage.local.remove(["activeInterventionTimer"]);
  actionStatusEl.textContent = "Timer stopped.";
}

async function setCurrentDomainCategory(category) {
  const stored = await getStoredUsage();
  const currentSession = stored.currentSession;

  if (!currentSession || !currentSession.domain) {
    categoryMessageEl.textContent =
      "No current site detected yet. Browse a website for a minute and refresh.";
    return;
  }

  const domain = currentSession.domain;

  const updatedCategories = {
    ...stored.userDomainCategories,
    [domain]: category
  };

  const updatedSession = {
    ...currentSession,
    category
  };

  await chrome.storage.local.set({
    userDomainCategories: updatedCategories,
    currentSession: updatedSession
  });

  renderCurrentSession(updatedSession);

  categoryMessageEl.textContent =
    `${domain} is now marked as ${category}. HabitGuard will remember this.`;
}

async function resetData() {
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }

  await chrome.storage.local.remove([
    "dailyUsageMinutes",
    "domainUsageMinutes",
    "lastNotificationAt",
    "latestIntervention",
    "latestInterventionCheckedAt",
    "activeInterventionTimer",
    "currentSession",
    "sessionHistory"
  ]);

  todayUsageEl.textContent = "0 min";
  topDomainEl.textContent = "No data";
  renderCurrentSession(null);
  usageStatusEl.textContent = "RESET";
  frictionTypeEl.textContent = "-";
  timerEl.textContent = "-";
  usageDetailsEl.textContent = "Stored usage data cleared.";
  actionStatusEl.textContent = "No active timer.";
  categoryMessageEl.textContent =
    "Your saved site categories are kept. You can personalize site categories.";
  messageEl.textContent = "Browse again to collect new usage data.";

  currentRecommendedTimerMinutes = null;
  setButtonsEnabled(true);
}

async function initializePopup() {
  await refreshUsageDisplay();
  await loadLatestIntervention();
  await loadActiveTimer();
}

analyzeBtn.addEventListener("click", analyzeUsage);
seedBtn.addEventListener("click", seedDemoData);
resetBtn.addEventListener("click", resetData);
refreshBtn.addEventListener("click", () => {
  refreshUsageDisplay(true);
});

startTimerBtn.addEventListener("click", startRecommendedTimer);
breakBtn.addEventListener("click", startBreakTimer);
stopTimerBtn.addEventListener("click", stopActiveTimer);

productiveBtn.addEventListener("click", () => {
  setCurrentDomainCategory("productive");
});

mixedBtn.addEventListener("click", () => {
  setCurrentDomainCategory("mixed");
});

temptationBtn.addEventListener("click", () => {
  setCurrentDomainCategory("temptation");
});

neutralBtn.addEventListener("click", () => {
  setCurrentDomainCategory("neutral");
});

initializePopup();