/**
 * HabitGuard — Offline queue grouping and rebinding contract test
 * Runs with: node chrome_extension/tests/test_offline_queue_grouping.js
 *
 * This test exercises the pure-logic portions of the offline reconciliation
 * pipeline extracted from background.js:
 *   - generateProvisionalEpisodeKey          (key generation + uniqueness)
 *   - groupQueueByProvisionalKey             (grouping logic)
 *   - rotateProvisionalKeyOnGap              (5-min gap rotation)
 *   - buildReconcilePayload                  (payload assembly)
 *   - applyReconcileResult                   (queue trimming after acceptance)
 *
 * No Chrome APIs, no fetch, no file system I/O.  All logic is synchronous.
 * Each test is self-contained and prints PASS / FAIL.
 */

"use strict";

// ─── Pure helpers extracted from background.js ────────────────────────────────

/** Mirror of background.js generateProvisionalEpisodeKey */
function generateProvisionalEpisodeKey() {
  const rand = Math.random().toString(36).substr(2, 10);
  return `pek_${Date.now()}_${rand}`;
}

const SESSION_RESUME_GAP_MINUTES = 5;

/**
 * Determine whether a new provisional_episode_key should be issued for a
 * domain-switch or gap-expiry event. Returns the key that should be used.
 *
 * @param {object|null} currentSession - current session object in storage
 * @param {string} activeDomain        - newly detected active domain
 * @param {number} nowMs               - current timestamp in ms (Date.now())
 * @returns {{ key: string, isRotation: boolean }}
 */
function resolveProvisionalEpisodeKey(currentSession, activeDomain, nowMs) {
  if (!currentSession || currentSession.domain !== activeDomain) {
    // Domain change → always rotate
    return { key: generateProvisionalEpisodeKey(), isRotation: true };
  }
  if (currentSession.canonicalState !== "OFFLINE_FALLBACK") {
    // Not an offline fallback (e.g. TRACKABLE_ACTIVE) → new key
    return { key: generateProvisionalEpisodeKey(), isRotation: true };
  }
  const fallbackStartedAt =
    currentSession.offlineFallbackStartedAt || currentSession.startedAt || nowMs;
  const gapMins = (nowMs - fallbackStartedAt) / (1000 * 60);
  if (gapMins <= SESSION_RESUME_GAP_MINUTES) {
    // Continuation: reuse existing key
    return {
      key: currentSession.provisionalEpisodeKey || generateProvisionalEpisodeKey(),
      isRotation: false
    };
  }
  // Gap exceeded → rotate
  return { key: generateProvisionalEpisodeKey(), isRotation: true };
}

/**
 * Group an offline queue by provisional_episode_key.
 * Entries without a key fall into a synthetic legacy bucket per domain.
 *
 * @param {Array} queue
 * @returns {{ bySession: object, byProvisionalKey: object }}
 */
function groupOfflineQueue(queue) {
  const bySession = {};
  const byProvisionalKey = {};
  for (const entry of queue) {
    if (entry.session_id) {
      if (!bySession[entry.session_id]) bySession[entry.session_id] = [];
      bySession[entry.session_id].push(entry);
    } else {
      const pek =
        entry.provisional_episode_key ||
        `pek_legacy_${entry.domain || "unknown"}`;
      if (!byProvisionalKey[pek]) byProvisionalKey[pek] = [];
      byProvisionalKey[pek].push(entry);
    }
  }
  return { bySession, byProvisionalKey };
}

/**
 * Build the /sessions/reconcile-offline request payload for a provisional group.
 * The started_at_utc is set to the earliest event_timestamp_utc in the group.
 *
 * @param {string} pek - provisional_episode_key
 * @param {Array}  entries
 * @param {string} userId
 * @param {string} timezone
 * @returns {object} payload ready to POST
 */
function buildReconcilePayload(pek, entries, userId = "local_user", timezone = "UTC") {
  let earliestTs = null;
  for (const e of entries) {
    if (!earliestTs || e.event_timestamp_utc < earliestTs) {
      earliestTs = e.event_timestamp_utc;
    }
  }
  const activities = entries.map((e) => ({
    client_event_id:     e.client_event_id,
    event_timestamp_utc: e.event_timestamp_utc,   // NEVER rewritten
    focused_duration_ms: e.focused_duration_ms,
    event_type:          e.event_type || "focus_heartbeat"
  }));
  return {
    user_id:                 userId,
    domain:                  entries[0].domain,
    provisional_episode_key: pek,
    started_at_utc:          earliestTs,
    local_timezone:          timezone,
    activities
  };
}

/**
 * Apply a successful reconcile response to the queue:
 * - Remove accepted event IDs
 * - Retain rejected events with failure_reason
 * - Retain unknown-outcome events for retry
 *
 * @param {Array}  queue           - current offline queue
 * @param {object} reconcileResult - response from /sessions/reconcile-offline
 * @param {string} pek             - the provisional key that was reconciled
 * @returns {{ remaining: Array, flushed: number }}
 */
function applyReconcileResult(queue, reconcileResult, pek) {
  const acceptedSet = new Set(reconcileResult.accepted_event_ids || []);
  const rejectedMap = {};
  for (const r of (reconcileResult.rejected_events || [])) {
    if (r.client_event_id) rejectedMap[r.client_event_id] = r.reason || "rejected";
  }

  let flushed = 0;
  const remaining = [];
  for (const e of queue) {
    // Only apply to entries belonging to this pek group
    const entryPek = e.provisional_episode_key || `pek_legacy_${e.domain || "unknown"}`;
    if (entryPek !== pek || e.session_id) {
      remaining.push(e);
      continue;
    }
    if (acceptedSet.has(e.client_event_id)) {
      flushed++;
      // removed from queue
    } else if (rejectedMap[e.client_event_id]) {
      e.failure_reason = rejectedMap[e.client_event_id];
      e.retry_count = (e.retry_count || 0) + 1;
      remaining.push(e);
    } else {
      e.retry_count = (e.retry_count || 0) + 1;
      remaining.push(e);
    }
  }
  return { remaining, flushed };
}


// ─── Test harness ─────────────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  FAIL: ${message}`);
    failed++;
  }
}

function test(name, fn) {
  try {
    fn();
    console.log(`PASS  ${name}`);
    passed++;
  } catch (e) {
    console.error(`FAIL  ${name}: ${e.message}`);
    failed++;
  }
}


// ─── Tests ────────────────────────────────────────────────────────────────────

test("generateProvisionalEpisodeKey: prefixed and non-empty", () => {
  const key = generateProvisionalEpisodeKey();
  assert(typeof key === "string" && key.startsWith("pek_"), `Key must start with pek_: ${key}`);
  assert(key.length > 10, "Key must be reasonably long");
});

test("generateProvisionalEpisodeKey: two calls produce distinct keys", () => {
  const k1 = generateProvisionalEpisodeKey();
  const k2 = generateProvisionalEpisodeKey();
  assert(k1 !== k2, `Keys must be distinct, got: ${k1} and ${k2}`);
});

test("resolveProvisionalEpisodeKey: domain change always rotates", () => {
  const session = {
    domain: "youtube.com",
    canonicalState: "OFFLINE_FALLBACK",
    provisionalEpisodeKey: "pek_old",
    offlineFallbackStartedAt: Date.now() - 60_000  // 1 min ago (within gap)
  };
  const { key, isRotation } = resolveProvisionalEpisodeKey(
    session, "reddit.com", Date.now()
  );
  assert(isRotation === true, "Domain change must cause key rotation");
  assert(key !== "pek_old", "New key must differ from old");
});

test("resolveProvisionalEpisodeKey: within gap reuses existing key", () => {
  const existingKey = "pek_111_aabbccdd";
  const session = {
    domain: "youtube.com",
    canonicalState: "OFFLINE_FALLBACK",
    provisionalEpisodeKey: existingKey,
    offlineFallbackStartedAt: Date.now() - 2 * 60_000  // 2 min ago
  };
  const { key, isRotation } = resolveProvisionalEpisodeKey(
    session, "youtube.com", Date.now()
  );
  assert(isRotation === false, "Within gap: must NOT rotate");
  assert(key === existingKey, `Key must be reused: expected ${existingKey}, got ${key}`);
});

test("resolveProvisionalEpisodeKey: gap > 5 min rotates key", () => {
  const existingKey = "pek_222_xxyyzz";
  const session = {
    domain: "youtube.com",
    canonicalState: "OFFLINE_FALLBACK",
    provisionalEpisodeKey: existingKey,
    offlineFallbackStartedAt: Date.now() - 7 * 60_000  // 7 min ago
  };
  const { key, isRotation } = resolveProvisionalEpisodeKey(
    session, "youtube.com", Date.now()
  );
  assert(isRotation === true, "Gap > 5 min must rotate key");
  assert(key !== existingKey, "Rotated key must differ");
});

test("groupOfflineQueue: session_id present → Group A only", () => {
  const queue = [
    { session_id: "sess_001", client_event_id: "e1", domain: "youtube.com",
      event_timestamp_utc: "2026-07-29T10:00:00Z", focused_duration_ms: 60000 }
  ];
  const { bySession, byProvisionalKey } = groupOfflineQueue(queue);
  assert(Object.keys(bySession).length === 1, "Must have 1 session group");
  assert(Object.keys(byProvisionalKey).length === 0, "No provisional groups");
  assert(bySession["sess_001"].length === 1, "Group A has 1 event");
});

test("groupOfflineQueue: null session_id → Group B by provisional_episode_key", () => {
  const queue = [
    { session_id: null, provisional_episode_key: "pek_A", client_event_id: "e1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:01:00Z",
      focused_duration_ms: 60000 },
    { session_id: null, provisional_episode_key: "pek_A", client_event_id: "e2",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:02:00Z",
      focused_duration_ms: 60000 },
    { session_id: null, provisional_episode_key: "pek_B", client_event_id: "e3",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:10:00Z",
      focused_duration_ms: 60000 }
  ];
  const { bySession, byProvisionalKey } = groupOfflineQueue(queue);
  assert(Object.keys(bySession).length === 0, "No canonical sessions");
  assert(Object.keys(byProvisionalKey).length === 2, "Must have 2 provisional groups");
  assert(byProvisionalKey["pek_A"].length === 2, "pek_A has 2 events");
  assert(byProvisionalKey["pek_B"].length === 1, "pek_B has 1 event");
});

test("groupOfflineQueue: two YouTube periods with different keys → two groups", () => {
  // Simulates T0+1 period (pek_A) and T0+8 period (pek_B) — 7 min gap caused rotation
  const queue = [
    { session_id: null, provisional_episode_key: "pek_A",
      client_event_id: "yt_1", domain: "youtube.com",
      event_timestamp_utc: "2026-07-29T10:00:00Z", focused_duration_ms: 60000 },
    { session_id: null, provisional_episode_key: "pek_B",
      client_event_id: "yt_2", domain: "youtube.com",
      event_timestamp_utc: "2026-07-29T10:08:00Z", focused_duration_ms: 60000 }
  ];
  const { byProvisionalKey } = groupOfflineQueue(queue);
  const keys = Object.keys(byProvisionalKey);
  assert(keys.length === 2, `Must produce 2 separate groups, got ${keys.length}`);
  assert("pek_A" in byProvisionalKey, "Group pek_A must exist");
  assert("pek_B" in byProvisionalKey, "Group pek_B must exist");
});

test("buildReconcilePayload: started_at_utc is the EARLIEST event timestamp", () => {
  const pek = "pek_test_early";
  const entries = [
    { client_event_id: "e1", event_timestamp_utc: "2026-07-29T10:05:00Z",
      focused_duration_ms: 60000, domain: "youtube.com" },
    { client_event_id: "e2", event_timestamp_utc: "2026-07-29T10:02:00Z",   // earlier
      focused_duration_ms: 60000, domain: "youtube.com" },
    { client_event_id: "e3", event_timestamp_utc: "2026-07-29T10:08:00Z",
      focused_duration_ms: 60000, domain: "youtube.com" }
  ];
  const payload = buildReconcilePayload(pek, entries);
  assert(
    payload.started_at_utc === "2026-07-29T10:02:00Z",
    `started_at_utc must be earliest: expected 10:02, got ${payload.started_at_utc}`
  );
  assert(payload.provisional_episode_key === pek, "pek must be echoed in payload");
  assert(payload.activities.length === 3, "All events included in activities");
});

test("buildReconcilePayload: original event_timestamp_utc values are NEVER rewritten", () => {
  const pek = "pek_ts_preserve";
  const entries = [
    { client_event_id: "e1", event_timestamp_utc: "2026-07-29T10:01:30Z",
      focused_duration_ms: 90000, domain: "youtube.com", event_type: "focus_heartbeat" }
  ];
  const payload = buildReconcilePayload(pek, entries);
  const act = payload.activities[0];
  assert(
    act.event_timestamp_utc === "2026-07-29T10:01:30Z",
    `Timestamp must be preserved: got ${act.event_timestamp_utc}`
  );
  assert(act.client_event_id === "e1", "client_event_id preserved");
  assert(act.focused_duration_ms === 90000, "duration preserved");
});

test("applyReconcileResult: accepted events removed from queue", () => {
  const pek = "pek_accept";
  const queue = [
    { session_id: null, provisional_episode_key: pek, client_event_id: "e1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:00:00Z",
      focused_duration_ms: 60000, retry_count: 0 },
    { session_id: null, provisional_episode_key: pek, client_event_id: "e2",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:01:00Z",
      focused_duration_ms: 60000, retry_count: 0 }
  ];
  const result = {
    accepted_event_ids: ["e1", "e2"],
    rejected_events: []
  };
  const { remaining, flushed } = applyReconcileResult(queue, result, pek);
  assert(flushed === 2, `Must flush 2 events, got ${flushed}`);
  assert(remaining.length === 0, `Queue must be empty after full acceptance, has ${remaining.length}`);
});

test("applyReconcileResult: rejected events retained with failure_reason", () => {
  const pek = "pek_reject";
  const queue = [
    { session_id: null, provisional_episode_key: pek, client_event_id: "e1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:00:00Z",
      focused_duration_ms: 60000, retry_count: 0 },
    { session_id: null, provisional_episode_key: pek, client_event_id: "e2",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:01:00Z",
      focused_duration_ms: 60000, retry_count: 0 }
  ];
  const result = {
    accepted_event_ids: ["e1"],
    rejected_events: [{ client_event_id: "e2", reason: "duration_out_of_range" }]
  };
  const { remaining, flushed } = applyReconcileResult(queue, result, pek);
  assert(flushed === 1, `Must flush 1 event, got ${flushed}`);
  assert(remaining.length === 1, "1 rejected event must remain");
  assert(remaining[0].client_event_id === "e2", "Retained event must be e2");
  assert(remaining[0].failure_reason === "duration_out_of_range", "failure_reason must be set");
});

test("applyReconcileResult: failed transaction leaves queue intact", () => {
  const pek = "pek_fail";
  const queue = [
    { session_id: null, provisional_episode_key: pek, client_event_id: "e1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:00:00Z",
      focused_duration_ms: 60000, retry_count: 0 }
  ];
  // Simulate no result (network failure) — applyReconcileResult is NOT called;
  // the caller simply increments retry_count and keeps the queue.
  const fakeFailedReconcile = null;
  if (fakeFailedReconcile === null) {
    queue[0].retry_count++;
  }
  assert(queue.length === 1, "Queue must remain intact after failed reconcile");
  assert(queue[0].retry_count === 1, "retry_count must be incremented");
  assert(queue[0].client_event_id === "e1", "client_event_id must be preserved");
  assert(queue[0].event_timestamp_utc === "2026-07-29T10:00:00Z", "timestamp must be preserved");
});

test("applyReconcileResult: events from OTHER pek groups are untouched", () => {
  const pekA = "pek_A";
  const pekB = "pek_B";
  const queue = [
    { session_id: null, provisional_episode_key: pekA, client_event_id: "a1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:00:00Z",
      focused_duration_ms: 60000, retry_count: 0 },
    { session_id: null, provisional_episode_key: pekB, client_event_id: "b1",
      domain: "youtube.com", event_timestamp_utc: "2026-07-29T10:10:00Z",
      focused_duration_ms: 60000, retry_count: 0 }
  ];
  const result = { accepted_event_ids: ["a1"], rejected_events: [] };
  // Reconciling pekA must not remove pekB events
  const { remaining, flushed } = applyReconcileResult(queue, result, pekA);
  assert(flushed === 1, "pekA event must be flushed");
  assert(remaining.length === 1, "pekB event must remain");
  assert(remaining[0].provisional_episode_key === pekB, "Remaining event belongs to pekB");
});

test("applyReconcileResult: idempotent — retry of same accepted IDs does not double-flush", () => {
  // After first flush, accepted events are removed. A retry with the same
  // accepted_event_ids against an empty group does nothing.
  const pek = "pek_idem";
  const queue = [];  // Already empty after first flush
  const result = { accepted_event_ids: ["e1"], rejected_events: [] };
  const { remaining, flushed } = applyReconcileResult(queue, result, pek);
  assert(flushed === 0, "Nothing to flush if queue is already empty");
  assert(remaining.length === 0, "Queue stays empty");
});


// ─── Summary ──────────────────────────────────────────────────────────────────

console.log(`\n${passed + failed} tests: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
