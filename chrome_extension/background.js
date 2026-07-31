importScripts("config.js");

logRuntimeDiagnostics("Background ServiceWorker Startup");

const TRACKING_ALARM_NAME = "habitguard_usage_tracker";
const JITAI_ALARM_NAME = "habitguard_jitai_checker";
const USAGE_SNAPSHOT_THROTTLE_MS = 2 * 60 * 1000;
const MAX_SESSION_HISTORY = 50;

const DEBUG = true;

let jitaiRunning = false;
let sessionSwitchGeneration = 0;
let sessionSwitchPromise = Promise.resolve();

function debugLog(...args) {
  if (DEBUG) console.log(...args);
}

/**
 * Generate a random provisional episode key.
 * Used to group offline events into logical watching periods.
 * This key is NEVER stored on the backend as a canonical ID.
 */
function generateProvisionalEpisodeKey() {
  const rand = Math.random().toString(36).substr(2, 10);
  return `pek_${Date.now()}_${rand}`;
}

function getTodayKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isTrackableUrl(url) {
  if (!url) return false;
  if (
    url.startsWith("chrome://") ||
    url.startsWith("chrome-extension://") ||
    url.startsWith("devtools://") ||
    url.startsWith("about:") ||
    url.startsWith("view-source:") ||
    url.startsWith("file://")
  ) {
    return false;
  }
  return url.startsWith("http://") || url.startsWith("https://");
}

function getDomain(url) {
  try {
    const parsedUrl = new URL(url);
    return parsedUrl.hostname.replace(/^www\./, "").toLowerCase();
  } catch {
    return "unknown";
  }
}

function getDefaultDomainCategory(domain) {
  const productiveDomains = [
    "leetcode.com", "github.com", "stackoverflow.com", "developer.mozilla.org",
    "docs.python.org", "kaggle.com", "coursera.org", "edx.org",
    "geeksforgeeks.org", "w3schools.com"
  ];
  const temptationDomains = [
    "youtube.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
    "reddit.com", "netflix.com", "primevideo.com", "hotstar.com", "discord.com"
  ];
  const mixedDomains = [
    "chatgpt.com", "google.com", "linkedin.com", "gmail.com", "mail.google.com", "drive.google.com"
  ];

  if (productiveDomains.some((item) => domain.includes(item))) return "productive";
  if (temptationDomains.some((item) => domain.includes(item))) return "temptation";
  if (mixedDomains.some((item) => domain.includes(item))) return "mixed";
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
  try {
    const tabs = await chrome.tabs.query({
      active: true,
      lastFocusedWindow: true
    });
    if (tabs && tabs.length > 0) return tabs[0];
  } catch {}

  try {
    const tabs = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });
    if (tabs && tabs.length > 0) return tabs[0];
  } catch {}

  return null;
}

async function isSystemActive() {
  return new Promise((resolve) => {
    if (!chrome.idle || !chrome.idle.queryState) {
      resolve(true);
      return;
    }
    chrome.idle.queryState(IDLE_INTERVAL_SECONDS || 60, (state) => {
      resolve(state === "active");
    });
  });
}

async function getStoredUsage() {
  const stored = await chrome.storage.local.get([
    "dailyUsageMinutes",
    "domainUsageMinutes",
    "currentSession",
    "sessionHistory",
    "userDomainCategories",
    OFFLINE_QUEUE_KEY,
    "offlineQueueDiagnostics"
  ]);
  return {
    dailyUsageMinutes: stored.dailyUsageMinutes || {},
    domainUsageMinutes: stored.domainUsageMinutes || {},
    currentSession: stored.currentSession || null,
    sessionHistory: stored.sessionHistory || [],
    userDomainCategories: stored.userDomainCategories || {},
    offlineQueue: stored[OFFLINE_QUEUE_KEY] || [],
    offlineQueueDiagnostics: stored.offlineQueueDiagnostics || { totalEnqueued: 0, totalFlushed: 0, totalDropped: 0 }
  };
}

function closeCurrentSession(currentSession, sessionHistory, endedAt) {
  if (!currentSession) return sessionHistory;
  const completedSession = {
    ...currentSession,
    endedAt,
    durationMinutes: currentSession.sessionMinutes || 0
  };
  const updatedHistory = [completedSession, ...sessionHistory];
  return updatedHistory.slice(0, MAX_SESSION_HISTORY);
}

let lastUnfocusedSessionId = null;

function isExtensionTransientUrl(url) {
  if (!url) return true;
  const lower = url.toLowerCase();
  return (
    lower.startsWith("chrome-extension://") ||
    lower.startsWith("devtools://") ||
    lower.startsWith("chrome-devtools://") ||
    lower.startsWith("chrome://") ||
    lower.startsWith("about:")
  );
}

async function notifySessionUnfocused(sessionId) {
  if (!sessionId || sessionId === lastUnfocusedSessionId) return false;

  lastUnfocusedSessionId = sessionId;

  try {
    const apiBase = await getApiBaseUrl();
    const response = await fetch(`${apiBase}/sessions/${sessionId}/unfocus`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });

    if (!response.ok) {
      lastUnfocusedSessionId = null;
      console.warn(`[HabitGuard] unfocus rejected: ${response.status}`);
      return false;
    }

    return true;
  } catch (error) {
    lastUnfocusedSessionId = null;
    console.warn("[HabitGuard] unfocus notification failed:", error);
    return false;
  }
}

/**
 * Authoritative background function to reconcile active browser session.
 * Mutex serialized to prevent race conditions during rapid domain switches.
 */
async function reconcileActiveSession(reason) {
  sessionSwitchPromise = sessionSwitchPromise
    .then(() => _doReconcileActiveSession(reason))
    .catch((err) => {
      console.error("[HabitGuard] reconcile error:", err);
    });
  return sessionSwitchPromise;
}

async function _doReconcileActiveSession(reason) {
  const generation = ++sessionSwitchGeneration;
  console.log(`[HabitGuard] reconcile reason: ${reason}`);
  console.log(`[HabitGuard] switch generation: ${generation}`);

  const activeTab = await getActiveTab();
  const rawUrl = activeTab ? activeTab.url : null;

  let windowFocused = false;
  if (activeTab && activeTab.windowId !== undefined) {
    try {
      const win = await chrome.windows.get(activeTab.windowId);
      windowFocused = win.focused && win.type === "normal" && win.state !== "minimized";
    } catch {
      windowFocused = false;
    }
  }

  const { currentSession, sessionHistory, userDomainCategories } = await getStoredUsage();
  const storedDomain = currentSession ? currentSession.domain : null;
  console.log(`[HabitGuard] stored domain: ${storedDomain || "none"}`);

  // Rule A: EXTENSION_TRANSIENT (popup, extension pages, devtools, chrome://)
  if (isExtensionTransientUrl(rawUrl)) {
    console.log(`[HabitGuard] active domain: transient extension page/popup (session preserved)`);
    return currentSession;
  }

  // Rule B: GENUINELY_UNFOCUSED (window unfocused, minimized, WINDOW_ID_NONE)
  if (!windowFocused) {
    console.log(`[HabitGuard] active domain: null (genuinely unfocused / minimized)`);
    if (currentSession && currentSession.session_id) {
      notifySessionUnfocused(currentSession.session_id);
    }
    return currentSession;
  }

  const activeDomain = getDomain(rawUrl);
  console.log(`[HabitGuard] active domain: ${activeDomain}`);
  lastUnfocusedSessionId = null;

  // Rule C: DIFFERENT_TRACKABLE_DOMAIN (session switch)
  if (currentSession && currentSession.domain && currentSession.domain !== activeDomain) {
    if (currentSession.session_id) {
      notifySessionUnfocused(currentSession.session_id);
    }
  }

  // Do not track dev localhost/127.0.0.1 unless user explicitly categorized it
  if ((activeDomain === "localhost" || activeDomain === "127.0.0.1") && !userDomainCategories[activeDomain]) {
    console.log(`[HabitGuard] active domain: ${activeDomain} ignored (dev server)`);
    return currentSession;
  }

  // Same domain and session active
  if (currentSession && currentSession.domain === activeDomain) {
    const now = Date.now();
    const gapMinutes = (now - (currentSession.lastUpdatedAt || now)) / (1000 * 60);
    if (gapMinutes <= SESSION_RESUME_GAP_MINUTES) {
      return currentSession;
    }
  }

  // Domain changed or gap reset: perform session switch
  const category = await getDomainCategory(activeDomain);
  const now = Date.now();
  const updatedHistory = (currentSession && currentSession.domain !== activeDomain)
    ? closeCurrentSession(currentSession, sessionHistory, now)
    : sessionHistory;

  let newSession = null;
  try {
    const browserTimezone = (typeof Intl !== "undefined" && Intl.DateTimeFormat)
      ? (Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC")
      : "UTC";

    const apiBase = await getApiBaseUrl();
    const response = await fetch(`${apiBase}/sessions/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: "local_user",
        domain: activeDomain,
        purpose: "unknown",
        intended_minutes: null,
        timer_mode: "no_timer",
        remember_today: true,
        local_timezone: browserTimezone
      })
    });

    if (response.ok) {
      const data = await parseApiResponse(response);

      // Race prevention check 1: generation check
      if (generation !== sessionSwitchGeneration) {
        console.log(`[HabitGuard] stale switch discarded`);
        return currentSession;
      }

      // Race prevention check 2: re-query active domain
      const recheckTab = await getActiveTab();
      const recheckDomain = recheckTab ? getDomain(recheckTab.url) : null;
      if (recheckDomain !== activeDomain) {
        console.log(`[HabitGuard] stale switch discarded`);
        return currentSession;
      }

      newSession = {
        session_id: data.session_id,
        episode_id: data.episode_id || (data.intent && data.intent.episode_id),
        domain: activeDomain,
        category: category,
        startedAt: now,
        lastUpdatedAt: now,
        sessionMinutes: 0,
        episodeFocusedMinutes: data.episode_focused_minutes || 0,
        intentPurpose: data.intent?.purpose || "unknown",
        intendedMinutes: data.intent?.effective_planned_minutes ?? data.intent?.original_intended_minutes ?? data.intent?.intended_minutes ?? null
      };

      await chrome.storage.local.set({
        currentSession: newSession,
        sessionHistory: updatedHistory
      });

      console.log(`[HabitGuard] session committed`);
      return newSession;
    }
  } catch (err) {
    console.error("[HabitGuard] reconcile session start error:", err);
  }

  // Local fallback if fetch failed during switch
  if (generation === sessionSwitchGeneration) {
    const now2 = Date.now();

    // Determine whether this fallback is a continuation of an existing fallback
    // or a fresh one. The provisional_episode_key is rotated when:
    //   (a) the domain changes, OR
    //   (b) the gap since the fallback started exceeds SESSION_RESUME_GAP_MINUTES.
    let fallbackSessionId = null;
    let provisionalEpisodeKey = generateProvisionalEpisodeKey(); // default: fresh key
    let offlineFallbackStartedAt = now2;                         // default: now

    if (currentSession && currentSession.domain === activeDomain) {
      if (currentSession.canonicalState === "OFFLINE_FALLBACK") {
        const fallbackStartedAt = currentSession.offlineFallbackStartedAt || currentSession.startedAt || now2;
        const gapMs = now2 - fallbackStartedAt;
        const gapMins = gapMs / (1000 * 60);
        if (gapMins <= (SESSION_RESUME_GAP_MINUTES || 5)) {
          // Within gap threshold: continue same fallback, reuse same key and start time
          fallbackSessionId      = currentSession.session_id || null;
          provisionalEpisodeKey  = currentSession.provisionalEpisodeKey || generateProvisionalEpisodeKey();
          offlineFallbackStartedAt = fallbackStartedAt;
        }
        // gap exceeded: new key + new startedAt (rotation)
      }
      // existing canonical session while offline: do not reuse session_id; generate fresh key
    }

    newSession = {
      session_id: fallbackSessionId,
      episode_id: null,
      domain: activeDomain,
      category: category,
      startedAt: now2,
      lastUpdatedAt: now2,
      sessionMinutes: (currentSession && currentSession.domain === activeDomain) ? currentSession.sessionMinutes : 0,
      intentPurpose: "unknown",
      intendedMinutes: null,
      canonicalState: "OFFLINE_FALLBACK",
      offlineFallbackStartedAt: offlineFallbackStartedAt,
      provisionalEpisodeKey: provisionalEpisodeKey
    };
    await chrome.storage.local.set({ currentSession: newSession, sessionHistory: updatedHistory });
    console.warn(`[HabitGuard] canonical session start failed; offline fallback key=${provisionalEpisodeKey}`);
    return newSession;
  }

  return currentSession;
}

async function incrementUsageMinute() {
  const currentSession = await reconcileActiveSession("heartbeat");

  const activeTab = await getActiveTab();
  if (!activeTab || !isTrackableUrl(activeTab.url)) return;

  try {
    const windowInfo = await chrome.windows.get(activeTab.windowId);
    if (!windowInfo.focused || windowInfo.type !== "normal") return;
  } catch {
    return;
  }

  const activeState = await isSystemActive();
  if (!activeState) return;

  const todayKey = getTodayKey();
  const domain = getDomain(activeTab.url);
  const category = await getDomainCategory(domain);

  const {
    dailyUsageMinutes,
    domainUsageMinutes,
    sessionHistory
  } = await getStoredUsage();

  dailyUsageMinutes[todayKey] = (dailyUsageMinutes[todayKey] || 0) + 1;
  if (!domainUsageMinutes[todayKey]) domainUsageMinutes[todayKey] = {};
  domainUsageMinutes[todayKey][domain] = (domainUsageMinutes[todayKey][domain] || 0) + 1;

  const now = Date.now();
  const updatedSession = currentSession ? {
    ...currentSession,
    lastUpdatedAt: now,
    sessionMinutes: (currentSession.sessionMinutes || 0) + 1
  } : {
    session_id: null,
    domain,
    category,
    startedAt: now,
    lastUpdatedAt: now,
    sessionMinutes: 1
  };

  await chrome.storage.local.set({
    dailyUsageMinutes,
    domainUsageMinutes,
    currentSession: updatedSession
  });

  // Send activity batch to canonical backend if session_id is valid
  if (updatedSession.session_id) {
    const clientEventId = `evt_${now}_${Math.random().toString(36).substr(2, 6)}`;
    const activity = {
      event_type: "focus_heartbeat",
      focused_duration_ms: 60000,
      client_event_id: clientEventId,
      event_timestamp_utc: new Date().toISOString()
    };
    const sent = await sendActivityBatch(updatedSession.session_id, [activity]);
    if (!sent) {
      await enqueueOfflineActivity(updatedSession.session_id, activity, domain, "local_user");
    }
  } else {
    // No canonical session_id yet (offline fallback): enqueue with null session_id
    // and domain so that flushOfflineQueue can reconcile after reconnect.
    const clientEventId = `evt_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    const activity = {
      event_type: "focus_heartbeat",
      focused_duration_ms: 60000,
      client_event_id: clientEventId,
      event_timestamp_utc: new Date().toISOString()
    };
    await enqueueOfflineActivity(null, activity, domain, "local_user");
  }
}

function mergeCanonicalSessionIntent(currentSession, canonicalData) {
  if (!canonicalData) return currentSession;
  const canonicalIntent = canonicalData.intent || {
    episode_id: canonicalData.episode_id,
    purpose: canonicalData.purpose || canonicalData.classification || "unknown",
    original_intended_minutes: canonicalData.original_intended_minutes ?? null,
    extension_minutes: canonicalData.extension_minutes ?? 0.0,
    effective_planned_minutes: canonicalData.effective_planned_minutes ?? null,
    timer_mode: canonicalData.timer_mode || (canonicalData.effective_planned_minutes ? "planned" : "no_timer"),
    episode_status: canonicalData.session_status === "NO_PLAN" ? "NO_PLAN" : "ACTIVE"
  };

  const canonicalEpisodeId = canonicalData.episode_id || canonicalIntent.episode_id;
  const currentEpisodeId = currentSession ? (currentSession.episode_id || currentSession.intent?.episode_id) : null;

  if (!currentSession || (canonicalEpisodeId && currentEpisodeId && canonicalEpisodeId !== currentEpisodeId)) {
    // New episode or episode mismatch: replace intent completely
    return {
      ...currentSession,
      session_id: canonicalData.session_id || currentSession?.session_id,
      episode_id: canonicalEpisodeId,
      domain: canonicalData.domain || currentSession?.domain,
      episodeFocusedMinutes: canonicalData.episode_focused_minutes ?? canonicalData.focused_minutes ?? currentSession?.episodeFocusedMinutes ?? 0,
      intentPurpose: canonicalIntent.purpose || "unknown",
      intendedMinutes: canonicalIntent.effective_planned_minutes ?? canonicalIntent.original_intended_minutes ?? null,
      intent: canonicalIntent
    };
  } else {
    // Same episode: retain existing purpose if canonicalIntent.purpose is missing/unknown, but update intent fields
    const mergedPurpose = (canonicalIntent.purpose && canonicalIntent.purpose !== "unknown")
      ? canonicalIntent.purpose
      : (currentSession.intent?.purpose || currentSession.intentPurpose || "unknown");

    const mergedIntended = canonicalIntent.effective_planned_minutes ?? canonicalIntent.original_intended_minutes ?? currentSession.intendedMinutes;

    const mergedIntent = {
      ...currentSession.intent,
      ...canonicalIntent,
      purpose: mergedPurpose,
      effective_planned_minutes: mergedIntended
    };

    return {
      ...currentSession,
      session_id: canonicalData.session_id || currentSession.session_id,
      episode_id: canonicalEpisodeId || currentSession.episode_id,
      episodeFocusedMinutes: canonicalData.episode_focused_minutes ?? canonicalData.focused_minutes ?? currentSession.episodeFocusedMinutes,
      intentPurpose: mergedPurpose,
      intendedMinutes: mergedIntended,
      intent: mergedIntent
    };
  }
}

/**
 * Send a batch of activities to the canonical backend.
 * Returns true on HTTP 200-299, false on network error.
 */
async function sendActivityBatch(sessionId, activities) {
  try {
    const apiBase = await getApiBaseUrl();
    const stored = await chrome.storage.local.get(["currentSession"]);
    const currentCategory = stored.currentSession?.category || "neutral";

    const response = await fetch(`${apiBase}/sessions/${sessionId}/activity/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ activities, current_category: currentCategory })
    });
    if (response.ok) {
      const batchData = await parseApiResponse(response);
      await consumeCanonicalDecision(batchData, "activity_heartbeat");
      return true;
    }
    // Session expired (404) on backend: return true so caller does not queue dead session events
    if (response.status === 404) return true;
    return false;
  } catch (err) {
    // Network error — tell caller to enqueue
    return false;
  }
}

/**
 * Add an activity event to persistent offline queue in chrome.storage.local.
 * Preserves original client_event_id, event_timestamp_utc, focused_duration_ms,
 * domain, user_id, and provisional_episode_key.
 * session_id may be null for events recorded during a long-gap offline period.
 */
async function enqueueOfflineActivity(sessionId, activity, domainOverride, userIdOverride) {
  const { offlineQueue, offlineQueueDiagnostics, currentSession } = await getStoredUsage();
  const newDiagnostics = { ...offlineQueueDiagnostics };

  // Capture the current provisional episode key from storage so the flush
  // can group events into the correct logical offline period.
  const provisionalEpisodeKey = currentSession?.provisionalEpisodeKey || null;

  const item = {
    // Identity — may be null when recorded after a long-gap expiry.
    session_id: sessionId || null,
    provisional_session_id: sessionId || null,   // preserved for audit
    // Grouping key — opaque, never sent to backend as a canonical ID.
    provisional_episode_key: provisionalEpisodeKey,
    // Payload — never rewritten after enqueueing.
    client_event_id: activity.client_event_id,
    event_timestamp_utc: activity.event_timestamp_utc || new Date().toISOString(),
    event_type: activity.event_type || "focus_heartbeat",
    focused_duration_ms: activity.focused_duration_ms || 60000,
    // Routing context — needed to obtain a fresh session on reconciliation.
    domain: domainOverride || activity.domain || null,
    user_id: userIdOverride || "local_user",
    retry_count: 0,
    enqueue_timestamp: new Date().toISOString()
  };

  offlineQueue.push(item);
  newDiagnostics.totalEnqueued = (newDiagnostics.totalEnqueued || 0) + 1;

  // Enforce queue limit: drop oldest
  if (offlineQueue.length > MAX_OFFLINE_QUEUE) {
    const overflow = offlineQueue.length - MAX_OFFLINE_QUEUE;
    offlineQueue.splice(0, overflow);
    newDiagnostics.totalDropped = (newDiagnostics.totalDropped || 0) + overflow;
  }

  await chrome.storage.local.set({
    [OFFLINE_QUEUE_KEY]: offlineQueue,
    offlineQueueDiagnostics: newDiagnostics
  });
  debugLog(`HabitGuard persistent queue: ${offlineQueue.length} pending events`);
}

/**
 * Flush persistent offline queue.
 *
 * Algorithm:
 * A. Events with a canonical session_id are sent directly to that session.
 *    Removed from queue only after successful HTTP 200.
 *    Retained with incremented retry_count on failure.
 *
 * B. Events with session_id = null are grouped by provisional_episode_key
 *    (not by domain alone). Two YouTube periods separated by more than
 *    SESSION_RESUME_GAP_MINUTES produce different keys and therefore
 *    reconcile into separate canonical episodes.
 *
 *    For each provisional group:
 *    1. Call POST /sessions/reconcile-offline with the group's events,
 *       the earliest event timestamp as started_at_utc, and the group's domain.
 *    2. The backend atomically creates a fresh episode + technical session with
 *       started_at_utc = that earliest timestamp. FocusedUsageTracker never
 *       rejects these events because the session pre-dates them.
 *    3. On success: remove only the accepted event IDs from the queue.
 *       Mark rejected events with a failure_reason and retain them.
 *    4. On network/server failure: retain all events with retry_count++.
 *    5. After reconciliation, update current provisional runtime state ONLY
 *       when the reconciled key matches the currently active provisional key.
 *       Historical keys must NOT become the current session.
 *
 * Invariants:
 *  - Original client_event_id and event_timestamp_utc are never rewritten.
 *  - Events are removed from queue ONLY after a canonical acceptance.
 *  - A failed transaction leaves the queue entirely intact.
 */
async function flushOfflineQueue() {
  const { offlineQueue, offlineQueueDiagnostics, currentSession } = await getStoredUsage();
  if (!offlineQueue || offlineQueue.length === 0) return;

  const newDiagnostics = { ...offlineQueueDiagnostics };
  const activeProvisionalKey = currentSession?.provisionalEpisodeKey || null;

  // Partition: Group A (canonical session_id) and Group B (provisional key groups)
  const bySession = {};              // session_id -> entries[]
  const byProvisionalKey = {};       // provisional_episode_key -> entries[]

  for (const entry of offlineQueue) {
    const sid = entry.session_id;
    if (sid) {
      if (!bySession[sid]) bySession[sid] = [];
      bySession[sid].push(entry);
    } else {
      // Group B: keyed by provisional_episode_key.
      // Entries without a key get a synthetic fallback key per domain so they
      // still reconcile rather than being retained forever.
      const pek = entry.provisional_episode_key
        || `pek_legacy_${entry.domain || "unknown"}`;
      if (!byProvisionalKey[pek]) byProvisionalKey[pek] = [];
      byProvisionalKey[pek].push(entry);
    }
  }

  // Track which entries to keep after flushing
  const failedEntries = [];

  // --- Group A: flush canonical-session events ---
  for (const [sessionId, entries] of Object.entries(bySession)) {
    const activities = entries.map((e) => ({
      event_type: e.event_type,
      focused_duration_ms: e.focused_duration_ms,
      client_event_id: e.client_event_id,
      event_timestamp_utc: e.event_timestamp_utc   // never rewritten
    }));

    const ok = await sendActivityBatch(sessionId, activities);
    if (ok) {
      newDiagnostics.totalFlushed = (newDiagnostics.totalFlushed || 0) + entries.length;
    } else {
      entries.forEach((e) => { e.retry_count = (e.retry_count || 0) + 1; });
      failedEntries.push(...entries);
    }
  }

  // --- Group B: reconcile provisional groups via /sessions/reconcile-offline ---
  for (const [pek, entries] of Object.entries(byProvisionalKey)) {
    const domain = entries[0]?.domain;
    if (!domain || domain === "__unknown__") {
      // Cannot reconcile without a domain — retain.
      entries.forEach((e) => { e.retry_count = (e.retry_count || 0) + 1; });
      failedEntries.push(...entries);
      continue;
    }

    const userId = entries[0]?.user_id || "local_user";

    // Compute the earliest event timestamp in this group (becomes session started_at_utc).
    let earliestTs = null;
    for (const e of entries) {
      if (!earliestTs || e.event_timestamp_utc < earliestTs) {
        earliestTs = e.event_timestamp_utc;
      }
    }
    if (!earliestTs) {
      entries.forEach((e) => { e.retry_count = (e.retry_count || 0) + 1; });
      failedEntries.push(...entries);
      continue;
    }

    const browserTimezone = (typeof Intl !== "undefined" && Intl.DateTimeFormat)
      ? (Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC")
      : "UTC";

    const activities = entries.map((e) => ({
      client_event_id:      e.client_event_id,
      event_timestamp_utc:  e.event_timestamp_utc,   // NEVER rewritten
      focused_duration_ms:  e.focused_duration_ms,
      event_type:           e.event_type || "focus_heartbeat"
    }));

    let reconcileResult = null;
    try {
      const apiBase = await getApiBaseUrl();
      const res = await fetch(`${apiBase}/sessions/reconcile-offline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id:                 userId,
          domain:                  domain,
          provisional_episode_key: pek,
          started_at_utc:          earliestTs,
          local_timezone:          browserTimezone,
          activities:              activities
        })
      });
      if (res.ok) {
        reconcileResult = await parseApiResponse(res);
      } else {
        console.warn(`[HabitGuard] reconcile-offline HTTP ${res.status} for key=${pek}`);
      }
    } catch (err) {
      console.warn(`[HabitGuard] reconcile-offline network error for key=${pek}:`, err);
    }

    if (!reconcileResult) {
      // Network or server failure — retain entire group intact for next cycle.
      entries.forEach((e) => { e.retry_count = (e.retry_count || 0) + 1; });
      failedEntries.push(...entries);
      continue;
    }

    // Partition accepted vs rejected by the canonical response.
    const acceptedSet = new Set(reconcileResult.accepted_event_ids || []);
    const rejectedMap = {};
    for (const r of (reconcileResult.rejected_events || [])) {
      if (r.client_event_id) rejectedMap[r.client_event_id] = r.reason || "rejected";
    }

    let groupFlushed = 0;
    for (const e of entries) {
      if (acceptedSet.has(e.client_event_id)) {
        // Successfully accepted — remove from queue.
        groupFlushed++;
      } else if (rejectedMap[e.client_event_id]) {
        // Permanently rejected — attach reason and retain for audit but do not retry.
        e.failure_reason = rejectedMap[e.client_event_id];
        e.retry_count = (e.retry_count || 0) + 1;
        failedEntries.push(e);
      } else {
        // Unknown outcome (transient) — retain for retry.
        e.retry_count = (e.retry_count || 0) + 1;
        failedEntries.push(e);
      }
    }
    newDiagnostics.totalFlushed = (newDiagnostics.totalFlushed || 0) + groupFlushed;

    // Update current provisional runtime state ONLY when this reconciled key
    // matches the CURRENTLY ACTIVE provisional episode. Historical keys must NOT
    // overwrite the current session.
    if (pek === activeProvisionalKey && reconcileResult.session_id) {
      const stored = await chrome.storage.local.get(["currentSession"]);
      const cs = stored.currentSession;
      if (cs && cs.provisionalEpisodeKey === pek && cs.canonicalState === "OFFLINE_FALLBACK") {
        await chrome.storage.local.set({
          currentSession: {
            ...cs,
            session_id:    reconcileResult.session_id,
            episode_id:    reconcileResult.episode_id,
            canonicalState: "RECONCILED",
            provisionalEpisodeKey: null   // key consumed
          }
        });
        console.log(`[HabitGuard] offline reconcile: provisional state promoted to ${reconcileResult.session_id}`);
      }
    }
  }

  await chrome.storage.local.set({
    [OFFLINE_QUEUE_KEY]: failedEntries,
    offlineQueueDiagnostics: newDiagnostics
  });

  if (failedEntries.length > 0) {
    debugLog(`HabitGuard queue flush: ${failedEntries.length} events remaining`);
  }
}

async function parseApiResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { raw_response: text };
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
      const dailyHistory = backendHistory.daily_usage_history || [];
      dailyHistory.forEach((item) => {
        if (item.date) mergedUsage[item.date] = Number(item.minutes || 0);
      });
    }
  } catch (error) {
    console.warn("Could not load backend usage history. Using local history only.", error);
  }
  const dates = Object.keys(mergedUsage).sort();
  return dates.map((date) => mergedUsage[date]);
}

function shouldTriggerNotification(intervention) {
  if (!intervention || !intervention.should_intervene) return false;
  const frictionType = intervention.friction_type;
  return (
    frictionType === "SOFT_WARNING" ||
    frictionType === "TIMER_WARNING" ||
    frictionType === "STRONG_FRICTION"
  );
}

function getInterventionCooldownMinutes(intervention, fallbackMinutes) {
  const value = Number(intervention?.cooldown_minutes);
  if (!Number.isFinite(value) || value <= 0) return fallbackMinutes;
  return Math.min(120, Math.max(5, value));
}

async function isNotificationCooldownActive(intervention) {
  const stored = await chrome.storage.local.get(["lastNotificationAt"]);
  const lastNotificationAt = stored.lastNotificationAt;
  if (!lastNotificationAt) return false;
  const elapsedMinutes = (Date.now() - lastNotificationAt) / (1000 * 60);
  const cooldownMinutes = getInterventionCooldownMinutes(intervention, DEFAULT_NOTIFICATION_COOLDOWN_MINUTES);
  return elapsedMinutes < cooldownMinutes;
}

async function recordDeliveryTrace(trace) {
  try {
    const stored = await chrome.storage.local.get(["deliveryTraceHistory"]);
    const history = stored.deliveryTraceHistory || [];
    history.unshift(trace);
    await chrome.storage.local.set({ deliveryTraceHistory: history.slice(0, 50) });

    const apiBase = await getApiBaseUrl();
    await fetch(`${apiBase}/jitai/delivery-trace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(trace)
    }).catch((err) => console.warn("[HabitGuard] trace sync failed:", err));
  } catch (err) {
    console.error("[HabitGuard] recordDeliveryTrace error:", err);
  }
}

async function consumeCanonicalDecision(batchData, source = "activity_heartbeat") {
  if (!batchData) return;

  const stored = await chrome.storage.local.get(["currentSession", "consumedDecisionIds", "lastNotificationAt", "lastOverlayAt"]);
  let currentSession = stored.currentSession;

  // 1. Merge intent safely
  currentSession = mergeCanonicalSessionIntent(currentSession, batchData);

  // 2. Update badge
  await updateBadge(batchData);

  const decisionId = batchData.decision_id || `dec_${Date.now()}`;
  const sessionId = batchData.session_id || currentSession?.session_id || "unknown_session";
  const episodeId = batchData.episode_id || currentSession?.episode_id || null;
  const domain = batchData.domain || currentSession?.domain || "unknown_domain";
  const attemptedAt = new Date().toISOString();

  // 3. Save current session and intervention state
  await chrome.storage.local.set({
    currentSession,
    latestIntervention: batchData,
    latestInterventionCheckedAt: Date.now()
  });

  // 4. Check idempotency
  const consumedIds = new Set(stored.consumedDecisionIds || []);
  const isAlreadyConsumed = consumedIds.has(decisionId);
  consumedIds.add(decisionId);
  await chrome.storage.local.set({ consumedDecisionIds: Array.from(consumedIds).slice(-100) });

  if (isAlreadyConsumed) {
    debugLog(`[HabitGuard] Decision ${decisionId} already consumed. Skipping notification/overlay.`);
    return;
  }

async function updateLatestDeliveryState(decisionId, updates) {
  const stored = await chrome.storage.local.get(["latestIntervention"]);
  const latest = stored.latestIntervention;

  if (!latest || latest.decision_id !== decisionId) return;

  await chrome.storage.local.set({
    latestIntervention: {
      ...latest,
      ...updates
    }
  });
}

  // 5. Handle Native Notification Delivery if independently eligible
  if (batchData.should_notify) {
    const lastNotifAt = stored.lastNotificationAt || 0;
    const notifCooldownMins = getInterventionCooldownMinutes(batchData, DEFAULT_NOTIFICATION_COOLDOWN_MINUTES);
    const notifElapsedMins = (Date.now() - lastNotifAt) / (1000 * 60);

    if (notifElapsedMins < notifCooldownMins) {
      await updateLatestDeliveryState(decisionId, {
        delivery_status: "SUPPRESSED",
        failure_reason: "notification_cooldown_active"
      });
      await recordDeliveryTrace({
        decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
        user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
        fallback_channel: "badge_popup", intervention_preserved: true, should_notify: true,
        should_overlay: false, eligible: false, attempted_at_utc: attemptedAt,
        delivery_status: "SUPPRESSED", failure_reason: "notification_cooldown_active"
      });
    } else {
      if (typeof chrome !== "undefined" && chrome.notifications) {
        const notifId = `hg_notif_${Date.now()}`;
        await recordDeliveryTrace({
          decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
          user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
          fallback_channel: null, intervention_preserved: true, should_notify: true,
          should_overlay: false, eligible: true, attempted_at_utc: attemptedAt,
          delivery_status: "ATTEMPTED", chrome_notification_id: notifId
        });

        try {
          const statusText = batchData.usage_status || "Usage Alert";
          const timerVal = batchData.recommended_remaining || batchData.recommended_timer_minutes;
          let msgText = batchData.message || "HabitGuard recommends taking a short break.";
          if (timerVal !== null && timerVal !== undefined) {
            msgText = `${msgText} Suggested timer: ${timerVal} min.`;
          }

          chrome.notifications.create(notifId, {
            type: "basic", iconUrl: "icon128.png", title: `HabitGuard: ${statusText}`,
            message: msgText, priority: 2
          }, async (createdId) => {
            if (chrome.runtime.lastError) {
              await updateLatestDeliveryState(decisionId, {
                delivery_status: "PERMISSION_DENIED",
                failure_reason: chrome.runtime.lastError.message
              });
              await recordDeliveryTrace({
                decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
                user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
                fallback_channel: "badge_popup", intervention_preserved: true, should_notify: true,
                should_overlay: false, eligible: true, attempted_at_utc: attemptedAt,
                delivery_status: "PERMISSION_DENIED", failure_reason: chrome.runtime.lastError.message
              });
            } else {
              await chrome.storage.local.set({ lastNotificationAt: Date.now() });
              await updateLatestDeliveryState(decisionId, {
                delivery_status: "API_ACCEPTED",
                chrome_notification_id: createdId || notifId,
                failure_reason: null
              });
              await recordDeliveryTrace({
                decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
                user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
                fallback_channel: null, intervention_preserved: true, should_notify: true,
                should_overlay: false, eligible: true, attempted_at_utc: attemptedAt,
                delivery_status: "API_ACCEPTED", chrome_notification_id: createdId || notifId
              });
            }
          });
        } catch (err) {
          await updateLatestDeliveryState(decisionId, {
            delivery_status: "FAILED",
            failure_reason: String(err)
          });
          await recordDeliveryTrace({
            decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
            user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
            fallback_channel: "badge_popup", intervention_preserved: true, should_notify: true,
            should_overlay: false, eligible: true, attempted_at_utc: attemptedAt,
            delivery_status: "FAILED", failure_reason: String(err)
          });
        }
      } else {
        // chrome.notifications API is missing: record PERMISSION_DENIED and update
        // latestIntervention so the popup is never left in a pending state.
        await updateLatestDeliveryState(decisionId, {
          delivery_status: "PERMISSION_DENIED",
          failure_reason: "chrome.notifications API missing",
          fallback_channel: "badge_popup"
        });
        await recordDeliveryTrace({
          decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
          user_id: "local_user", domain, channel: "notification", requested_channel: "notification",
          fallback_channel: "badge_popup", intervention_preserved: true, should_notify: true,
          should_overlay: false, eligible: true, attempted_at_utc: attemptedAt,
          delivery_status: "PERMISSION_DENIED", failure_reason: "chrome.notifications API missing"
        });
      }
    }
  }

  // 6. Handle Overlay Delivery if independently eligible
  if (batchData.should_overlay) {
    const lastOverlayAt = stored.lastOverlayAt || 0;
    const overlayCooldownMins = getInterventionCooldownMinutes(batchData, 15);
    const overlayElapsedMins = (Date.now() - lastOverlayAt) / (1000 * 60);

    if (overlayElapsedMins < overlayCooldownMins) {
      await recordDeliveryTrace({
        decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
        user_id: "local_user", domain, channel: "overlay", requested_channel: "overlay",
        fallback_channel: "badge_popup", intervention_preserved: true, should_notify: false,
        should_overlay: true, eligible: false, attempted_at_utc: attemptedAt,
        delivery_status: "SUPPRESSED", failure_reason: "overlay_cooldown_active"
      });
    } else {
      const activeTab = await getActiveTab();
      if (activeTab && activeTab.url && isTrackableUrl(activeTab.url)) {
        const activeTabDomain = getDomain(activeTab.url);
        if (activeTabDomain === domain) {
          try {
            await chrome.tabs.sendMessage(activeTab.id, {
              type: "SHOW_HABITGUARD_OVERLAY",
              payload: {
                domain,
                category: currentSession?.category || batchData.current_category || "neutral",
                sessionMinutes: batchData.focused_minutes || currentSession?.sessionMinutes || 0,
                timerMinutes: batchData.recommended_remaining || batchData.recommended_timer_minutes || null,
                frictionType: batchData.friction_type,
                message: batchData.message
              }
            });
            await chrome.storage.local.set({ lastOverlayAt: Date.now() });
            await recordDeliveryTrace({
              decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
              user_id: "local_user", domain, channel: "overlay", requested_channel: "overlay",
              fallback_channel: null, intervention_preserved: true, should_notify: false,
              should_overlay: true, eligible: true, attempted_at_utc: attemptedAt,
              delivery_status: "API_ACCEPTED"
            });
          } catch (err) {
            await recordDeliveryTrace({
              decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
              user_id: "local_user", domain, channel: "overlay", requested_channel: "overlay",
              fallback_channel: "badge_popup", intervention_preserved: true, should_notify: false,
              should_overlay: true, eligible: true, attempted_at_utc: attemptedAt,
              delivery_status: "FAILED", failure_reason: String(err)
            });
          }
        } else {
          await recordDeliveryTrace({
            decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
            user_id: "local_user", domain, channel: "overlay", requested_channel: "overlay",
            fallback_channel: "badge_popup", intervention_preserved: true, should_notify: false,
            should_overlay: true, eligible: false, attempted_at_utc: attemptedAt,
            delivery_status: "SUPPRESSED", failure_reason: "active_tab_domain_mismatch"
          });
        }
      } else {
        await recordDeliveryTrace({
          decision_id: decisionId, session_id: sessionId, episode_id: episodeId,
          user_id: "local_user", domain, channel: "overlay", requested_channel: "overlay",
          fallback_channel: "badge_popup", intervention_preserved: true, should_notify: false,
          should_overlay: true, eligible: false, attempted_at_utc: attemptedAt,
          delivery_status: "SUPPRESSED", failure_reason: "no_trackable_active_tab"
        });
      }
    }
  }
}

async function showInterventionNotification(intervention) {
  await consumeCanonicalDecision(intervention, "manual");
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
      return { success: true, skipped: true, reason: "throttled" };
    }

    const apiBase = await getApiBaseUrl();
    const body = {
      user_id: "local_user",
      date: todayKey,
      daily_usage_minutes: stored.dailyUsageMinutes || {},
      domain_usage_minutes: stored.domainUsageMinutes || {},
      current_session: stored.currentSession || null,
      session_history: stored.sessionHistory || [],
      latest_intervention: latestIntervention || stored.latestIntervention || null,
      active_intervention_timer: stored.activeInterventionTimer || null,
      source
    };

    const response = await fetch(`${apiBase}/usage/snapshot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await parseApiResponse(response);
    const result = { success: response.ok, status: response.status, data };
    await chrome.storage.local.set({
      lastUsageSnapshotAt: response.ok ? now : stored.lastUsageSnapshotAt || null,
      lastUsageSnapshotResult: result
    });
    return result;
  } catch (error) {
    console.error("HabitGuard usage snapshot failed:", error);
    return { success: false, error: error.message };
  }
}

async function runJitaiCheck() {
  if (jitaiRunning) return;
  jitaiRunning = true;
  try {
    const currentSession = await reconcileActiveSession("jitai_check");

    if (currentSession && currentSession.session_id) {
      const apiBase = await getApiBaseUrl();
      const currentCategory = currentSession.category || "neutral";
      const res = await fetch(`${apiBase}/sessions/${currentSession.session_id}/activity/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ activities: [], current_category: currentCategory })
      });
      if (res.ok) {
        const intervention = await parseApiResponse(res);
        await consumeCanonicalDecision(intervention, "jitai_check");
        await sendUsageSnapshot(intervention, { source: "chrome_extension_jitai_check" });
      }
    }

    await flushOfflineQueue();
  } catch (error) {
    console.error("HabitGuard JITAI check failed:", error);
  } finally {
    jitaiRunning = false;
  }
}

async function startAlarms() {
  await chrome.alarms.clearAll();
  await chrome.alarms.create(TRACKING_ALARM_NAME, { periodInMinutes: ALARM_INTERVAL_MINUTES || 1 });
  await chrome.alarms.create(JITAI_ALARM_NAME, { periodInMinutes: JITAI_CHECK_INTERVAL_MINUTES || 5 });
}

async function sendFeedbackEvent(eventType, payload = {}) {
  const { currentSession } = await getStoredUsage();
  const sessionId = (currentSession && currentSession.session_id) ? currentSession.session_id : null;

  let actionName = eventType;
  let taskCompletion = payload.task_completion || null;
  let timeSufficient = payload.time_sufficient || null;

  if (eventType === "overlay_dismissed") {
    actionName = "dismiss";
  } else if (eventType === "break_accepted") {
    actionName = "extend_5";
  } else if (eventType === "task_not_finished") {
    actionName = "task_not_finished";
    taskCompletion = "not_completed";
    timeSufficient = "insufficient";
  } else if (eventType === "finish") {
    actionName = "finish";
    taskCompletion = "unknown";
    timeSufficient = "unknown";
  } else if (eventType === "stop_reminders") {
    actionName = "stop_reminders";
  }

  if (sessionId) {
    try {
      const apiBase = await getApiBaseUrl();
      const canonicalRes = await fetch(`${apiBase}/sessions/${sessionId}/action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: actionName,
          task_completion: taskCompletion,
          time_sufficient: timeSufficient
        })
      });
      const canonicalData = await parseApiResponse(canonicalRes);
      debugLog("HabitGuard canonical action recorded:", canonicalData);
    } catch (err) {
      console.error("HabitGuard canonical action failed:", err);
    }
  }

  const body = {
    user_id: payload.user_id || "local_user",
    event_type: eventType,
    site: payload.site || payload.domain || null,
    category: payload.category || null,
    overlay_id: payload.overlay_id || null,
    decision: payload.decision || null,
    reason: payload.reason || null,
    timestamp: new Date().toISOString(),
    context: {
      ...payload.context,
      domain: payload.domain || null,
      sessionMinutes: payload.sessionMinutes || null,
      timerMinutes: payload.timerMinutes || null,
      frictionType: payload.frictionType || payload.friction_type || null,
      status: payload.status || null
    }
  };

  try {
    const apiBase = await getApiBaseUrl();
    const response = await fetch(`${apiBase}/feedback/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const data = await parseApiResponse(response);
    return { success: response.ok, data };
  } catch (error) {
    console.error("HabitGuard feedback send failed:", error);
    return { success: false, error: error.message };
  }
}

// ── Tab & Window listeners for instant session synchronization ─────────────

chrome.tabs.onActivated.addListener(async () => {
  await reconcileActiveSession("tab_activated");
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.url && tab.active) {
    await reconcileActiveSession("tab_updated");
  }
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    const { currentSession } = await getStoredUsage();
    if (currentSession && currentSession.session_id) {
      await notifySessionUnfocused(currentSession.session_id);
    }
  } else {
    try {
      const win = await chrome.windows.get(windowId);
      if (win.state === "minimized") {
        const { currentSession } = await getStoredUsage();
        if (currentSession && currentSession.session_id) {
          await notifySessionUnfocused(currentSession.session_id);
        }
      } else {
        await reconcileActiveSession("window_focused");
      }
    } catch {
      await reconcileActiveSession("window_focused");
    }
  }
});

if (typeof chrome !== "undefined" && chrome.idle && chrome.idle.onStateChanged) {
  chrome.idle.onStateChanged.addListener(async (newState) => {
    if (newState === "idle" || newState === "locked") {
      const { currentSession } = await getStoredUsage();
      if (currentSession && currentSession.session_id) {
        await notifySessionUnfocused(currentSession.session_id);
      }
    }
  });
}

chrome.runtime.onInstalled.addListener(() => { startAlarms(); });
chrome.runtime.onStartup.addListener(() => { startAlarms(); });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === TRACKING_ALARM_NAME) incrementUsageMinute();
  if (alarm.name === JITAI_ALARM_NAME) runJitaiCheck();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) return;

  if (message.type === "RECONCILE_ACTIVE_SESSION") {
    reconcileActiveSession("popup_refresh").then((session) => {
      sendResponse({ session });
    });
    return true;
  }

  if (message.type === "HANDLE_CANONICAL_RESPONSE") {
    (async () => {
      const canonicalData = message.data;
      const stored = await chrome.storage.local.get(["currentSession"]);
      const updatedSess = mergeCanonicalSessionIntent(stored.currentSession, canonicalData);
      const checkedAt = Date.now();
      await chrome.storage.local.set({
        currentSession: updatedSess,
        latestIntervention: canonicalData,
        latestInterventionCheckedAt: checkedAt
      });
      await updateBadge(canonicalData);
      if (canonicalData.should_intervene && shouldTriggerNotification(canonicalData)) {
        await showInterventionNotification(canonicalData);
      }
      sendResponse({ status: "success", session: updatedSess });
    })();
    return true;
  }

  if (message.type === "PROCESS_DECISION") {
    showInterventionNotification(message.decision).then(() => {
      sendResponse({ status: "processed" });
    });
    return true;
  }

  if (message.type === "GET_OFFLINE_QUEUE_DEBUG") {
    getStoredUsage().then(({ offlineQueue, offlineQueueDiagnostics }) => {
      sendResponse({
        queueLength: (offlineQueue || []).length,
        diagnostics: offlineQueueDiagnostics,
        queue: offlineQueue || []
      });
    });
    return true;
  }

  if (message.type === "HABITGUARD_OVERLAY_DISMISSED") {
    chrome.storage.local.set({
      lastOverlayDismissedAt: Date.now(),
      lastOverlayDismissedPayload: message.payload || null
    });
    return;
  }

  if (message.type === "HABITGUARD_BREAK_ACCEPTED") {
    const endAt = Date.now() + 5 * 60 * 1000;
    chrome.storage.local.set({
      lastBreakAcceptedAt: Date.now(),
      lastBreakAcceptedPayload: message.payload || null,
      activeInterventionTimer: { type: "break", durationMinutes: 5, endAt }
    });
    return;
  }

  if (message.type === "HABITGUARD_FEEDBACK_EVENT") {
    const eventType = message.eventType;
    const payload = message.payload || {};

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
  }
});

chrome.notifications.onClicked.addListener((notificationId) => {
  chrome.notifications.clear(notificationId);
  chrome.tabs.create({ url: chrome.runtime.getURL("popup.html") });
});