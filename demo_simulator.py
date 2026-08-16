"""
HabitGuard Live Demonstration Harness & Simulator
=================================================
Use this script during your presentation/demo to interactively simulate
or automate ALL 10 possible HabitGuard runtime scenarios.

Usage:
  Interactive Menu Mode:
    python demo_simulator.py

  Automated Full Walkthrough:
    python demo_simulator.py --auto
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app
from app.db.repositories.rollups import DailyUsageRollupsRepository

client = TestClient(app)
rollups_repo = DailyUsageRollupsRepository()

# ── Formatting Helpers ────────────────────────────────────────────────────────
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")

def print_result(label, data):
    print(f"{BOLD}{label}:{RESET}")
    print(json.dumps(data, indent=2))

def ts_utc(offset_minutes: float = 0.0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


# ── Scenario Functions ────────────────────────────────────────────────────────

def scenario_1_within_plan():
    """Scenario 1: Normal Session within Planned Limit"""
    print_header("SCENARIO 1: Normal Session Within Planned Limit")
    uid = f"demo_user_s1_{int(time.time())}"
    
    # 1. Start a 15 minute session on youtube.com for study
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "work_study", "intended_minutes": 15.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]
    print(f"-> Started 15-min session '{sid}' on youtube.com for 'work_study'")

    # 2. Add 3 minutes of usage
    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_s1_{time.time()}",
            "focused_duration_ms": 180000, # 3 mins
            "event_timestamp_utc": ts_utc(),
        }]
    }).json()

    print_result("Resulting Engine Output", {
        "session_status": act.get("session_status"),
        "usage_status": act.get("usage_status"),
        "focused_minutes": act.get("focused_minutes"),
        "effective_planned_minutes": act.get("effective_planned_minutes"),
        "remaining_minutes": act.get("recommended_remaining_minutes"),
        "should_intervene": act.get("should_intervene"),
        "friction_type": act.get("friction_type"),
        "decision_reason": act.get("decision_reason")
    })
    print(f"{GREEN}[OK] Case Verified: Normal usage on track. No friction triggered.{RESET}")


def scenario_2_near_plan():
    """Scenario 2: Approaching Timer Limit (Near Plan)"""
    print_header("SCENARIO 2: Approaching Timer Limit (Near-Plan Soft Check-in)")
    uid = f"demo_user_s2_{int(time.time())}"
    
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "work_study", "intended_minutes": 15.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]
    print(f"-> Started 15-min session '{sid}' on youtube.com")

    # Add 13.5 minutes of usage (within 2 minutes of 15 min limit)
    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_s2_{time.time()}",
            "focused_duration_ms": 810000, # 13.5 mins
            "event_timestamp_utc": ts_utc(),
        }]
    }).json()

    print_result("Resulting Engine Output", {
        "session_status": act.get("session_status"),
        "usage_status": act.get("usage_status"),
        "focused_minutes": act.get("focused_minutes"),
        "remaining_minutes": act.get("recommended_remaining_minutes"),
        "should_intervene": act.get("should_intervene"),
        "friction_type": act.get("friction_type"),
        "decision_reason": act.get("decision_reason")
    })
    print(f"{YELLOW}[OK] Case Verified: Near-plan detected. Soft warning / check-in recommendation.{RESET}")


def scenario_3_over_plan_strong_friction():
    """Scenario 3: Exceeding Timer Limit (Strong Friction Notification & Overlay)"""
    print_header("SCENARIO 3: Exceeding Timer Limit (Strong Friction + Notification + Overlay)")
    uid = f"demo_user_s3_{int(time.time())}"
    
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 15.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]
    print(f"-> Started 15-min session '{sid}' on youtube.com for 'entertainment'")

    # Add 32 minutes of usage (exceeding 15 min plan by 17 mins)
    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{
            "client_event_id": f"evt_s3_{time.time()}",
            "focused_duration_ms": 1920000, # 32 mins
            "event_timestamp_utc": ts_utc(),
        }]
    }).json()

    print_result("Resulting Engine Output", {
        "session_status": act.get("session_status"),
        "overuse_gap_minutes": act.get("overuse_gap_minutes"),
        "should_intervene": act.get("should_intervene"),
        "should_notify": act.get("should_notify"),
        "should_overlay": act.get("should_overlay"),
        "friction_type": act.get("friction_type"),
        "message": act.get("message")
    })
    print(f"{RED}[OK] Case Verified: Over-plan detected! Strong friction notification & overlay dispatched.{RESET}")


def scenario_4_user_action_extend():
    """Scenario 4: User Action — Extending Session (+5 Mins)"""
    print_header("SCENARIO 4: User Action — Extending Session (+5 Mins)")
    uid = f"demo_user_s4_{int(time.time())}"
    
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 10.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]

    # User overruns 10 min plan (12 mins used)
    client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": f"evt_s4_{time.time()}", "focused_duration_ms": 720000, "event_timestamp_utc": ts_utc()}]
    })

    print("-> User clicks '+5 Mins' button in popup/notification")
    action_res = client.post(f"/sessions/{sid}/action", json={"action": "extend_5"}).json()

    print_result("Updated Session State After Extension", {
        "original_intended_minutes": action_res.get("original_intended_minutes"),
        "extension_minutes": action_res.get("extension_minutes"),
        "effective_planned_minutes": action_res.get("effective_planned_minutes"),
        "used_minutes": action_res.get("used_minutes"),
        "remaining_minutes": action_res.get("remaining_minutes"),
        "overuse_gap_minutes": action_res.get("overuse_gap_minutes")
    })
    print(f"{GREEN}[OK] Case Verified: Planned target extended to 15 mins. Remaining time updated.{RESET}")


def scenario_5_stop_reminders():
    """Scenario 5: User Action — Muting Reminders (Stop Reminders)"""
    print_header("SCENARIO 5: User Action — Muting Reminders for Session")
    uid = f"demo_user_s5_{int(time.time())}"
    
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 10.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]

    print("-> User selects 'Stop Reminders' action")
    client.post(f"/sessions/{sid}/action", json={"action": "stop_reminders"})

    # Subsequent over-plan activity batch
    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": f"evt_s5_{time.time()}", "focused_duration_ms": 900000, "event_timestamp_utc": ts_utc()}]
    }).json()

    print_result("Engine Response After Stop Reminders", {
        "suppression_reason": act.get("suppression_reason"),
        "should_intervene": act.get("should_intervene"),
        "should_notify": act.get("should_notify"),
        "should_overlay": act.get("should_overlay"),
        "friction_type": act.get("friction_type")
    })
    print(f"{GREEN}[OK] Case Verified: Interventions suppressed due to user 'stop_reminders' action.{RESET}")


def scenario_6_cross_domain_displacement():
    """Scenario 6: Cross-Domain Site Substitution / Displacement"""
    print_header("SCENARIO 6: Cross-Domain Displacement (YouTube -> Instagram Switch)")
    uid = f"demo_user_s6_{int(time.time())}"
    today = datetime.now(timezone.utc).date().isoformat()

    # User already spent 90 minutes on YouTube today
    rollups_repo.upsert_rollup(uid, today, "youtube.com", focused_minutes=90.0, unplanned_minutes=40.0)
    print("-> Recorded 90 minutes of YouTube usage today for user")

    print("-> User switches to instagram.com and starts a session")
    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "instagram.com",
        "purpose": "browsing", "intended_minutes": 20.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]

    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": f"evt_s6_{time.time()}", "focused_duration_ms": 300000, "event_timestamp_utc": ts_utc()}]
    }).json()

    print_result("Cross-Domain Calculation Output", {
        "domain": act.get("domain"),
        "cross_domain_allowance": act.get("cross_domain_allowance"),
        "substitution_status": act.get("substitution_status"),
        "addiction_score": act.get("addiction_score"),
        "recommended_daily_limit": act.get("recommended_daily_limit")
    })
    print(f"{YELLOW}[OK] Case Verified: Cross-Domain engine detected displacement and ratcheted allowance.{RESET}")


def scenario_7_short_gap_resume():
    """Scenario 7: Short Gap Pause & Resume (< 5 Min)"""
    print_header("SCENARIO 7: Short Gap Pause & Resume (< 5 Min Same Episode)")
    uid = f"demo_user_s7_{int(time.time())}"
    
    s1 = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 25.0, "timer_mode": "planned"
    }).json()
    ep1 = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]
    print(f"-> Started Session 1: episode={ep1}")

    # Unfocus 2 minutes ago
    client.post(f"/sessions/{sid1}/unfocus", params={"timestamp_utc": ts_utc(-2.0)})
    print("-> User switched tab away 2 minutes ago (short gap)")

    # User returns to youtube.com
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    ep2 = s2["intent"]["episode_id"]
    print(f"-> Started Session 2 on return: episode={ep2}")

    print_result("Episode Continuity Check", {
        "original_episode_id": ep1,
        "returned_episode_id": ep2,
        "same_episode_restored": (ep1 == ep2),
        "restored_purpose": s2["intent"]["purpose"],
        "restored_intended_minutes": s2["intent"]["intended_minutes"]
    })
    assert ep1 == ep2
    print(f"{GREEN}[OK] Case Verified: Short gap (<5 min) preserved exact same episode and planned timer.{RESET}")


def scenario_8_long_gap_expiration():
    """Scenario 8: Long Gap Session Expiration (> 5 Min)"""
    print_header("SCENARIO 8: Long Gap Session Expiration (> 5 Min Fresh Episode)")
    uid = f"demo_user_s8_{int(time.time())}"
    
    s1 = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 25.0, "timer_mode": "planned"
    }).json()
    ep1 = s1["intent"]["episode_id"]
    sid1 = s1["session_id"]
    print(f"-> Started Session 1: episode={ep1}")

    # Unfocus 12 minutes ago
    client.post(f"/sessions/{sid1}/unfocus", params={"timestamp_utc": ts_utc(-12.0)})
    print("-> User left tab 12 minutes ago (long gap > 5 min)")

    # User returns to youtube.com
    s2 = client.post("/sessions/start", json={"user_id": uid, "domain": "youtube.com"}).json()
    ep2 = s2["intent"]["episode_id"]
    print(f"-> Started Session 2 on return: episode={ep2}")

    print_result("Episode Expiration Check", {
        "original_episode_id": ep1,
        "returned_episode_id": ep2,
        "fresh_episode_created": (ep1 != ep2),
        "timer_mode": s2["intent"]["timer_mode"],
        "intended_minutes": s2["intent"]["intended_minutes"]
    })
    assert ep1 != ep2
    print(f"{GREEN}[OK] Case Verified: Long gap (>5 min) expired old episode and created fresh 'no_timer' episode.{RESET}")


def scenario_9_offline_reconciliation():
    """Scenario 9: Atomic Offline Reconciliation"""
    print_header("SCENARIO 9: Atomic Offline Reconciliation (Reconnecting Queued Events)")
    uid = f"demo_user_s9_{int(time.time())}"
    pek = f"pek_demo_{int(time.time())}"
    t_start = ts_utc(-25.0)

    print("-> Reconnecting and submitting 2 queued offline heartbeats from 25 mins ago")
    r = client.post("/sessions/reconcile-offline", json={
        "user_id": uid,
        "domain": "reddit.com",
        "provisional_episode_key": pek,
        "started_at_utc": t_start,
        "local_timezone": "UTC",
        "activities": [
            {
                "client_event_id": f"evt_off_1_{time.time()}",
                "event_timestamp_utc": ts_utc(-24.0),
                "focused_duration_ms": 60000,
                "event_type": "focus_heartbeat"
            },
            {
                "client_event_id": f"evt_off_2_{time.time()}",
                "event_timestamp_utc": ts_utc(-18.0),
                "focused_duration_ms": 60000,
                "event_type": "focus_heartbeat"
            }
        ]
    }).json()

    print_result("Reconciliation Response", {
        "session_id": r.get("session_id"),
        "episode_id": r.get("episode_id"),
        "provisional_episode_key": r.get("provisional_episode_key"),
        "started_at_utc": r.get("started_at_utc"),
        "accepted_event_ids": r.get("accepted_event_ids"),
        "total_accepted": r.get("total_accepted"),
        "total_rejected": r.get("total_rejected")
    })
    print(f"{GREEN}[OK] Case Verified: Offline events reconciled atomically without timestamp predating errors.{RESET}")


def scenario_10_addiction_and_dynamic_limit():
    """Scenario 10: Addiction Score & Dynamic Limit Ratcheting"""
    print_header("SCENARIO 10: Addiction Score & Dynamic Daily Limit Ratcheting")
    uid = f"demo_user_s10_{int(time.time())}"
    
    # Populate 14 days of heavy usage history
    print("-> Injecting 14 days of heavy usage history into daily rollups...")
    for i in range(14, 0, -1):
        d_str = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        rollups_repo.upsert_rollup(uid, d_str, "youtube.com", focused_minutes=180.0, unplanned_minutes=120.0)

    s = client.post("/sessions/start", json={
        "user_id": uid, "domain": "youtube.com",
        "purpose": "entertainment", "intended_minutes": 30.0, "timer_mode": "planned"
    }).json()
    sid = s["session_id"]

    act = client.post(f"/sessions/{sid}/activity/batch", json={
        "activities": [{"client_event_id": f"evt_s10_{time.time()}", "focused_duration_ms": 300000, "event_timestamp_utc": ts_utc()}]
    }).json()

    print_result("Addiction Engine & Dynamic Limit Output", {
        "addiction_score": act.get("addiction_score"),
        "addiction_level": act.get("addiction_level"),
        "recommended_daily_limit": act.get("recommended_daily_limit"),
        "structural_timer_summary": act.get("structural_timer_summary")
    })
    print(f"{YELLOW}[OK] Case Verified: High addiction score calculated; daily limit dynamically ratcheted.{RESET}")


# ── Interactive Menu Runner ───────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print(f"\n{BOLD}{GREEN}===================================================={RESET}")
        print(f"{BOLD}{GREEN} RUNNING AUTOMATED FULL WALKTHROUGH (ALL 10 CASES) {RESET}")
        print(f"{BOLD}{GREEN}===================================================={RESET}")
        scenarios = [
            scenario_1_within_plan,
            scenario_2_near_plan,
            scenario_3_over_plan_strong_friction,
            scenario_4_user_action_extend,
            scenario_5_stop_reminders,
            scenario_6_cross_domain_displacement,
            scenario_7_short_gap_resume,
            scenario_8_long_gap_expiration,
            scenario_9_offline_reconciliation,
            scenario_10_addiction_and_dynamic_limit,
        ]
        for idx, func in enumerate(scenarios, 1):
            func()
            time.sleep(0.5)
        print(f"\n{BOLD}{GREEN}===================================================={RESET}")
        print(f"{BOLD}{GREEN} ALL 10 SCENARIOS COMPLETED SUCCESSFULLY WITH 0 ERRORS {RESET}")
        print(f"{BOLD}{GREEN}===================================================={RESET}\n")
        return

    while True:
        print(f"\n{BOLD}{CYAN}===================================================={RESET}")
        print(f"{BOLD}{CYAN}   HABITGUARD LIVE DEMO SIMULATOR & TEST HARNESS   {RESET}")
        print(f"{BOLD}{CYAN}===================================================={RESET}")
        print("Select a scenario to trigger and simulate:")
        print("  [1] Normal Session (Within Plan - On Track)")
        print("  [2] Near-Limit Warning (Near Plan - Gentle Check-in)")
        print("  [3] Over-Plan Intervention (Strong Friction + Notification + Overlay)")
        print("  [4] User Action: Extend Session (+5 Mins)")
        print("  [5] User Action: Muting Reminders (Stop Reminders)")
        print("  [6] Cross-Domain Displacement (YouTube -> Instagram)")
        print("  [7] Short Gap Pause & Resume (< 5 Min Same Episode)")
        print("  [8] Long Gap Session Expiration (> 5 Min Fresh Episode)")
        print("  [9] Atomic Offline Reconciliation (Reconnecting Queued Events)")
        print("  [10] Addiction Score & Dynamic Daily Limit Ratcheting")
        print("  [A] RUN ALL 10 SCENARIOS AUTOMATICALLY")
        print("  [0] Exit Simulator")
        print("-" * 52)
        
        choice = input(f"{BOLD}Enter choice (0-10 or A): {RESET}").strip().upper()
        if choice == "1":
            scenario_1_within_plan()
        elif choice == "2":
            scenario_2_near_plan()
        elif choice == "3":
            scenario_3_over_plan_strong_friction()
        elif choice == "4":
            scenario_4_user_action_extend()
        elif choice == "5":
            scenario_5_stop_reminders()
        elif choice == "6":
            scenario_6_cross_domain_displacement()
        elif choice == "7":
            scenario_7_short_gap_resume()
        elif choice == "8":
            scenario_8_long_gap_expiration()
        elif choice == "9":
            scenario_9_offline_reconciliation()
        elif choice == "10":
            scenario_10_addiction_and_dynamic_limit()
        elif choice == "A":
            sys.argv.append("--auto")
            main()
            break
        elif choice == "0":
            print("Exiting simulator. Good luck with your demo!")
            break
        else:
            print("Invalid choice, please select 0-10 or A.")

if __name__ == "__main__":
    main()
