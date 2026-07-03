const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null);
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function normalizeTrend(value) {
  if (!value) return [];

  if (Array.isArray(value)) {
    return value
      .map((row, index) => ({
        date: row.date || row.day || row.label || `Day ${index + 1}`,
        minutes: toNumber(
          firstDefined(
            row.minutes,
            row.usage_minutes,
            row.total_minutes,
            row.totalUsageMinutes,
            row.value
          )
        ),
      }))
      .slice(-7);
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([date, minutes]) => ({
        date,
        minutes: toNumber(minutes),
      }))
      .slice(-7);
  }

  return [];
}

function normalizeDomains(value) {
  if (!value) return [];

  if (Array.isArray(value)) {
    return value
      .map((row) => ({
        domain: row.domain || row.name || row.site || row.app || "Unknown",
        minutes: toNumber(
          firstDefined(
            row.minutes,
            row.usage_minutes,
            row.total_minutes,
            row.totalUsageMinutes,
            row.value
          )
        ),
        sessions: toNumber(firstDefined(row.sessions, row.session_count, 0)),
      }))
      .sort((a, b) => b.minutes - a.minutes);
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([domain, minutes]) => ({
        domain,
        minutes: toNumber(minutes),
        sessions: 0,
      }))
      .sort((a, b) => b.minutes - a.minutes);
  }

  return [];
}

function normalizeObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value;
}

export async function fetchUsageSummary() {
  const response = await fetch(`${API_BASE_URL}/usage/summary/local_user`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  const raw = await response.json();

  const todayTotalMinutes = toNumber(
    firstDefined(
      raw.today_total_usage_minutes,
      raw.today_total_minutes,
      raw.todayUsageMinutes,
      raw.dailyUsageMinutes,
      raw.today?.total_minutes,
      raw.today?.usage_minutes,
      0
    )
  );

  const sevenDayTrend = normalizeTrend(
    firstDefined(
      raw.seven_day_usage_trend,
      raw.usage_trend_7d,
      raw.usage_trend_7_days,
      raw.daily_usage_last_7_days,
      raw.last_7_days,
      raw.daily_usage,
      raw.dailyUsageMinutes
    )
  );

  const topDomainsToday = normalizeDomains(
    firstDefined(
      raw.top_domains_today,
      raw.today_top_domains,
      raw.today?.top_domains,
      raw.domainUsageMinutesToday,
      raw.domain_usage_today
    )
  );

  const topDomainsAllTime = normalizeDomains(
    firstDefined(
      raw.top_domains_all_time,
      raw.all_time_top_domains,
      raw.all_time?.top_domains,
      raw.domainUsageMinutes,
      raw.domain_usage_all_time
    )
  );

  return {
    raw,

    todayTotalMinutes,
    sevenDayTrend,
    topDomainsToday,
    topDomainsAllTime,

    currentSession: normalizeObject(
      firstDefined(raw.current_session, raw.currentSession, raw.session_current)
    ),

    latestIntervention: normalizeObject(
      firstDefined(
        raw.latest_intervention,
        raw.latestIntervention,
        raw.intervention_latest
      )
    ),

    sessionStats: normalizeObject(
      firstDefined(raw.session_stats, raw.sessionStats, raw.sessions)
    ),

    interventionStats: normalizeObject(
      firstDefined(
        raw.intervention_stats,
        raw.interventionStats,
        raw.interventions
      )
    ),

    extensionEventStats: normalizeObject(
      firstDefined(
        raw.extension_event_stats,
        raw.extensionEventStats,
        raw.event_stats,
        raw.events
      )
    ),
  };
}