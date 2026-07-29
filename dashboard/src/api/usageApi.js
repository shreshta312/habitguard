const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}: ${text.slice(0, 120)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Expected JSON but received: ${text.slice(0, 120)}`);
  }
}

export async function fetchCanonicalUserDashboard(userId = "local_user") {
  const [summaryRes, historyRes, platformsRes, goalRes] = await Promise.all([
    fetch(`${API_BASE_URL}/dashboard/${userId}/summary`),
    fetch(`${API_BASE_URL}/dashboard/${userId}/history?days=7`),
    fetch(`${API_BASE_URL}/dashboard/${userId}/platforms`),
    fetch(`${API_BASE_URL}/dashboard/${userId}/goal`)
  ]);

  const summary = await readJsonResponse(summaryRes);
  const historyData = await readJsonResponse(historyRes);
  const platformsData = await readJsonResponse(platformsRes);
  const goal = await readJsonResponse(goalRes);

  const history = historyData.history || [];
  const platforms = platformsData.platforms || {};

  const sevenDayTrend = history.map((item) => ({
    date: item.date || item.created_at_utc || "Today",
    minutes: toNumber(item.focused_minutes),
    planned_minutes: toNumber(item.planned_minutes),
    unplanned_minutes: toNumber(item.unplanned_minutes)
  }));

  const topDomainsToday = Object.entries(platforms).map(([domain, minutes]) => ({
    domain,
    minutes: toNumber(minutes),
    sessions: 0
  })).sort((a, b) => b.minutes - a.minutes);

  return {
    raw: {
      summary,
      history,
      platforms,
      goal,
      dashboard_ready: true
    },
    todayTotalMinutes: summary.active_usage_minutes || 0,
    unplannedOveruseMinutes: summary.unplanned_overuse_minutes || 0,
    weeklyProgress: summary.weekly_progress || 0,
    sevenDayTrend,
    topDomainsToday,
    topDomainsAllTime: topDomainsToday,
    currentSession: null,
    latestIntervention: {
      usage_status: summary.status || "STABLE",
      overuse_gap_minutes: summary.unplanned_overuse_minutes || 0,
      recommended_timer_minutes: null
    },
    goal
  };
}

export async function fetchUsageSummary(userId = "local_user") {
  try {
    return await fetchCanonicalUserDashboard(userId);
  } catch (err) {
    console.warn("Canonical dashboard endpoints failed, checking fallback:", err);
    throw err;
  }
}