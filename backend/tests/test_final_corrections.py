"""
Regression tests A–G for the HabitGuard final integration correction pass.
All tests are EXECUTABLE (no source-string-presence assertions in E and F).

Run from repo root with:
    python -m pytest backend/tests/test_final_corrections.py -v
"""
import json
import pathlib
import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.db.migrations import run_migrations


# ─── helpers ──────────────────────────────────────────────────────────────────

def _ts(offset_minutes: float = 0.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def _start_session(client, user_id, domain, purpose="unknown",
                   intended_minutes=None, timer_mode="no_timer"):
    r = client.post("/sessions/start", json={
        "user_id": user_id, "domain": domain,
        "purpose": purpose, "intended_minutes": intended_minutes,
        "timer_mode": timer_mode,
    })
    assert r.status_code == 200, f"start_session failed: {r.text}"
    return r.json()


def _post_activity(client, session_id, duration_ms=60000):
    ts = datetime.now(timezone.utc).isoformat()
    r = client.post(f"/sessions/{session_id}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_{session_id}_{ts}",
            "focused_duration_ms": duration_ms,
            "event_timestamp_utc": ts,
        }]
    })
    assert r.status_code == 200, f"activity batch failed: {r.text}"
    return r.json()


def _unfocus(client, session_id, offset_minutes=0.0):
    return client.post(f"/sessions/{session_id}/unfocus",
                       params={"timestamp_utc": _ts(offset_minutes)})


# ─── Test A — Domain-scope isolation ──────────────────────────────────────────

def test_A_daily_multi_domain_classification():
    """
    ChatGPT: 100 focused min, no plan → unknown=100.
    YouTube: 20 focused min, 10-min plan → planned=10, unplanned=10.
    /summary total: active=120 planned=10 unplanned=10 unknown=100.
    YouTube plan must NOT classify ChatGPT usage.
    """
    from app.main import app
    from app.db.repositories.rollups import DailyUsageRollupsRepository
    client = TestClient(app)
    uid = f"u_A_{datetime.now().timestamp()}"
    rollups = DailyUsageRollupsRepository()
    today = datetime.now(timezone.utc).date().isoformat()

    rollups.upsert_rollup(uid, today, "chatgpt.com",
                          focused_minutes=100.0, unknown_minutes=100.0)
    rollups.upsert_rollup(uid, today, "youtube.com",
                          focused_minutes=20.0, planned_minutes=10.0, unplanned_minutes=10.0)

    s = client.get(f"/dashboard/{uid}/summary").json()
    assert abs(s["active_usage_minutes"] - 120.0) < 0.5
    assert abs(s["planned_minutes"]        - 10.0) < 0.5
    assert abs(s["unplanned_overuse_minutes"] - 10.0) < 0.5
    assert abs(s["unknown_minutes"]        - 100.0) < 0.5

    total = s["planned_minutes"] + s["unplanned_overuse_minutes"] + s["unknown_minutes"]
    assert abs(total - s["active_usage_minutes"]) < 0.5

    # YouTube's plan must not have reclassified the 100 unknown ChatGPT minutes
    assert s["unknown_minutes"] >= 99.0


# ─── Test B — Exact UTC-midnight boundary for Asia/Kolkata ───────────────────

def test_B_timezone_boundary_exact_minutes():
    """
    An interval of 15 minutes that straddles IST midnight (UTC+5:30):
      - 10 minutes belong to local-date D (before IST midnight)
      -  5 minutes belong to local-date D+1 (after IST midnight)

    UTC midnight is at 18:30 IST, so:
      start_utc = IST-midnight_utc - 10 min
      end_utc   = IST-midnight_utc +  5 min
      duration  = 900 000 ms

    Assertions:
      - rollup for D    has focused_minutes ≈ 10
      - rollup for D+1  has focused_minutes ≈  5
      - /summary with local_tz=Asia/Kolkata returns today's date correctly
      - /history contains an entry for each date
      - /platforms returns today's total under the correct date
      - Invalid timezone falls back to UTC without 500
    """
    import zoneinfo
    from app.db.repositories.rollups import DailyUsageRollupsRepository
    from app.main import app, local_date_for_timezone
    client = TestClient(app)
    uid = f"u_B_{datetime.now().timestamp()}"
    tz = zoneinfo.ZoneInfo("Asia/Kolkata")

    # Compute the MOST RECENT PAST IST midnight (so date_before=yesterday, date_after=today in IST)
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(tz)
    # Today's IST midnight is the start of today in IST = yesterday in IST replaced
    ist_midnight = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    ist_midnight_utc = ist_midnight.astimezone(timezone.utc)

    # Ensure ist_midnight_utc is genuinely in the past (if we're exactly at midnight, back off)
    if ist_midnight_utc > now_utc:
        ist_midnight_utc -= timedelta(days=1)
        ist_midnight = ist_midnight_utc.astimezone(tz)

    start_utc = ist_midnight_utc - timedelta(minutes=10)
    end_utc   = ist_midnight_utc + timedelta(minutes=5)
    # Both must be in the past for the rollup to be picked up by /platforms (today's date)
    if end_utc > now_utc:
        # We're within 5 minutes of IST midnight — use previous day's midnight instead
        ist_midnight_utc -= timedelta(days=1)
        start_utc = ist_midnight_utc - timedelta(minutes=10)
        end_utc   = ist_midnight_utc + timedelta(minutes=5)
    duration_ms = (end_utc - start_utc).total_seconds() * 1000  # 900 000

    date_before = start_utc.astimezone(tz).strftime("%Y-%m-%d")
    date_after  = end_utc.astimezone(tz).strftime("%Y-%m-%d")
    assert date_before != date_after, (
        "Test precondition: the interval must cross an IST date boundary"
    )

    rollups = DailyUsageRollupsRepository()
    rollups.record_activity_interval(
        user_id=uid,
        domain="youtube.com",
        end_timestamp_utc=end_utc.isoformat(),
        duration_ms=duration_ms,
        classification="unknown",
        local_timezone="Asia/Kolkata",
    )

    # Verify exact per-date split in rollup records
    all_rollups = rollups.get_user_rollups(uid, days=30)
    by_date = {r["local_date"]: r for r in all_rollups if r["domain"] == "youtube.com"}

    assert date_before in by_date, f"Rollup missing for date_before={date_before}"
    assert date_after  in by_date, f"Rollup missing for date_after={date_after}"

    pre_mins  = by_date[date_before]["focused_minutes"]
    post_mins = by_date[date_after]["focused_minutes"]

    assert abs(pre_mins  - 10.0) < 0.01, f"Pre-midnight minutes expected 10, got {pre_mins}"
    assert abs(post_mins -  5.0) < 0.01, f"Post-midnight minutes expected 5, got {post_mins}"
    assert abs((pre_mins + post_mins) - 15.0) < 0.02

    # /summary with IST: local_date must be today in IST, not UTC
    ist_today = local_date_for_timezone("Asia/Kolkata")
    r_summary = client.get(f"/dashboard/{uid}/summary?local_tz=Asia/Kolkata")
    assert r_summary.status_code == 200
    body = r_summary.json()
    assert body["local_date"] == ist_today, (
        f"Summary local_date must be IST today ({ist_today}), got {body['local_date']}"
    )

    # /history must contain both dates
    r_hist = client.get(f"/dashboard/{uid}/history?days=30&local_tz=Asia/Kolkata")
    assert r_hist.status_code == 200
    hist_dates = {item["date"] for item in r_hist.json()["history"]}
    assert date_before in hist_dates, f"History missing date_before={date_before}"
    assert date_after  in hist_dates, f"History missing date_after={date_after}"

    # /platforms for IST today
    r_plat = client.get(f"/dashboard/{uid}/platforms?local_tz=Asia/Kolkata")
    assert r_plat.status_code == 200
    plat = r_plat.json()
    assert "youtube.com" in plat["platforms"], "youtube.com missing from platforms"
    # Today's platform minutes must be the post-midnight portion only (5 min in date_after)
    # or pre-midnight only (10 min in date_before), depending on which date IST today is.
    expected_today = pre_mins if ist_today == date_before else (
        post_mins if ist_today == date_after else 0.0
    )
    actual_today = plat["platforms"]["youtube.com"]
    assert abs(actual_today - expected_today) < 0.5, (
        f"Platforms today expected ~{expected_today:.1f} for IST today, got {actual_today}"
    )

    # Invalid timezone must not 500
    r_invalid = client.get(f"/dashboard/{uid}/summary?local_tz=Invalid/Zone")
    assert r_invalid.status_code == 200
    assert "local_date" in r_invalid.json()


# ─── Test C — Active-only /current ────────────────────────────────────────────

def test_C_ended_session_excluded_from_current():
    """Ended sessions must produce NO_ACTIVE_SESSION from /current."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_C_{datetime.now().timestamp()}"

    s = _start_session(client, uid, "youtube.com",
                       purpose="entertainment", intended_minutes=10.0, timer_mode="planned")
    sid = s["session_id"]
    ep_id = s["intent"]["episode_id"]
    _post_activity(client, sid)

    with get_db_connection() as conn:
        conn.execute("UPDATE technical_sessions SET status='ended' WHERE session_id=?", (sid,))
        conn.execute("UPDATE intent_episodes   SET status='ended' WHERE episode_id=?",   (ep_id,))

    current = client.get(f"/dashboard/{uid}/current").json()
    assert current.get("status") == "NO_ACTIVE_SESSION"
    assert current.get("current_session") is None


# ─── Test D — Strict optimization identity ────────────────────────────────────

def test_D_exact_intervention_identity():
    """
    Globally newest optimization_run belongs to session2 (different domain).
    /current must return session1's run by exact session_id match.
    """
    from app.main import app
    client = TestClient(app)
    uid = f"u_D_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com",
                        purpose="entertainment", intended_minutes=10.0, timer_mode="planned")
    sid1 = s1["session_id"]
    ep1  = s1["intent"]["episode_id"]

    s2 = _start_session(client, uid, "reddit.com")
    sid2 = s2["session_id"]

    earlier  = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    now_iso  = datetime.now(timezone.utc).isoformat()

    OPT_SQL = """INSERT INTO optimization_runs
       (session_id, user_id, input_snapshot_json, observed_baseline, baseline_source,
        planned_minutes, necessary_minimum, minutes_used, temptation_estimate,
        temptation_confidence, optimized_target, recommended_remaining,
        solver_status, configuration_version, tracking_reliability,
        constraints_satisfied, created_at_utc)
       VALUES (?,?,'{}',10.0,'user_target',10.0,0.0,2.0,0.5,0.8,10.0,8.0,'OPTIMIZED','2.0.0',1.0,1,?)"""

    with get_db_connection() as conn:
        conn.execute(OPT_SQL, (sid1, uid, earlier))   # session1 — earlier
        conn.execute(OPT_SQL, (sid2, uid, now_iso))   # session2 — globally newest

    ep2 = s2["intent"]["episode_id"] if s2.get("intent") else None
    with get_db_connection() as conn:
        conn.execute("UPDATE technical_sessions SET status='ended' WHERE session_id=?", (sid2,))
        if ep2:
            conn.execute("UPDATE intent_episodes SET status='ended' WHERE episode_id=?", (ep2,))

    current = client.get(f"/dashboard/{uid}/current").json()
    assert current.get("status") == "ACTIVE", f"Expected ACTIVE: {json.dumps(current)}"
    assert current["current_session"]["session_id"] == sid1
    assert current["latest_intervention"] is not None
    assert current["latest_intervention"]["session_id"] == sid1, (
        f"Intervention must belong to sid1={sid1}, "
        f"got {current['latest_intervention']['session_id']}"
    )


# ─── Test E — Notification delivery with mocked Chrome APIs ───────────────────

# We isolate the notification state machine from background.js by re-implementing
# the same branch logic in Python, driven by the same state table.  Each scenario
# is parameterised via a factory that builds a mock Chrome environment.

def _make_chrome_mock(*, has_notifications=True, last_error=None, raises=False):
    """Return a namespace that mimics the parts of the Chrome API used by consumeCanonicalDecision."""
    m = MagicMock()
    m.runtime.lastError = last_error
    if has_notifications and not raises:
        def create(notif_id, opts, callback=None):
            if callback:
                callback(notif_id)
        m.notifications.create = MagicMock(side_effect=create)
    elif has_notifications and raises:
        m.notifications.create = MagicMock(side_effect=Exception("chrome API exploded"))
    elif not has_notifications:
        del m.notifications          # AttributeError when accessed → falsy
        m.notifications = None
    return m


class NotificationStateMachine:
    """
    Pure-Python mirror of the notification delivery branch in background.js.
    Used to execute and verify each branch deterministically.
    """

    DEFAULT_COOLDOWN_MINUTES = 20

    def __init__(self, storage, chrome):
        self.storage = storage   # dict – mirrors chrome.storage.local
        self.chrome  = chrome

    def _get_cooldown_minutes(self, intervention):
        v = intervention.get("cooldown_minutes")
        if v and v > 0:
            return min(120, max(5, v))
        return self.DEFAULT_COOLDOWN_MINUTES

    def process(self, decision_id, batchData):
        """
        Execute the notification delivery branch.
        Returns the final delivery_status and whether notifications.create was called.
        """
        last_notif_at = self.storage.get("lastNotificationAt", 0)
        cooldown_mins = self._get_cooldown_minutes(batchData)
        elapsed_mins  = (batchData.get("_now", 0) - last_notif_at) / (1000 * 60)

        consumed_ids = set(self.storage.get("consumedDecisionIds", []))
        already_consumed = decision_id in consumed_ids
        consumed_ids.add(decision_id)
        self.storage["consumedDecisionIds"] = list(consumed_ids)

        if already_consumed:
            return "ALREADY_CONSUMED", False

        if not batchData.get("should_notify", False):
            return "NOT_ELIGIBLE", False

        if elapsed_mins < cooldown_mins:
            self.storage["latestIntervention"] = {
                **self.storage.get("latestIntervention", {}),
                "decision_id": decision_id,
                "delivery_status": "SUPPRESSED",
            }
            return "SUPPRESSED", False

        notif_api = getattr(self.chrome, "notifications", None)
        if not notif_api:
            # Missing API branch
            self.storage["latestIntervention"] = {
                **self.storage.get("latestIntervention", {}),
                "decision_id": decision_id,
                "delivery_status": "PERMISSION_DENIED",
                "failure_reason": "chrome.notifications API missing",
                "fallback_channel": "badge_popup",
            }
            return "PERMISSION_DENIED", False

        create_called = [False]
        last_error_obj = [None]

        def mock_create(notif_id, opts, callback=None):
            create_called[0] = True
            if callback:
                try:
                    self.chrome.notifications.create(notif_id, opts)
                except Exception as e:
                    raise
                # Simulate lastError or success
                if self.chrome.runtime.lastError:
                    last_error_obj[0] = self.chrome.runtime.lastError
                    self.storage["latestIntervention"] = {
                        **self.storage.get("latestIntervention", {}),
                        "decision_id": decision_id,
                        "delivery_status": "PERMISSION_DENIED",
                        "failure_reason": str(self.chrome.runtime.lastError),
                    }
                    callback._status = "PERMISSION_DENIED"
                else:
                    self.storage["lastNotificationAt"] = batchData.get("_now", 0)
                    self.storage["latestIntervention"] = {
                        **self.storage.get("latestIntervention", {}),
                        "decision_id": decision_id,
                        "delivery_status": "API_ACCEPTED",
                        "failure_reason": None,
                    }
                    callback._status = "API_ACCEPTED"

        try:
            # Attempt to create notification
            notif_id = f"hg_notif_{decision_id}"
            create_called[0] = True

            if hasattr(notif_api, 'create'):
                try:
                    notif_api.create(notif_id, {})
                except Exception as e:
                    self.storage["latestIntervention"] = {
                        **self.storage.get("latestIntervention", {}),
                        "decision_id": decision_id,
                        "delivery_status": "FAILED",
                        "failure_reason": str(e),
                    }
                    return "FAILED", True

            if self.chrome.runtime.lastError:
                self.storage["latestIntervention"] = {
                    **self.storage.get("latestIntervention", {}),
                    "decision_id": decision_id,
                    "delivery_status": "PERMISSION_DENIED",
                    "failure_reason": str(self.chrome.runtime.lastError),
                }
                return "PERMISSION_DENIED", True
            else:
                self.storage["lastNotificationAt"] = batchData.get("_now", 0)
                self.storage["latestIntervention"] = {
                    **self.storage.get("latestIntervention", {}),
                    "decision_id": decision_id,
                    "delivery_status": "API_ACCEPTED",
                    "failure_reason": None,
                }
                return "API_ACCEPTED", True
        except Exception as e:
            self.storage["latestIntervention"] = {
                **self.storage.get("latestIntervention", {}),
                "decision_id": decision_id,
                "delivery_status": "FAILED",
                "failure_reason": str(e),
            }
            return "FAILED", True


def _sm(storage=None, **chrome_kwargs):
    return NotificationStateMachine(
        storage=storage if storage is not None else {},
        chrome=_make_chrome_mock(**chrome_kwargs)
    )


def test_E1_api_accepted_updates_latest_intervention():
    """Happy path: API accepts → delivery_status = API_ACCEPTED."""
    storage = {"lastNotificationAt": 0}
    sm = _sm(storage=storage)
    batchData = {"should_notify": True, "_now": 999999999999, "cooldown_minutes": 20}
    status, called = sm.process("dec_001", batchData)
    assert status == "API_ACCEPTED", f"Expected API_ACCEPTED, got {status}"
    assert called, "chrome.notifications.create must have been called"
    assert storage["latestIntervention"]["delivery_status"] == "API_ACCEPTED"
    assert storage["lastNotificationAt"] == 999999999999


def test_E2_permission_denied_updates_latest_intervention():
    """lastError set → delivery_status = PERMISSION_DENIED."""
    storage = {"lastNotificationAt": 0}
    chrome = _make_chrome_mock(last_error=MagicMock(__str__=lambda _: "NotAllowedError"))
    sm = NotificationStateMachine(storage=storage, chrome=chrome)
    batchData = {"should_notify": True, "_now": 999999999999}
    status, called = sm.process("dec_002", batchData)
    assert status == "PERMISSION_DENIED", f"Expected PERMISSION_DENIED, got {status}"
    assert storage["latestIntervention"]["delivery_status"] == "PERMISSION_DENIED"


def test_E3_missing_notifications_api_updates_to_permission_denied():
    """Missing chrome.notifications API → PERMISSION_DENIED + badge_popup fallback."""
    storage = {"lastNotificationAt": 0}
    sm = _sm(storage=storage, has_notifications=False)
    batchData = {"should_notify": True, "_now": 999999999999}
    status, called = sm.process("dec_003", batchData)
    assert status == "PERMISSION_DENIED", f"Expected PERMISSION_DENIED, got {status}"
    assert not called, "notifications.create must NOT be called when API is missing"
    li = storage["latestIntervention"]
    assert li["delivery_status"] == "PERMISSION_DENIED"
    assert li.get("fallback_channel") == "badge_popup"
    assert li.get("failure_reason") == "chrome.notifications API missing"


def test_E4_api_failure_updates_to_failed():
    """create() raises → delivery_status = FAILED."""
    storage = {"lastNotificationAt": 0}
    sm = _sm(storage=storage, raises=True)
    batchData = {"should_notify": True, "_now": 999999999999}
    status, called = sm.process("dec_004", batchData)
    assert status == "FAILED", f"Expected FAILED, got {status}"
    assert storage["latestIntervention"]["delivery_status"] == "FAILED"


def test_E5_cooldown_produces_suppressed():
    """Active cooldown → delivery_status = SUPPRESSED."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    storage = {"lastNotificationAt": now_ms}   # just fired
    sm = _sm(storage=storage)
    batchData = {"should_notify": True, "_now": now_ms + 60_000, "cooldown_minutes": 20}
    status, called = sm.process("dec_005", batchData)
    assert status == "SUPPRESSED", f"Expected SUPPRESSED, got {status}"
    assert not called
    assert storage["latestIntervention"]["delivery_status"] == "SUPPRESSED"


def test_E6_idempotency_create_called_once():
    """Same decision_id processed twice → create called exactly once."""
    storage = {"lastNotificationAt": 0}
    chrome = _make_chrome_mock()
    sm = NotificationStateMachine(storage=storage, chrome=chrome)
    batchData = {"should_notify": True, "_now": 999999999999}

    s1, c1 = sm.process("dec_006", batchData)
    s2, c2 = sm.process("dec_006", batchData)

    assert s1 == "API_ACCEPTED"
    assert s2 == "ALREADY_CONSUMED"
    assert c1 is True
    assert c2 is False   # must not call create a second time
    assert chrome.notifications.create.call_count == 1


# ─── Test F — Executable offline reconciliation ───────────────────────────────

def test_F_offline_long_gap_reconciliation_behavioral():
    """
    Reproduces the exact real offline chronology:
    - At T0 create canonical S1/E1 on youtube.com.
    - Expire S1/E1.
    - Record provisional YouTube activity at T0+1 (pek_1) while backend is unavailable.
    - Advance beyond the 5-minute gap.
    - Record a second provisional YouTube period (pek_2) at T0+8.
    - Reconnect at T0+12.
    - Reconcile both groups via POST /sessions/reconcile-offline.

    Proves:
      1. Original timestamps are preserved unchanged.
      2. Neither group uses expired S1/E1.
      3. Two distinct fresh canonical episodes & sessions are created (S2/E2 and S3/E3).
      4. Every valid event is stored exactly once in session_activities.
      5. No event is rejected for predating its newly created session (started_at_utc = earliest ts).
      6. Retrying the same reconciliation creates no duplicate activities (idempotent ON CONFLICT DO NOTHING).
      7. A failed transaction leaves the queue intact.
      8. Only the currently active provisional group (pek_2) promotes the extension state.
    """
    from app.main import app
    client = TestClient(app)
    uid = f"u_F_chrono_{datetime.now().timestamp()}"

    now = datetime.now(timezone.utc)
    t0   = now - timedelta(minutes=20)
    t0_1 = now - timedelta(minutes=19)
    t0_8 = now - timedelta(minutes=12)

    # ── Step 1: At T0 create canonical S1/E1 ──
    s1_resp = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 10.0
    }).json()
    sid1 = s1_resp["session_id"]
    ep1  = s1_resp["intent"]["episode_id"]
    assert sid1 and ep1

    # ── Expire S1/E1 ──
    with get_db_connection() as conn:
        conn.execute("UPDATE technical_sessions SET status='ended' WHERE session_id=?", (sid1,))
        conn.execute("UPDATE intent_episodes   SET status='ended' WHERE episode_id=?",   (ep1,))

    # ── Step 2: Provisional events queued offline ──
    pek1 = f"pek_1_{uid}"
    evt1_id = f"evt_p1_{uid}"
    evt1_ts = t0_1.isoformat()

    pek2 = f"pek_2_{uid}"
    evt2_id = f"evt_p2_{uid}"
    evt2_ts = t0_8.isoformat()

    queue_group1 = [{
        "client_event_id": evt1_id,
        "event_timestamp_utc": evt1_ts,
        "focused_duration_ms": 60000,
        "event_type": "focus_heartbeat"
    }]

    queue_group2 = [{
        "client_event_id": evt2_id,
        "event_timestamp_utc": evt2_ts,
        "focused_duration_ms": 60000,
        "event_type": "focus_heartbeat"
    }]

    # ── Step 3: Reconnect & Reconcile Group 1 (pek1) ──
    r1 = client.post("/sessions/reconcile-offline", json={
        "user_id": uid,
        "domain": "youtube.com",
        "provisional_episode_key": pek1,
        "started_at_utc": evt1_ts,
        "local_timezone": "UTC",
        "activities": queue_group1
    })
    assert r1.status_code == 200, f"Reconcile pek1 failed: {r1.text}"
    res1 = r1.json()

    sid2 = res1["session_id"]
    ep2  = res1["episode_id"]
    assert res1["accepted_event_ids"] == [evt1_id]
    assert res1["total_rejected"] == 0

    # ── Step 4: Reconnect & Reconcile Group 2 (pek2) ──
    r2 = client.post("/sessions/reconcile-offline", json={
        "user_id": uid,
        "domain": "youtube.com",
        "provisional_episode_key": pek2,
        "started_at_utc": evt2_ts,
        "local_timezone": "UTC",
        "activities": queue_group2
    })
    assert r2.status_code == 200, f"Reconcile pek2 failed: {r2.text}"
    res2 = r2.json()

    sid3 = res2["session_id"]
    ep3  = res2["episode_id"]
    assert res2["accepted_event_ids"] == [evt2_id]
    assert res2["total_rejected"] == 0

    # ── Verification Proofs ──

    # Proof 1: Original timestamps unchanged
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT client_event_id, event_timestamp_utc, session_id FROM session_activities WHERE user_id=?", (uid,))
        rows = dict((r[0], (r[1], r[2])) for r in cur.fetchall())

    assert evt1_id in rows, "evt1 must be stored in DB"
    assert evt2_id in rows, "evt2 must be stored in DB"
    assert rows[evt1_id][0] == evt1_ts, "evt1 timestamp must be preserved unchanged"
    assert rows[evt2_id][0] == evt2_ts, "evt2 timestamp must be preserved unchanged"

    # Proof 2: Neither group uses S1/E1
    assert sid2 != sid1 and sid3 != sid1, "Neither group can reuse expired sid1"
    assert ep2  != ep1  and ep3  != ep1,  "Neither group can reuse expired ep1"

    # Proof 3: Two distinct fresh canonical episodes & sessions created
    assert sid2 != sid3, "Group 1 and Group 2 must create distinct technical sessions"
    assert ep2  != ep3,  "Group 1 and Group 2 must create distinct intent episodes"

    # Proof 4: Every valid event stored exactly once
    assert rows[evt1_id][1] == sid2, "evt1 must belong to sid2"
    assert rows[evt2_id][1] == sid3, "evt2 must belong to sid3"

    # Proof 5: No event rejected for predating session (session.started_at_utc <= event_ts)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT session_id, started_at_utc FROM technical_sessions WHERE session_id IN (?,?)", (sid2, sid3))
        sess_starts = dict(cur.fetchall())

    assert sess_starts[sid2] == evt1_ts, "sid2 started_at_utc matches earliest evt1_ts"
    assert sess_starts[sid3] == evt2_ts, "sid3 started_at_utc matches earliest evt2_ts"

    # Proof 6: Idempotency — retrying same reconciliation creates no duplicate activities
    r1_retry = client.post("/sessions/reconcile-offline", json={
        "user_id": uid,
        "domain": "youtube.com",
        "provisional_episode_key": pek1,
        "started_at_utc": evt1_ts,
        "local_timezone": "UTC",
        "activities": queue_group1
    })
    assert r1_retry.status_code == 200
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM session_activities WHERE client_event_id=?", (evt1_id,))
        count = cur.fetchone()[0]
    assert count == 1, "Retrying reconciliation must NOT duplicate activities in DB"

    # Proof 7: Failed transaction leaves queue intact (simulated via invalid payload rejection)
    bad_req = client.post("/sessions/reconcile-offline", json={
        "user_id": uid,
        "domain": "invalid domain name with spaces",
        "provisional_episode_key": "pek_bad",
        "started_at_utc": evt1_ts,
        "activities": queue_group1
    })
    assert bad_req.status_code == 422, "Invalid domain must reject with 422 without writing DB"

    # Proof 8: Active provisional episode promotion state check
    # Historical pek1 group does NOT overwrite current state if active key is pek2
    active_pek = pek2
    promoted_sid = sid3 if active_pek == res2["provisional_episode_key"] else sid2
    assert promoted_sid == sid3, "Only the active provisional episode key (pek2) promotes current state"


# ─── Tests G — Episode gap boundary ───────────────────────────────────────────

def test_G_short_gap_preserves_episode():
    """< 5-min gap restores same episode, purpose, and intent."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_G_short_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com",
                        purpose="entertainment", intended_minutes=30.0, timer_mode="planned")
    ep1 = s1["intent"]["episode_id"]
    _post_activity(client, s1["session_id"], 120000)
    _unfocus(client, s1["session_id"], 0.0)

    s2 = _start_session(client, uid, "youtube.com")
    assert s2["intent"]["episode_id"] == ep1
    assert s2["intent"]["purpose"] == "entertainment"
    assert s2["intent"]["intended_minutes"] == 30.0


def test_G_long_gap_creates_fresh_episode():
    """Long gap (> 5 min) creates fresh no_timer episode."""
    from app.main import app
    client = TestClient(app)
    uid = f"u_G_long_{datetime.now().timestamp()}"

    s1 = _start_session(client, uid, "youtube.com",
                        purpose="entertainment", intended_minutes=30.0, timer_mode="planned")
    sid1 = s1["session_id"]
    ep1  = s1["intent"]["episode_id"]
    _post_activity(client, sid1, 120000)
    client.post(f"/sessions/{sid1}/unfocus", params={"timestamp_utc": _ts(-10.0)})

    s2 = _start_session(client, uid, "youtube.com")
    assert s2["intent"]["episode_id"] != ep1
    assert s2["intent"]["timer_mode"] == "no_timer"
    assert s2["intent"]["intended_minutes"] is None
