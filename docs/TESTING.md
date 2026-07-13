# HabitGuard Testing and Verification

## 1. Purpose

This document records the testing strategy, verified workflows, current results, and final checks required before release.

---

## 2. Backend Tests

Run:

```bash
cd backend
python -m pytest -v
```

A previous full run reached:

```text
56 passed
```

A final complete run should be performed immediately before the release commit.

### Main areas covered

- usage endpoints,
- intervention endpoints,
- feedback events,
- feedback summaries,
- structural timer behaviour,
- calibration mode,
- active mode,
- decision-engine responses,
- safety clamps,
- API validation,
- ML-service fallbacks.

---

## 3. Dashboard Build Test

Run:

```bash
cd dashboard
npm run build
```

Verified result:

```text
Vite production build completed successfully.
```

The bundle-size message is an optimisation warning, not a build failure.

---

## 4. Verified End-to-End Flow

The following complete path has been manually verified:

```text
Browser usage
→ Chrome extension session tracking
→ FastAPI intervention request
→ StructuralTimerEngine
→ DecisionEngine
→ natural intervention overlay
→ user action
→ feedback API
→ SQLite storage
→ feedback summary
```

Verified backend decision fields included:

```text
should_intervene = true
should_overlay = true
should_notify = true
friction_type = STRONG_FRICTION
usage_status = RISKY_USAGE_SPIKE
```

---

## 5. Verified Feedback Events

The following events were tested:

```text
overlay_dismissed
break_accepted
break_completed
break_skipped
```

A verified feedback summary included:

```json
{
  "total_events": 8,
  "event_type_counts": {
    "overlay_dismissed": 3,
    "break_accepted": 2,
    "break_completed": 1,
    "break_skipped": 2
  },
  "break_acceptance_rate": 0.4
}
```

From these values:

```text
Acceptance rate = 40%
Dismissal rate = 60%
```

---

## 6. Verified Usage Summary

The dashboard summary endpoint was verified to return:

- dashboard readiness,
- daily usage total,
- baseline usage,
- overuse gap,
- days tracked,
- seven-day trend,
- top domains,
- current session,
- latest intervention,
- intervention statistics,
- extension statistics,
- anomaly result,
- forecast result.

Representative endpoint:

```http
GET /usage/summary/local_user
```

---

## 7. Calibration Tests

Calibration behaviour should verify:

```text
Insufficient history
→ mode = CALIBRATION
→ timer_active = false
```

```text
Sufficient history
→ mode = ACTIVE
→ timer_active = true
```

Example calibration output:

```text
days_available = 5
days_required = 10
days_remaining = 5
```

---

## 8. Structural Timer Tests

Verify:

- baseline calculation,
- recent usage calculation,
- overuse-gap calculation,
- personalised persistence,
- minimum and maximum clamps,
- negative-target protection,
- timer recommendation,
- insufficient-history fallback.

Example:

```text
baseline_usage_minutes = 22.1
recent_usage_minutes = 52.0
overuse_gap_minutes = 29.9
```

---

## 9. Decision Engine Tests

Verify decisions for:

- stable usage,
- slightly elevated usage,
- high usage,
- risky spikes,
- productive context,
- temptation context,
- active cooldown,
- low feedback acceptance,
- strong friction,
- notification-only delivery,
- overlay delivery.

The extension must obey:

```text
show notification only when
should_intervene = true
AND should_notify = true
```

```text
show overlay only when
should_intervene = true
AND should_overlay = true
```

---

## 10. Extension Reliability Checks

Before final release, verify:

1. Tracking resumes after Chrome restart.
2. Backend downtime does not crash the extension.
3. Productive domains do not receive unnecessary strong friction.
4. Temptation domains can receive stronger friction when appropriate.
5. Overlay cooldown prevents repeated prompts.
6. Notification cooldown prevents notification spam.
7. Content-script failure is handled safely.
8. Break completion records `break_completed`.
9. Early break exit records `break_skipped`.
10. Usage snapshots continue after temporary backend failure.

---

## 11. ML Verification

### Risk classifier

Verify:

- model loads,
- low-risk input returns `LOW`,
- high-risk input returns `HIGH`,
- invalid input is rejected,
- result is marked as supporting analytics.

### Segmentation

Still required:

- retrain final pipeline,
- restart backend,
- submit questionnaire,
- confirm cluster and name,
- add endpoint test.

### Anomaly detector

Verify:

```text
normal pattern → NORMAL
obvious spike → ANOMALY
```

### Forecaster

Verify:

- normal model path,
- insufficient-history fallback,
- low-confidence disclosure,
- no effect on live intervention decisions.

---

## 12. Database Checks

Verify:

- usage snapshots persist,
- feedback events persist,
- data survives backend restart,
- duplicate writes are handled,
- invalid events are rejected,
- local database files are ignored by Git.

Recommended ignored patterns:

```gitignore
*.db
*.sqlite
*.sqlite3
```

---

## 13. Final Release Checklist

Run:

```bash
cd backend
python -m pytest -v
```

Then:

```bash
cd ../dashboard
npm run build
```

Then inspect:

```bash
cd ..
git status --short
git diff --check
```

Required before release:

- all backend tests pass,
- dashboard builds,
- no accidental backup files,
- no database files staged,
- no generated build files staged,
- segmentation status documented honestly,
- README and docs render correctly,
- extension tested in a clean Chrome profile.

---

## 14. Current Verification Status

### Verified

- natural extension-to-backend intervention flow,
- natural overlay delivery,
- overlay dismissal feedback,
- break acceptance,
- break completion,
- break skipping,
- SQLite feedback storage,
- usage summary,
- feedback summary,
- dashboard build,
- structural-timer safety behaviour,
- risk-service revision.

### Still required

- final full test run,
- final segmentation retraining,
- clean-profile extension test,
- deployment test,
- production CORS and URL test.

---

## 15. Summary

HabitGuard has a verified working core:

```text
tracking
→ personal calibration
→ intervention decision
→ delivery
→ feedback
→ persistence
→ dashboard summary
```

The remaining testing work is mainly final release verification rather than basic feature construction.
