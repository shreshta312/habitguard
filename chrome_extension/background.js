const API_URL = "http://127.0.0.1:8000/habitguard/custom/intervention";

const TRACKING_ALARM_NAME = "habitguard_usage_tracker";
const JITAI_ALARM_NAME = "habitguard_jitai_checker";

const JITAI_CHECK_INTERVAL_MINUTES = 5;
const NOTIFICATION_COOLDOWN_MINUTES = 15;
const OVERLAY_COOLDOWN_MINUTES = 20;
const SESSION_GAP_RESET_MINUTES = 3;
const MAX_SESSION_HISTORY = 50;

// Set to true during development to enable verbose console logging.
const DEBUG = false;

function debugLog(...args) {
  if (DEBUG) console.log(...args);
}

// Concurrency guard: prevents overlapping JITAI fetch calls.
let jitaiRunning = false;

function getTodayKey() {
  return new Date().toISOString().slice(0, 10);
}

function isTrackableUrl(url) {
  if (!url) return false;
  return url.startsWith("http://") || url.startsWith("https://");
}

function getDomain(url) {
  try {
    const parsedUrl = new URL(url);
    return parsedUrl.hostname.replace(/^www\./, "");
  } catch {
    return "unknown";
  }
}

function getDefaultDomainCategory(domain) {
  const productiveDomains = [
    "leetcode.com",
    "github.com",
    "stackoverflow.com",
    "developer.mozilla.org",
    "docs.python.org",
    "kaggle.com",
    "coursera.org",
    "edx.org",
    "geeksforgeeks.org",
    "w3schools.com",
    "localhost",
    "127.0.0.1"
  ];

  const temptationDomains = [
    "youtube.com",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "netflix.com",
    "primevideo.com",
    "hotstar.com",
    "discord.com"
  ];

  const mixedDomains = [
    "chatgpt.com",
    "google.com",
    "linkedin.com",
    "gmail.com",
    "mail.google.com",
    "drive.google.com"
  ];

  if (productiveDomains.some((item) => domain.includes(item))) {
    return "productive";
  }

  if (temptationDomains.some((item) => domain.includes(item))) {
    return "temptation";
  }

  if (mixedDomains.some((item) => domain.includes(item))) {
    return "mixed";
  }

  return "neutral";
}

async function getDomainCategory(domain) {
  const stored = await chrome.storage.local.get(["userDomainCategories"]);
  const userDomainCategories = stored.userDomainCategories || {};

  if (userDomainCategories[domain]) {
    return userDomainCategories[domain];
  }

  return getDefaultDomainCategory(domain);
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({
    active: true,
    lastFocusedWindow: true
  });

  if (!tabs || tabs.length === 0) return null;
  return tabs[0];
}

async function getStoredUsage() {
  const stored = await chrome.storage.local.get([
    "dailyUsageMinutes",
    "domainUsageMinutes",
    "currentSession",
    "sessionHistory"
  ]);

  return {
    dailyUsageMinutes: stored.dailyUsageMinutes || {},
    domainUsageMinutes: stored.domainUsageMinutes || {},
    currentSession: stored.currentSession || null,
    sessionHistory: stored.sessionHistory || []
  };
}

function closeCurrentSession(currentSession, sessionHistory, endedAt) {
  if (!currentSession) {
    return sessionHistory;
  }

  const completedSession = {
    ...currentSession,
    endedAt,
    durationMinutes: currentSession.sessionMinutes || 0
  };

  const updatedHistory = [completedSession, ...sessionHistory];

  return updatedHistory.slice(0, MAX_SESSION_HISTORY);
}

// Accepts current state from the caller so this function never reads storage
// itself. This lets incrementUsageMinute merge all writes into a single
// chrome.storage.local.set call, eliminating the read-write race.
//
// Note on gap time: when a session expires (domain changed or gap >
// SESSION_GAP_RESET_MINUTES), elapsed gap time is not credited to the closing
// session's durationMinutes. This is intentional — gap time means the user
// was away, so crediting it would inflate session length.
function computeSessionUpdate(domain, category, currentSession, sessionHistory) {
  const now = Date.now();

  if (!currentSession) {
    return {
      sessionHistory,
      currentSession: {
        domain,
        category,
        startedAt: now,
        lastUpdatedAt: now,
        sessionMinutes: 1
      }
    };
  }

  const gapMinutes = (now - currentSession.lastUpdatedAt) / (1000 * 60);
  const domainChanged = currentSession.domain !== domain;
  const sessionExpired = gapMinutes > SESSION_GAP_RESET_MINUTES;

  if (domainChanged || sessionExpired) {
    const updatedHistory = closeCurrentSession(currentSession, sessionHistory, now);
    return {
      sessionHistory: updatedHistory,
      currentSession: {
        domain,
        category,
        startedAt: now,
        lastUpdatedAt: now,
        sessionMinutes: 1
      }
    };
  }

  return {
    sessionHistory,
    currentSession: {
      ...currentSession,
      category,
      lastUpdatedAt: now,
      sessionMinutes: currentSession.sessionMinutes + 1
    }
  };
}

async function incrementUsageMinute() {
  const activeTab = await getActiveTab();

  if (!activeTab || !isTrackableUrl(activeTab.url)) return;

  try {
    const windowInfo = await chrome.windows.get(activeTab.windowId);
    if (!windowInfo.focused) return;
  } catch {
    return;
  }

  const todayKey = getTodayKey();
  const domain = getDomain(activeTab.url);
  const category = await getDomainCategory(domain);

  // Single read for all state we need.
  const { dailyUsageMinutes, domainUsageMinutes, currentSession, sessionHistory } =
    await getStoredUsage();

  dailyUsageMinutes[todayKey] = (dailyUsageMinutes[todayKey] || 0) + 1;

  if (!domainUsageMinutes[todayKey]) {
    domainUsageMinutes[todayKey] = {};
  }
  domainUsageMinutes[todayKey][domain] =
    (domainUsageMinutes[todayKey][domain] || 0) + 1;

  // Compute session update without touching storage.
  const { currentSession: newSession, sessionHistory: newHistory } =
    computeSessionUpdate(domain, category, currentSession, sessionHistory);

  // Single atomic write for all state.
  await chrome.storage.local.set({
    dailyUsageMinutes,
    domainUsageMinutes,
    currentSession: newSession,
    sessionHistory: newHistory
  });

  debugLog("HabitGuard tracked 1 minute:", {
    date: todayKey,
    domain,
    category,
    totalToday: dailyUsageMinutes[todayKey]
  });
}

async function getDailyUsageHistory() {
  const { dailyUsageMinutes } = await getStoredUsage();
  const dates = Object.keys(dailyUsageMinutes).sort();
  return dates.map((date) => dailyUsageMinutes[date]);
}

function shouldTriggerNotification(intervention) {
  const status = intervention.usage_status;
  return status === "HIGH_USAGE" || status === "RISKY_USAGE_SPIKE";
}

async function isNotificationCooldownActive() {
  const stored = await chrome.storage.local.get(["lastNotificationAt"]);
  const lastNotificationAt = stored.lastNotificationAt;

  if (!lastNotificationAt) return false;

  const elapsedMinutes = (Date.now() - lastNotificationAt) / (1000 * 60);
  return elapsedMinutes < NOTIFICATION_COOLDOWN_MINUTES;
}

async function isOverlayCooldownActive() {
  const stored = await chrome.storage.local.get(["lastOverlayShownAt"]);
  const lastOverlayShownAt = stored.lastOverlayShownAt;

  if (!lastOverlayShownAt) return false;

  const elapsedMinutes = (Date.now() - lastOverlayShownAt) / (1000 * 60);
  return elapsedMinutes < OVERLAY_COOLDOWN_MINUTES;
}

async function showInterventionNotification(intervention) {
  const cooldownActive = await isNotificationCooldownActive();
  if (cooldownActive) return;

  const timer = intervention.recommended_timer_minutes;
  const status = intervention.usage_status || "Usage alert";

  let message =
    intervention.message || "HabitGuard recommends taking a short break.";

  if (timer !== null && timer !== undefined) {
    message = `${message} Suggested timer: ${timer} min.`;
  }

  await chrome.notifications.create({
    type: "basic",
    iconUrl: "icon128.png",
    title: `HabitGuard: ${status}`,
    message,
    priority: 2
  });

  await chrome.storage.local.set({
    lastNotificationAt: Date.now()
  });
}

async function updateBadge(intervention) {
  const status = intervention.usage_status;

  if (status === "RISKY_USAGE_SPIKE") {
    await chrome.action.setBadgeText({ text: "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#dc2626" });
    return;
  }

  if (status === "HIGH_USAGE") {
    await chrome.action.setBadgeText({ text: "T" });
    await chrome.action.setBadgeBackgroundColor({ color: "#f97316" });
    return;
  }

  if (status === "SLIGHTLY_ABOVE_BASELINE") {
    await chrome.action.setBadgeText({ text: "S" });
    await chrome.action.setBadgeBackgroundColor({ color: "#2563eb" });
    return;
  }

  await chrome.action.setBadgeText({ text: "" });
}

function shouldTriggerOverlay(intervention, currentSession) {
  if (!intervention || !currentSession) {
    return false;
  }

  const status = intervention.usage_status;
  const category = currentSession.category;
  const sessionMinutes = currentSession.sessionMinutes || 0;

  const riskyStatus =
    status === "HIGH_USAGE" || status === "RISKY_USAGE_SPIKE";

  const riskyContext =
    category === "temptation" && sessionMinutes >= 3;

  return riskyStatus && riskyContext;
}

async function sendOverlayToActiveTab(intervention, currentSession) {
  const activeTab = await getActiveTab();

  if (!activeTab || !activeTab.id || !isTrackableUrl(activeTab.url)) {
    return;
  }

  const payload = {
    domain: currentSession.domain,
    category: currentSession.category,
    sessionMinutes: currentSession.sessionMinutes || 0,
    timerMinutes: intervention.recommended_timer_minutes,
    status: intervention.usage_status,
    frictionType: intervention.friction_type,
    message: intervention.message
  };

  try {
    await chrome.tabs.sendMessage(activeTab.id, {
      type: "SHOW_HABITGUARD_OVERLAY",
      payload
    });

    await chrome.storage.local.set({
      lastOverlayShownAt: Date.now(),
      lastOverlayPayload: payload
    });
  } catch (error) {
    console.error("HabitGuard overlay failed:", error);
  }
}

async function runJitaiCheck() {
  if (jitaiRunning) {
    debugLog("HabitGuard JITAI: skipping, previous check still in flight.");
    return;
  }

  jitaiRunning = true;

  try {
    const usageHistory = await getDailyUsageHistory();

    if (usageHistory.length === 0) return;

    const todayKey = getTodayKey();

    const storedContext = await chrome.storage.local.get([
      "currentSession",
      "domainUsageMinutes"
    ]);

    const currentSession = storedContext.currentSession || null;
    const domainUsageMinutes = storedContext.domainUsageMinutes || {};

    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        usage_history_minutes: usageHistory,
        context: {
          current_domain: currentSession?.domain || null,
          current_category: currentSession?.category || null,
          session_minutes: currentSession?.sessionMinutes || 0,
          top_domains: domainUsageMinutes[todayKey] || {},
          timestamp: Date.now()
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const intervention = await response.json();

    await chrome.storage.local.set({
      latestIntervention: intervention,
      latestInterventionCheckedAt: Date.now()
    });

    await updateBadge(intervention);

    if (shouldTriggerNotification(intervention)) {
      await showInterventionNotification(intervention);
    }

    if (shouldTriggerOverlay(intervention, currentSession)) {
      const overlayCooldownActive = await isOverlayCooldownActive();

      if (!overlayCooldownActive) {
        await sendOverlayToActiveTab(intervention, currentSession);
      }
    }

    debugLog("HabitGuard JITAI check:", intervention);

  } catch (error) {
    console.error("HabitGuard JITAI check failed:", error);
  } finally {
    jitaiRunning = false;
  }
}

async function startAlarms() {
  await chrome.alarms.clearAll();

  await chrome.alarms.create(TRACKING_ALARM_NAME, {
    periodInMinutes: 1
  });

  await chrome.alarms.create(JITAI_ALARM_NAME, {
    periodInMinutes: JITAI_CHECK_INTERVAL_MINUTES
  });
}

chrome.runtime.onInstalled.addListener(() => {
  startAlarms();
});

chrome.runtime.onStartup.addListener(() => {
  startAlarms();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === TRACKING_ALARM_NAME) {
    incrementUsageMinute();
  }

  if (alarm.name === JITAI_ALARM_NAME) {
    runJitaiCheck();
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (!message || !message.type) {
    return;
  }

  if (message.type === "HABITGUARD_OVERLAY_DISMISSED") {
    chrome.storage.local.set({
      lastOverlayDismissedAt: Date.now(),
      lastOverlayDismissedPayload: message.payload || null
    });
  }

  if (message.type === "HABITGUARD_BREAK_ACCEPTED") {
    const endAt = Date.now() + 5 * 60 * 1000;

    chrome.storage.local.set({
      lastBreakAcceptedAt: Date.now(),
      lastBreakAcceptedPayload: message.payload || null,
      activeInterventionTimer: {
        type: "break",
        durationMinutes: 5,
        endAt
      }
    });
  }
});