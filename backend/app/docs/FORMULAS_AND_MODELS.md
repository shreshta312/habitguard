# HabitGuard Active Formulas, Optimization Engine & Parameter Taxonomy

This document describes all mathematical equations, optimization terms, parameters, classification tags, and provenance labels in the HabitGuard codebase.

---

## Formula Classification Taxonomy

Every formula in HabitGuard is categorized into one of four explicit classification tags:
- **`ACTIVE_CANONICAL`**: Used in live real-time decision-making, JITAI intervention triggers, or session optimization.
- **`ANALYTICS_ONLY`**: Used strictly for post-hoc research, offline forecasting, anomaly detection, or dashboard metrics.
- **`LEGACY_ONLY`**: Retained for backward-compatible fallback endpoints only.
- **`REFERENCE_ONLY`**: Theoretical formulation from literature (e.g. Allcott et al. 2022) not directly evaluated in production loops.

---

## 1. Intent Episode Resumption & Interruption Gap

- **Classification Tag**: `ACTIVE_CANONICAL`
- **Formula ID**: `FORMULA_INTENT_RESUME_GAP`
- **Equation**:
  $$\text{gap}_{\text{minutes}} = \frac{\text{now}_{\text{UTC}} - \text{unfocused\_at\_utc}}{60.0}$$
- **Units**: Minutes.
- **Scope**: Intent episode boundary resolution (`(user_id, domain)`).
- **Behavior**: An active intent episode is resumed when $\text{gap}_{\text{minutes}} \le 3.0$ and the user has not explicitly finished the episode. If $\text{gap}_{\text{minutes}} > 3.0$, the active episode is expired (`expiry_reason = 'gap_timeout'`) and a new episode is initialized.
- **Provenance**: `VERSIONED_DEFAULT` (`INTENT_RESUME_GAP_MINUTES = 3.0`).
- **Active Call Sites**: `backend/app/db/repositories/sessions.py:resolve_intent_episode`.
- **Tests**: `backend/tests/test_intent_and_extensions.py`, `backend/tests/test_final_stabilization.py`.

---

## 2. Explicit Plan & Overrun Accounting

- **Classification Tag**: `ACTIVE_CANONICAL`
- **Formula ID**: `FORMULA_EXPLICIT_PLAN_ACCOUNTING`
- **Equations**:
  $$P_{\text{effective}} = P_{\text{original}} + \text{extension\_minutes}$$
  $$P_{\text{planned}} = \min(u_{\text{episode}}, P_{\text{effective}})$$
  $$u_{\text{unplanned}} = \max(0.0, u_{\text{episode}} - P_{\text{effective}})$$
  $$\text{overuse\_gap} = \max(0.0, u_{\text{episode}} - P_{\text{effective}})$$
- **Units**: Minutes.
- **Scope**: Canonical intent episode accounting (`EPISODE` scope).
- **Provenance**: `USER_SELECTED` ($P_{\text{original}}$, extensions) and `HABITGUARD_PROPOSED` (accounting split).
- **Active Call Sites**: `backend/app/main.py:add_activity_batch`, `record_session_action`.
- **Tests**: `backend/tests/test_session_status_and_actions.py`.

---

## 3. Session Optimization Grid Search Solver

- **Classification Tag**: `ACTIVE_CANONICAL`
- **Formula ID**: `FORMULA_SESSION_OPTIMIZATION_GRID`
- **Objective Function**:
  $$J(x) = \alpha \cdot U_{\text{cost}}(x) + \beta \cdot T_{\text{estimate}} \cdot U_{\text{cost}}(x) + \lambda \cdot D_{\text{plan}}(x) + \gamma \cdot G_{\text{goal}}(x)$$
  where:
  - $U_{\text{cost}}(x) = \frac{x}{60}$ (usage duration in hours, range $[0.0, 8.0]$)
  - $T_{\text{estimate}} \in [0.0, 1.0]$ (temptation score, range $[0.0, 1.0]$)
  - $D_{\text{plan}}(x) = \left(\frac{x - P_{\text{effective}}}{P_{\text{effective}} + 1e-5}\right)^2$ (plan deviation, range $[0.0, \infty)$)
  - $G_{\text{goal}}(x) = \frac{\max(0.0, x - C_{\text{allowance}})}{60}$ (cross-domain goal overrun in hours, range $[0.0, \infty)$)
- **Feasibility Constraint**: $U(x) \ge U_{\text{min}} = 0.35$ and $x \ge \max(0.0, u_{\text{used}}, \text{necessary\_minimum})$.
- **Objective Component Breakdown (Exposed on every run)**:
  - `usage_cost_contribution`: $\alpha \cdot \frac{x}{60}$
  - `temptation_cost_contribution`: $\beta \cdot T_{\text{estimate}} \cdot \frac{x}{60}$
  - `plan_deviation_contribution`: $\lambda \cdot D_{\text{plan}}(x)$
  - `goal_deviation_contribution`: $\gamma \cdot G_{\text{goal}}(x)$
- **Coefficients & Provenance**:
  - $\alpha = 0.25$ (`VERSIONED_DEFAULT`)
  - $\beta = 0.30$ (`VERSIONED_DEFAULT`)
  - $\lambda = 0.20$ (`VERSIONED_DEFAULT`)
  - $\gamma = 0.15$ (`VERSIONED_DEFAULT`)
  - $U_{\text{min}} = 0.35$ (`VERSIONED_DEFAULT` from `SYSTEM_PARAMETERS["utility_parameters"]`)
- **Active Call Sites**: `backend/app/services/session_optimization_engine.py:solve`.
- **Tests**: `backend/tests/test_target_ratcheting.py`, `backend/tests/test_temptation_objective_verification.py`.

---

## 4. Bounded EMA Personal Adaptation

- **Classification Tag**: `ACTIVE_CANONICAL`
- **Formula ID**: `FORMULA_BOUNDED_EMA_ADAPTATION`
- **Equation**:
  $$L_{\text{next}} = \text{clip}\left((1 - \eta_{\text{EMA}}) \cdot L_{\text{current}} + \eta_{\text{EMA}} \cdot \text{obs}_{\text{bounded}}, L_{\text{min}}, L_{\text{max}}\right)$$
  where $\eta_{\text{EMA}} = \min(0.25, 0.15)$, $L_{\text{min}} = 5.0$, $L_{\text{max}} = 180.0$, and max per-event increase is capped at $+15.0$ minutes.
- **Scope**: Contextual parameters per $(user\_id, domain, purpose)$ for `work_study` and `necessary` tasks ONLY.
- **Provenance**: `PERSONALLY_LEARNED`.
- **Active Call Sites**: `backend/app/services/personal_adaptation_service.py:process_feedback_event`.
- **Tests**: `backend/tests/test_adaptation_wiring.py`, `backend/tests/test_feedback_adaptation.py`.

---

## 5. Cross-Domain Distracting Goal Allowance

- **Classification Tag**: `ACTIVE_CANONICAL`
- **Formula ID**: `FORMULA_CROSS_DOMAIN_ALLOWANCE`
- **Equation**:
  $$\text{remaining\_goal\_budget} = \max\left(0.0, \text{target\_daily} - \text{focused\_minutes\_used\_today}\right)$$
- **Units**: Minutes.
- **Scope**: User daily distracting usage allowance.
- **Provenance**: `USER_SELECTED` (reduction target %) and `DIRECTLY_MEASURED` (rollups).
- **Active Call Sites**: `backend/app/services/cross_domain_goal_service.py:_compute_allowance`.
- **Tests**: `backend/tests/test_cross_domain.py`.

---

## 6. Structural Quasi-Hyperbolic Discounting Model (Literature Reference)

- **Classification Tag**: `REFERENCE_ONLY`
- **Formula ID**: `FORMULA_LITERATURE_QUASI_HYPERBOLIC`
- **Equation**:
  $$V_0 = u_0 + \beta \sum_{t=1}^T \delta^t u_t$$
- **Note**: Structural quasi-hyperbolic parameters ($\eta = -2.68, \zeta = 3.08, \gamma = 1.09$) from Allcott et al. (2022) are population reference defaults used to initialize baseline priors. They are NOT updated by real-time session feedback loops.

---

## Provenance Labels Taxonomy

- `PAPER_EQUATION`: Structural equations from Allcott et al. (2022).
- `PAPER_POPULATION_DEFAULT`: Calibrated population parameters ($\eta = -2.68, \zeta = 3.08, \gamma = 1.09$).
- `USER_SELECTED`: User explicit inputs (intended minutes, reduction percentage).
- `DIRECTLY_MEASURED`: Recorded active focus time and daily rollups.
- `PERSONALLY_LEARNED`: Contextual EMA-adapted parameters.
- `VERSIONED_DEFAULT`: Engine defaults (step size, default cooldowns, grace periods).
- `SAFETY_BOUND`: Absolute floor/ceiling bounds ($L_{\text{min}}=5.0, L_{\text{max}}=180.0$).
- `HABITGUARD_PROPOSED`: HabitGuard-specific multi-objective term formulations.
