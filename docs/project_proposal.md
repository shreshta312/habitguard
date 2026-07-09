# Project Proposal & System Specification

## HabitGuard: Intelligent Digital Wellbeing Platform

HabitGuard is a digital wellbeing platform that aims to replace static blocklists with responsive, Just-In-Time Adaptive Interventions (JITAI). By loading offline machine learning models directly on the client/backend boundary and monitoring live browsing context, the system provides personalized, context-aware reminders.

---

## 1. System Overview & Objectives
*   **Behavioral Calibration**: Tracks baseline user usage over time and automatically recalibrates intervention thresholds.
*   **Intelligent Intervention Decider**: Evaluates live browsing activity (temptation vs. mixed vs. productive sites) and applies progressive warnings (e.g. Timer warning vs. Soft/Strong warning overlays).
*   **Privacy-Centric Architecture**: Retains detailed browsing history locally inside the browser extension. Profile characteristics are processed on-demand and stored client-side in `localStorage`.

---

## 2. Technical Stack Specification

### Backend (Python/FastAPI)
*   **FastAPI**: Selected for asynchronous performance, automated OpenAPI documentation, and simple JSON endpoints.
*   **SQLite Persistence Layer**: Migrated from flat JSONL logs to SQLite to support atomic transactions, concurrent queries, and structural relational mapping.
*   **Scikit-Learn**: Loads trained models for anomaly detection, usage forecasting, overall addiction classification, and user segmentation.

### Frontend (React/Vite)
*   **Vite**: Dev server with fast HMR.
*   **Tailwind CSS**: Modern utility styling.
*   **Lucide React**: Vector icon system.
*   **Recharts**: SVG charting for usage trend visualization.

### Extension (Chrome Extension manifest v3)
*   **Background Worker**: Periodically monitors current tab URLs, schedules alarms, and manages local timers.
*   **Injectable Overlay**: Inserts lightweight DOM dialog overlays on temptation sites when triggered by a Strong Intervention decision.

---

## 3. Data Flow and API Endpoints

### 1. Usage Snapshot Sync
`POST /usage/snapshot`
*   **Purpose**: Receives daily usage breakdown and current session status from the extension, persisting it to the SQLite database.

### 2. Intervention Check
`POST /habitguard/custom/intervention`
*   **Purpose**: Processes the current domain context, checks the decision engine rules, and returns:
    *   `should_intervene` (boolean)
    *   `friction_type` (Soft warning, timer, strong warning, or none)
    *   `recommended_timer_minutes`
    *   `should_notify` / `should_overlay` (JITAI delivery directives)
    *   `delivery_reason` (contextual explanation)

### 3. Analytics Summary
`GET /usage/summary/local_user`
*   **Purpose**: Compiles daily time breakdowns, 7-day usage trends, and fires the Anomaly and Forecaster ML services to display insights on the dashboard.

### 4. Risk / Segment Predictions
`POST /risk/predict` and `POST /segment/predict`
*   **Purpose**: Runs voluntary user questionnaires against trained Random Forest and KMeans models.

### 5. Diagnostics
`GET /diagnostics`
*   **Purpose**: Collates model parameter info (tree depth, contamination ratios, features significance) for transparency.
