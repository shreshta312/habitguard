# HabitGuard Limitations and Future Work

## 1. Purpose

This document records the current limitations of HabitGuard and the most meaningful directions for future development.

The project is functional as an academic prototype, but it should not be presented as a clinically validated or production-scale system.

---

## 2. Current Limitations

### 2.1 Browser-Only Tracking

HabitGuard currently measures supported Chrome browser usage.

It does not capture:

- complete smartphone usage,
- desktop applications,
- other browsers,
- cross-device activity,
- offline device activity.

Therefore, the system observes only part of the user's total digital behaviour.

### 2.2 Imperfect Context Classification

A domain does not have one universal purpose.

For example:

```text
youtube.com
```

may be used for:

- lectures,
- coding tutorials,
- music,
- entertainment,
- short-form distraction.

HabitGuard uses categories such as productive, mixed, neutral, and temptation, but these categories cannot fully infer user intent.

### 2.3 Calibration Sensitivity

The personal baseline depends on the calibration period.

Atypical days may distort the baseline, including:

- exams,
- holidays,
- illness,
- travel,
- project deadlines,
- temporary entertainment spikes.

### 2.4 Limited Longitudinal Validation

HabitGuard has not yet been evaluated through a long-term controlled user study.

Therefore, the project cannot yet prove that it causes sustained behaviour change.

### 2.5 Feedback Ambiguity

An overlay dismissal may mean:

- the intervention was annoying,
- the timing was poor,
- the user was busy,
- the user intended to stop soon,
- the current activity was important.

Feedback metrics are useful but not perfect indicators of intervention quality.

### 2.6 Estimated ML Features

The anomaly model expects launches and interactions.

The browser extension does not directly observe all device-level interactions.

Some values are therefore estimated from browser-session data.

These estimates reduce model precision.

### 2.7 Forecasting Performance

Previous forecasting results showed negative R-squared values.

This means the current model performed worse than a simple mean baseline on the corresponding test split.

The forecast is therefore:

```text
experimental
low-confidence
not used for interventions
```

### 2.8 Segmentation Verification

The segmentation pipeline was revised, but final retraining and complete endpoint verification remain pending.

Segment names should not yet be treated as final validated behavioural categories.

### 2.9 Dataset Generalisation

Public datasets may differ from real HabitGuard users in:

- age distribution,
- geography,
- device habits,
- application mix,
- culture,
- work patterns,
- self-report reliability.

Strong test accuracy on one dataset does not guarantee real-world performance.

### 2.10 No Clinical Validation

HabitGuard is not:

- a diagnostic tool,
- a treatment system,
- a substitute for a psychologist,
- a medical-device product.

Risk outputs are educational estimates only.

### 2.11 Localhost Configuration

The current system is designed primarily for local development.

Production use still requires:

- hosted backend,
- HTTPS,
- environment variables,
- production CORS,
- persistent hosted database,
- extension URL updates.

### 2.12 Single-User Local Identity

The current implementation primarily uses:

```text
local_user
```

A production system would require:

- authentication,
- user isolation,
- secure sessions,
- ownership checks,
- consent management.

### 2.13 SQLite Scalability

SQLite is appropriate for local use and academic demonstration.

It is less suitable for:

- many concurrent users,
- distributed deployment,
- high write volume,
- multi-instance hosting.

### 2.14 Intervention Fatigue

Even adaptive prompts may become repetitive.

Poorly tuned cooldowns can cause:

- notification fatigue,
- automatic dismissal,
- loss of trust,
- extension removal.

### 2.15 Accessibility

The extension and dashboard still require full accessibility review for:

- keyboard navigation,
- screen readers,
- contrast,
- reduced motion,
- focus visibility,
- readable intervention wording.

---

## 3. Future Work

### 3.1 Mobile Integration

Develop an Android companion application or digital-wellbeing integration to capture:

- app usage,
- unlock frequency,
- mobile sessions,
- cross-device behaviour.

### 3.2 Cross-Device Synchronisation

Synchronise browser and mobile usage through a secure backend.

This would provide a more complete digital-behaviour profile.

### 3.3 Improved Intent Detection

Future context models could combine:

- user category,
- time of day,
- session purpose,
- calendar context,
- active task,
- optional user confirmation.

Intent detection must remain privacy-preserving and transparent.

### 3.4 Robust Baseline Estimation

Replace a simple baseline with methods such as:

- median-based baseline,
- trimmed mean,
- weekday/weekend separation,
- rolling baseline,
- anomaly-resistant estimation,
- seasonal adjustment.

### 3.5 Personalised Cooldowns

Learn which cooldown duration works best for each user.

Possible inputs:

- acceptance history,
- domain,
- time of day,
- session duration,
- intervention type.

### 3.6 Better Forecasting

Compare:

- naive last-value baseline,
- moving average,
- exponential smoothing,
- gradient boosting,
- personalised models,
- time-series cross-validation.

A forecast model should only be promoted when it consistently beats simple baselines.

### 3.7 Segmentation Completion

Complete:

- final retraining,
- cluster-centre interpretation,
- label validation,
- endpoint testing,
- stability analysis,
- documentation of cluster sizes.

### 3.8 Explainable Analytics

Show why a result was generated.

Examples:

```text
Risk increased mainly because of:
high stress
low sleep
high social-media time
```

```text
Anomaly detected because:
screen time was much higher than recent history
```

### 3.9 PostgreSQL Migration

For hosted multi-user deployment:

```text
SQLite → PostgreSQL
```

This would improve:

- concurrency,
- reliability,
- migrations,
- cloud persistence,
- backup support.

### 3.10 Authentication and Consent

Add:

- account creation,
- secure login,
- explicit data consent,
- data export,
- data deletion,
- privacy settings.

### 3.11 Controlled User Study

Evaluate HabitGuard with real participants.

Possible measures:

- intervention acceptance,
- reduction in unplanned usage,
- perceived helpfulness,
- annoyance,
- retention,
- behaviour after several weeks.

### 3.12 Reinforcement Learning

A future system could learn intervention policies from user feedback.

This should only be attempted with:

- strong safety constraints,
- explainability,
- conservative exploration,
- explicit consent,
- rollback mechanisms.

### 3.13 Weekly Reports

Generate optional reports containing:

- total usage,
- baseline change,
- most distracting domains,
- productive sessions,
- intervention acceptance,
- completed breaks,
- recommendations.

### 3.14 Browser Store Publishing

Prepare the extension for Chrome Web Store release by completing:

- permissions review,
- privacy policy,
- icons,
- screenshots,
- versioning,
- packaged ZIP,
- store description.

### 3.15 Production Deployment

Deploy:

- FastAPI backend,
- persistent database,
- React dashboard,
- environment-based configuration,
- HTTPS API,
- restricted CORS.

### 3.16 Accessibility Improvements

Add:

- screen-reader labels,
- keyboard-only support,
- reduced-motion mode,
- high-contrast mode,
- accessible overlay focus handling.

---

## 4. Recommended Priority Order

### Priority 1: Release Reliability

```text
final pytest run
segmentation verification
extension clean-profile test
repository cleanup
```

### Priority 2: Submission Quality

```text
screenshots
professor presentation
demo rehearsal
final README review
```

### Priority 3: Deployment

```text
environment variables
hosted backend
persistent database
extension API URL update
production CORS
```

### Priority 4: Research Improvement

```text
longitudinal study
better baseline
improved forecasting
personalised timing
```

---

## 5. Final Positioning

HabitGuard should be presented as:

```text
A functional, privacy-conscious, JITAI-inspired academic prototype
for personalised digital-wellbeing support.
```

It should not be presented as:

```text
A clinically validated addiction-treatment system.
```

Its main contribution is the integration of:

```text
personal calibration
+ structural habit model
+ context-aware decisions
+ adaptive friction
+ user feedback
+ transparent supporting analytics
```
