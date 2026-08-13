/**
 * HabitGuard Chrome Extension — shared API configuration & versioning.
 */
const CONFIG_VERSION = "2.0.1";
const SOURCE_VERSIONED_DEFAULT = "VERSIONED_DEFAULT";
const SESSION_RESUME_GAP_MINUTES = 5;
const INTENT_RESUME_GAP_MINUTES = 5;
const IDLE_INTERVAL_SECONDS = 60;
const DOMAIN_SWITCH_GRACE_MS = 10000;
const ALARM_INTERVAL_MINUTES = 1;
const JITAI_CHECK_INTERVAL_MINUTES = 5;
const OFFLINE_QUEUE_KEY = "offlineActivityQueue";
const MAX_OFFLINE_QUEUE = 200;
const DEFAULT_NOTIFICATION_COOLDOWN_MINUTES = 15;
const DEFAULT_OVERLAY_COOLDOWN_MINUTES = 20;

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const RAILWAY_API_BASE_URL = "https://habitguard-production.up.railway.app";

// Explicit default API base URL (Railway production). Override locally via chrome.storage.local.set({ apiBaseUrl: "http://localhost:8000" })
const API_BASE_URL = RAILWAY_API_BASE_URL;

async function getApiBaseUrl() {
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    try {
      const stored = await chrome.storage.local.get(["apiBaseUrl"]);
      if (stored.apiBaseUrl) return stored.apiBaseUrl;
    } catch {
      // Fallback
    }
  }
  return API_BASE_URL;
}

const BUILD_IDENTIFIER = "9b92c33-v2.0.1-config-fix";

async function logRuntimeDiagnostics(contextLabel = "Diagnostics") {
  const manifestVer = (typeof chrome !== "undefined" && chrome.runtime?.getManifest) ? chrome.runtime.getManifest().version : CONFIG_VERSION;
  const runtimeId = (typeof chrome !== "undefined" && chrome.runtime?.id) ? chrome.runtime.id : "standalone";
  const apiBase = await getApiBaseUrl();
  let currentSession = null;
  if (typeof chrome !== "undefined" && chrome.storage?.local) {
    try {
      const stored = await chrome.storage.local.get(["currentSession"]);
      currentSession = stored.currentSession;
    } catch {}
  }
  console.log(`[HabitGuard ${contextLabel}]`, {
    manifestVersion: manifestVer,
    buildIdentifier: BUILD_IDENTIFIER,
    chromeRuntimeId: runtimeId,
    resolvedApiBaseUrl: apiBase,
    activeSessionId: currentSession?.session_id || null,
    activeEpisodeId: currentSession?.episode_id || null,
    activeDomain: currentSession?.domain || null
  });
}
