# HabitGuard Demonstration Guide

## 1. Purpose

This guide provides a clear professor-demo flow for HabitGuard.

The recommended demonstration duration is approximately:

```text
8 to 12 minutes
```

---

## 2. Before the Demonstration

Open three terminals.

### Terminal 1: Backend

```powershell
cd C:\Users\jimmi\.gemini\antigravity\scratch\habitguard\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2: Dashboard

```powershell
cd C:\Users\jimmi\.gemini\antigravity\scratch\habitguard\dashboard
npm.cmd run dev
```

Open:

```text
http://localhost:5173
```

### Chrome Extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Load the `chrome_extension` folder.
4. Refresh the website tab used for the demo.

---

## 3. Suggested Presentation Flow

### Step 1: Introduce the problem

Say:

> Most digital-wellbeing tools use fixed limits. HabitGuard instead learns the user's personal baseline and decides whether an intervention is suitable using usage, context, feedback, and cooldown.

### Step 2: Explain the architecture

Show the README or architecture diagram.

Explain:

```text
Chrome extension
→ FastAPI backend
→ StructuralTimerEngine
→ DecisionEngine
→ SQLite
→ React dashboard
```

Clarify:

> Machine learning supports dashboard analytics, but it does not control live interventions.

### Step 3: Show the dashboard

Point out:

- today's usage,
- baseline,
- overuse gap,
- suggested timer,
- usage trend,
- top domains,
- active session,
- anomaly result,
- forecast result.

### Step 4: Explain calibration

Say:

> HabitGuard observes approximately ten days of usage before activating personalised timer logic. This prevents it from applying an arbitrary limit immediately after installation.

Show:

```text
CALIBRATION
ACTIVE
```

### Step 5: Explain the mathematics

Use this example:

```text
Baseline = 22.1 minutes
Recent usage = 52.0 minutes
Overuse gap = 29.9 minutes
```

Formula:

```math
OveruseGap = RecentUsage - BaselineUsage
```

Explain that `rho_user` represents personalised behavioural persistence and is safety-clamped.

### Step 6: Show domain context

Open the extension popup.

Explain the categories:

```text
productive
mixed
neutral
temptation
```

Example:

> YouTube may be marked temptation during entertainment use, while LeetCode may be marked productive.

### Step 7: Trigger or show an intervention

Use a temptation-domain test or a prepared intervention state.

Show fields such as:

```text
should_intervene
should_notify
should_overlay
friction_type
recommended_timer_minutes
```

Explain:

> Decision and delivery are separate. The backend may recommend an intervention but suppress an overlay because of cooldown or productive context.

### Step 8: Show the overlay

Demonstrate:

- intervention message,
- break option,
- dismiss option,
- countdown.

### Step 9: Show feedback

Dismiss or accept the prompt.

Then query:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/feedback/summary?user_id=local_user" `
  -Method GET
```

Explain the event types:

```text
overlay_dismissed
break_accepted
break_completed
break_skipped
```

### Step 10: Explain adaptation

Say:

> Repeated dismissal can soften future intervention strength or increase cooldown. This helps HabitGuard avoid becoming annoying.

### Step 11: Show FastAPI documentation

Open:

```text
http://127.0.0.1:8000/docs
```

Show:

- usage endpoint,
- intervention endpoint,
- feedback endpoint,
- risk endpoint,
- segmentation endpoint,
- diagnostics endpoint.

### Step 12: Explain ML honestly

Say:

> The risk classifier, anomaly detector, segmentation model, and forecaster are supporting analytics. They do not directly trigger the overlay.

Mention:

- risk classifier performed well on its held-out dataset,
- anomaly detection distinguishes normal and spike patterns,
- forecasting remains experimental,
- final segmentation retraining is still pending.

---

## 4. Recommended Live Commands

### Usage summary

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/usage/summary/local_user" `
  -Method GET |
  ConvertTo-Json -Depth 10
```

### Feedback summary

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/feedback/summary?user_id=local_user" `
  -Method GET |
  ConvertTo-Json -Depth 10
```

### Backend tests

```powershell
cd C:\Users\jimmi\.gemini\antigravity\scratch\habitguard\backend
python -m pytest
```

### Dashboard build

```powershell
cd C:\Users\jimmi\.gemini\antigravity\scratch\habitguard\dashboard
npm.cmd run build
```

---

## 5. Questions You Should Be Ready to Answer

### Why not use a fixed timer?

Because normal usage differs across users. HabitGuard compares the user with their own historical baseline.

### Why ten days?

It provides an initial observation window long enough to avoid using only one or two unusual days. It is still a design choice, not a universal scientific constant.

### What is `rho_user`?

A personalised estimate of behavioural persistence derived from observed usage and bounded for safety.

### Does ML trigger interventions?

No. Live interventions are controlled by the structural timer, decision engine, context, feedback, and cooldown.

### How is intent detected?

HabitGuard uses user-adjustable domain categories. It does not claim to fully infer intent automatically.

### What happens when the backend is unavailable?

Local extension tracking should continue, while backend-dependent decisions are skipped or retried safely.

### Is HabitGuard a medical system?

No. It is an academic digital-wellbeing and behavioural-support project.

### Why use SQLite?

It provides structured, queryable, transactional local storage and is simpler than maintaining raw JSONL files.

### Why is forecasting weak?

Browser behaviour is highly variable and the available dataset does not capture every real-life factor. The forecast is therefore exploratory.

---

## 6. Screenshots to Capture

Add these before final submission:

```text
docs/images/dashboard-light.png
docs/images/dashboard-dark.png
docs/images/extension-popup.png
docs/images/intervention-overlay.png
docs/images/break-countdown.png
docs/images/feedback-summary.png
docs/images/fastapi-docs.png
docs/images/test-results.png
```

---

## 7. Demo Safety Notes

Before presenting:

- restart backend,
- refresh extension,
- verify dashboard loads,
- confirm no synthetic session remains active,
- keep a prepared screenshot in case the overlay does not appear,
- do not depend entirely on live network deployment,
- keep `/docs` open in another tab,
- keep the feedback-summary command ready.

---

## 8. One-Minute Summary

> HabitGuard is a JITAI-inspired digital-wellbeing assistant. A Chrome extension tracks browser sessions and sends usage to a FastAPI backend. After a calibration period, the StructuralTimerEngine calculates a personal baseline and overuse gap. The DecisionEngine combines this with domain context, session duration, feedback history, and cooldown rules to decide whether to deliver a notification or overlay. User actions are stored in SQLite and influence future intervention strength. A React dashboard visualises usage, while machine-learning models provide supporting risk, anomaly, segmentation, and forecast analytics without controlling the live intervention loop.
