const API_URL = "http://127.0.0.1:8000/habitguard/custom/intervention";
const USAGE_SNAPSHOT_URL = "http://127.0.0.1:8000/usage/snapshot";

const USAGE_SNAPSHOT_THROTTLE_MS = 2 * 60 * 1000;
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

function getTodayKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
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
  if (!intervention || !intervention.should_intervene) {
    return false;
  }

  const frictionType = intervention.friction_type;

  return (
    frictionType === "TIMER_WARNING" ||
    frictionType === "STRONG_FRICTION"
  );
}

async function isNotificationCooldownActive() {
  const stored = await chrome.storage.local.get(["lastNotificationAt"]);
  const lastNotificationAt = stored.lastNotificationAt;

  if (!lastNotificationAt) return false;

  const elapsedMinutes = (Date.now() - lastNotificationAt) / (1000 * 60);
  return elapsedMinutes < NOTIFICATION_COOLDOWN_MINUTES;
}

async function isOverlayCooldownActive(domain) {
  if (!domain) return false;

  const stored = await chrome.storage.local.get(["overlayCooldownByDomain"]);
  const overlayCooldownByDomain = stored.overlayCooldownByDomain || {};

  const lastOverlayShownAt = overlayCooldownByDomain[domain];

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
  if (!intervention || !intervention.should_intervene) {
    await chrome.action.setBadgeText({ text: "" });
    return;
  }

  const frictionType = intervention.friction_type;

  if (frictionType === "STRONG_FRICTION") {
    await chrome.action.setBadgeText({ text: "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#dc2626" });
    return;
  }

  if (frictionType === "TIMER_WARNING") {
    await chrome.action.setBadgeText({ text: "T" });
    await chrome.action.setBadgeBackgroundColor({ color: "#f97316" });
    return;
  }

  if (frictionType === "SOFT_WARNING") {
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

  const shouldIntervene = intervention.should_intervene;
  const frictionType = intervention.friction_type;
  const category = currentSession.category;
  const sessionMinutes = currentSession.sessionMinutes || 0;

  const strongEnough =
    frictionType === "STRONG_FRICTION" || frictionType === "TIMER_WARNING";

  const riskyContext =
    category === "temptation" && sessionMinutes >= 3;

  return shouldIntervene && strongEnough && riskyContext;
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

    const now = Date.now();

    const stored = await chrome.storage.local.get(["overlayCooldownByDomain"]);
    const overlayCooldownByDomain = stored.overlayCooldownByDomain || {};

    overlayCooldownByDomain[currentSession.domain] = now;

    await chrome.storage.local.set({
      lastOverlayShownAt: now,
      lastOverlayPayload: payload,
      overlayCooldownByDomain
    });
  } catch (error) {
    console.error("HabitGuard overlay failed:", error);
  }
}

async function parseApiResponse(response) {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch (error) {
    return {
      raw_response: text
    };
  }
}

async function sendUsageSnapshot(latestIntervention = null, options = {}) {
  const { force = false, source = "chrome_extension" } = options;

  try {
    const todayKey = getTodayKey();
    const now = Date.now();

    const stored = await chrome.storage.local.get([
      "dailyUsageMinutes",
      "domainUsageMinutes",
      "currentSession",
      "sessionHistory",
      "latestIntervention",
      "activeInterventionTimer",
      "lastUsageSnapshotAt"
    ]);

    const lastSnapshotAt = stored.lastUsageSnapshotAt || 0;

    if (!force && now - lastSnapshotAt < USAGE_SNAPSHOT_THROTTLE_MS) {
      await chrome.storage.local.set({
        lastUsageSnapshotSkippedAt: now,
        lastUsageSnapshotSkipReason: "throttled"
      });

      return {
        success: true,
        skipped: true,
        reason: "throttled"
      };
    }

    const body = {
      user_id: "local_user",
      date: todayKey,
      daily_usage_minutes: stored.dailyUsageMinutes || {},
      domain_usage_minutes: stored.domainUsageMinutes || {},
      current_session: stored.currentSession || null,
      session_history: stored.sessionHistory || [],
      latest_intervention:
        latestIntervention || stored.latestIntervention || null,
      active_intervention_timer: stored.activeInterventionTimer || null,
      source
    };

    const response = await fetch(USAGE_SNAPSHOT_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    const data = await parseApiResponse(response);

    const result = {
      success: response.ok,
      status: response.status,
      data
    };

    await chrome.storage.local.set({
      lastUsageSnapshotAt: response.ok ? now : stored.lastUsageSnapshotAt || null,
      lastUsageSnapshotResult: result
    });

    if (!response.ok) {
      console.error("HabitGuard usage snapshot failed:", result);
    }

    return result;
  } catch (error) {
    console.error("HabitGuard usage snapshot failed:", error);

    await chrome.storage.local.set({
      lastUsageSnapshotError: error.message,
      lastUsageSnapshotFailedAt: Date.now()
    });

    return {
      success: false,
      error: error.message
    };
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

    await sendUsageSnapshot(intervention);

    await updateBadge(intervention);

    if (shouldTriggerNotification(intervention)) {
      await showInterventionNotification(intervention);
    }

    if (shouldTriggerOverlay(intervention, currentSession)) {
      const overlayCooldownActive = await isOverlayCooldownActive(
        currentSession?.domain
      );

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
const HABITGUARD_API_BASE = "http://127.0.0.1:8000";

async function sendFeedbackEvent(eventType, payload = {}) {
  const body = {
    user_id: payload.user_id || "local_user",
    event_type: eventType,

    site: payload.site || null,
    category: payload.category || null,
    overlay_id: payload.overlay_id || null,

    decision: payload.decision || null,
    reason: payload.reason || null,

    timestamp: new Date().toISOString(),

    context: payload.context || {}
  };

  try {
    const response = await fetch(`${HABITGUARD_API_BASE}/feedback/event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body)
    });

    const data = await response.json();

    return {
      success: response.ok,
      data
    };
  } catch (error) {
    console.error("HabitGuard feedback send failed:", error);

    return {
      success: false,
      error: error.message
    };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "HABITGUARD_FEEDBACK_EVENT") {
    return;
  }

  const eventType = message.eventType;
  const payload = message.payload || {};

  if (eventType === "overlay_dismissed") {
    chrome.storage.local.set({
      lastOverlayDismissedAt: Date.now(),
      lastOverlayDismissedPayload: payload
    });
  }

  if (eventType === "break_accepted") {
    const endAt = Date.now() + 5 * 60 * 1000;

    chrome.storage.local.set({
      lastBreakAcceptedAt: Date.now(),
      lastBreakAcceptedPayload: payload,
      activeInterventionTimer: {
        type: "break",
        durationMinutes: 5,
        endAt
      }
    });
  }

  if (eventType === "break_completed" || eventType === "break_skipped") {
    chrome.storage.local.set({
      activeInterventionTimer: null,
      lastBreakEndedAt: Date.now(),
      lastBreakEndReason: eventType,
      lastBreakEndPayload: payload
    });
  }

  sendFeedbackEvent(eventType, payload)
    .then(async (feedbackResult) => {
      await sendUsageSnapshot(null, {
        force: true,
        source: `chrome_extension_feedback_${eventType}`
      });

      return feedbackResult;
    })
    .then(sendResponse);

  return true;
});