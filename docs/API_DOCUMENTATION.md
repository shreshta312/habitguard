# HabitGuard API Documentation

## 1. Purpose

This document describes the main FastAPI endpoints used by HabitGuard.

The backend supports four major responsibilities:

- usage collection and dashboard summaries,
- personalised intervention decisions,
- feedback collection and adaptation,
- supporting machine-learning analytics.

The interactive FastAPI documentation should be treated as the final source for the exact request and response schema of the currently running backend.

Local API documentation:

```text
http://127.0.0.1:8000/docs
```

Local backend URL:

```text
http://127.0.0.1:8000
```

---

## 2. API Groups

HabitGuard endpoints can be grouped into:

```text
Intervention APIs
Usage APIs
Feedback APIs
Analytics APIs
Diagnostics APIs
```

---

## 3. Intervention API

### POST `/habitguard/custom/intervention`

Calculates a personalised intervention decision using:

- user usage history,
- current usage,
- active domain,
- domain category,
- current session duration,
- structural timer output,
- feedback history,
- cooldown rules.

This is the main endpoint used by the Chrome extension for live JITAI checks.

### Representative request

```json
{
  "user_id": "local_user",
  "current_domain": "youtube.com",
  "current_category": "temptation",
  "session_minutes": 15,
  "recent_usage_minutes": 52
}
```

The exact accepted fields depend on the current Pydantic schema.

### Representative response

```json
{
  "mode": "ACTIVE",
  "timer_active": true,
  "usage_status": "RISKY_USAGE_SPIKE",
  "friction_type": "STRONG_FRICTION",
  "intervention_type": "BREAK_PROMPT",
  "recommended_timer_minutes": 10,
  "baseline_usage_minutes": 22.1,
  "recent_usage_minutes": 52.0,
  "overuse_gap_minutes": 29.9,
  "rho_user": 0.05,
  "should_intervene": true,
  "should_notify": true,
  "should_overlay": true,
  "cooldown_minutes": 25,
  "decision_reason": "Usage is far above the personal baseline.",
  "delivery_reason": "Risky context and sustained session permit stronger friction."
}
```

### Important response fields

| Field | Meaning |
|---|---|
| `mode` | `CALIBRATION` or `ACTIVE` |
| `timer_active` | Whether personalised timer logic is active |
| `usage_status` | Current behavioural state |
| `friction_type` | Intervention intensity |
| `intervention_type` | Recommended behavioural action |
| `recommended_timer_minutes` | Suggested temporary timer |
| `baseline_usage_minutes` | Personal usage baseline |
| `recent_usage_minutes` | Recent measured usage |
| `overuse_gap_minutes` | Recent usage minus baseline |
| `rho_user` | Personal persistence estimate |
| `should_intervene` | Whether any intervention is recommended |
| `should_notify` | Whether notification delivery is allowed |
| `should_overlay` | Whether overlay delivery is allowed |
| `cooldown_minutes` | Wait period before another similar prompt |
| `decision_reason` | Explanation of the behavioural decision |
| `delivery_reason` | Explanation of the delivery choice |

### Extension delivery rule

The extension should follow the flags exactly.

```text
Notification:
should_intervene = true
AND should_notify = true
```

```text
Overlay:
should_intervene = true
AND should_overlay = true
```

The extension should not infer delivery permission from `friction_type` alone.

---

## 4. Usage APIs

### POST `/usage/snapshot`

Stores a browser usage snapshot.

The Chrome extension uses this endpoint to synchronise local usage state with the backend.

### Representative request

```json
{
  "user_id": "local_user",
  "timestamp": "2026-07-14T01:20:00",
  "today_usage_minutes": 53.2,
  "domain_usage": {
    "youtube.com": 20.0,
    "chatgpt.com": 18.2,
    "leetcode.com": 15.0
  },
  "current_session": {
    "domain": "chatgpt.com",
    "category": "mixed",
    "session_minutes": 3.4
  },
  "source": "chrome_extension"
}
```

The exact snapshot structure may include additional extension and intervention state.

### Typical response

```json
{
  "status": "saved",
  "user_id": "local_user"
}
```

### Storage behaviour

The backend stores usage in SQLite and makes it available to:

- the structural timer,
- the dashboard,
- anomaly analytics,
- forecasting analytics,
- calibration logic.

---

### GET `/usage/summary/local_user`

Returns the aggregated dashboard summary for the local extension user.

### Representative response

```json
{
  "user_id": "local_user",
  "dashboard_ready": true,
  "today_usage_minutes": 53.2,
  "baseline_usage_minutes": 22.1,
  "overuse_gap_minutes": 31.1,
  "days_tracked": 14,
  "top_domains": [
    {
      "domain": "youtube.com",
      "minutes": 20.0
    },
    {
      "domain": "chatgpt.com",
      "minutes": 18.2
    }
  ],
  "usage_trend": [
    {
      "date": "2026-07-08",
      "minutes": 44.0
    },
    {
      "date": "2026-07-09",
      "minutes": 51.0
    }
  ],
  "current_session": null,
  "latest_intervention": null,
  "anomaly": {
    "result": "NORMAL"
  },
  "forecast": {
    "predicted_usage_minutes": 48.0,
    "confidence": "LOW"
  }
}
```

### Summary contents

The summary may include:

- today's total usage,
- personal baseline,
- overuse gap,
- days tracked,
- seven-day trend,
- top domains,
- current session,
- latest intervention,
- active timer state,
- session statistics,
- intervention statistics,
- extension event statistics,
- anomaly result,
- forecast result,
- dashboard readiness state.

### Dashboard readiness

```text
dashboard_ready = true
```

means enough valid summary data is available for the dashboard to render.

---

## 5. Feedback APIs

### POST `/feedback/event`

Stores a feedback event generated by the extension.

Supported event types:

```text
overlay_dismissed
break_accepted
break_completed
break_skipped
```

### Representative request

```json
{
  "user_id": "local_user",
  "event_type": "overlay_dismissed",
  "domain": "youtube.com",
  "timestamp": "2026-07-14T01:25:00",
  "metadata": {
    "friction_type": "STRONG_FRICTION",
    "intervention_type": "BREAK_PROMPT"
  }
}
```

### Representative response

```json
{
  "status": "recorded",
  "event_type": "overlay_dismissed"
}
```

### Event meaning

| Event | Meaning |
|---|---|
| `overlay_dismissed` | User closed the overlay |
| `break_accepted` | User accepted the proposed break |
| `break_completed` | Break countdown reached the end |
| `break_skipped` | User ended the break early |

---

### GET `/feedback/summary?user_id=local_user`

Returns aggregated feedback statistics.

### Representative response

```json
{
  "user_id": "local_user",
  "total_events": 8,
  "event_type_counts": {
    "overlay_dismissed": 3,
    "break_accepted": 2,
    "break_completed": 1,
    "break_skipped": 2
  },
  "break_acceptance_rate": 0.4,
  "dismissal_rate": 0.6
}
```

### Acceptance-rate calculation

```math
AcceptanceRate =
AcceptedBreaks / (AcceptedBreaks + DismissedOverlays)
```

### Dismissal-rate calculation

```math
DismissalRate =
DismissedOverlays / (AcceptedBreaks + DismissedOverlays)
```

These statistics may influence later decision softening and cooldown behaviour.

---

## 6. Risk Analytics API

### POST `/risk/predict`

Returns a broad behavioural risk estimate from questionnaire features.

The risk model supports dashboard analytics only.

It does not control live interventions.

### Representative request

```json
{
  "age": 21,
  "sleep_hours": 6.5,
  "stress_level": 7,
  "daily_social_media_time": 180,
  "daily_gaming_time": 30,
  "app_opens": 65
}
```

The current model expects a larger complete feature set. The exact fields must be checked in `/docs`.

### Representative response

```json
{
  "prediction": 1,
  "risk_level": "HIGH",
  "confidence": 0.82,
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

### Risk labels

```text
0 → LOW
1 → HIGH
```

### Important limitation

This result is:

- educational,
- dataset-dependent,
- not a medical diagnosis,
- not used to determine live intervention delivery.

---

## 7. Segmentation API

### POST `/segment/predict`

Assigns a questionnaire profile to a behavioural cluster.

The segmentation model is a supporting dashboard feature.

### Representative request

```json
{
  "age": 21,
  "sleep_hours": 6.5,
  "stress_level": 7,
  "daily_social_media_time": 180,
  "daily_gaming_time": 30,
  "app_opens": 65
}
```

The exact complete feature list must be checked in `/docs`.

### Representative response

```json
{
  "cluster": 2,
  "segment_name": "Heavy Distracted",
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

### Current verification status

The segmentation preprocessing and service were revised, but final retraining and full end-to-end verification should be completed before the segment labels are treated as stable final results.

---

## 8. Diagnostics API

### GET `/diagnostics`

Returns health and model-loading information.

### Representative response

```json
{
  "status": "ok",
  "database": {
    "available": true
  },
  "models": {
    "risk_classifier": {
      "loaded": true
    },
    "user_segmentation": {
      "loaded": true
    },
    "anomaly_detector": {
      "loaded": true
    },
    "usage_forecaster": {
      "loaded": true
    }
  }
}
```

### Diagnostics purpose

The endpoint helps verify:

- database availability,
- model presence,
- model loading,
- preprocessing compatibility,
- fallback status,
- service readiness.

---

## 9. Anomaly and Forecast Data

Anomaly and forecast results are currently included in the usage summary rather than controlling the live JITAI decision.

### Anomaly result

Representative fields:

```json
{
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false,
  "screen_time_min": 53.2,
  "launches": 4,
  "interactions": 798,
  "is_productive": 0,
  "result": "NORMAL",
  "message": "Usage pattern looks normal."
}
```

### Forecast result

Representative fields:

```json
{
  "predicted_usage_minutes": 48.0,
  "confidence": "LOW",
  "fallback_used": true,
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

### Important limitation

Browser tracking does not directly provide all model features.

Therefore:

- launches may be approximated from sessions,
- interactions may be estimated from usage duration,
- forecast confidence may be reduced,
- results are supporting indicators only.

---

## 10. Error Handling

### 400 Bad Request

Used when input data is invalid or incomplete.

Example:

```json
{
  "detail": "Invalid event type."
}
```

### 404 Not Found

Used when requested user usage data is unavailable.

Example:

```json
{
  "detail": "Usage data not found for user."
}
```

### 422 Unprocessable Entity

Returned by FastAPI when the JSON payload does not match the Pydantic schema.

Example:

```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

### 500 Internal Server Error

Indicates an unexpected backend failure.

Core endpoints should avoid failing solely because an optional ML model is unavailable.

---

## 11. CORS

During local development, the backend must permit requests from:

```text
http://localhost:5173
```

and the Chrome extension origin.

Production deployment should replace permissive local settings with explicit trusted origins.

---

## 12. Local API Testing

### PowerShell: usage summary

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/usage/summary/local_user" `
    -Method GET
```

### PowerShell: feedback summary

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/feedback/summary?user_id=local_user" `
    -Method GET
```

### PowerShell: feedback event

```powershell
$body = @{
    user_id = "local_user"
    event_type = "overlay_dismissed"
    domain = "youtube.com"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/feedback/event" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

These commands should be used carefully because feedback events are persisted.

---

## 13. API Design Principles

HabitGuard follows these API principles:

```text
Core intervention logic should remain available even if ML fails.
```

```text
The extension should follow explicit delivery flags.
```

```text
Usage and feedback should be stored separately.
```

```text
Dashboard analytics should not silently control interventions.
```

```text
Errors should be clear rather than replaced with fabricated values.
```

---

## 14. Endpoint Summary

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/habitguard/custom/intervention` | Calculate a personalised JITAI decision |
| `POST` | `/usage/snapshot` | Save extension usage state |
| `GET` | `/usage/summary/local_user` | Retrieve dashboard summary |
| `POST` | `/feedback/event` | Record intervention feedback |
| `GET` | `/feedback/summary?user_id=local_user` | Retrieve feedback metrics |
| `POST` | `/risk/predict` | Supporting risk analytics |
| `POST` | `/segment/predict` | Supporting user segmentation |
| `GET` | `/diagnostics` | Check backend and model readiness |

---

## 15. Verification Note

Before final release:

1. Start the backend.
2. Open `/docs`.
3. Confirm every route listed here exists.
4. Compare the exact request fields with the Pydantic schemas.
5. Update any representative payload that differs from the final implementation.
6. Run the complete backend test suite.

This document explains the intended API contract, while the running FastAPI OpenAPI page remains the exact schema reference.
