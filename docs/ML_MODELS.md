# HabitGuard Machine-Learning Models

## 1. Purpose

This document explains the machine-learning components used in HabitGuard.

The most important architectural rule is:

```text
Machine learning does not control the live intervention loop.
```

Live interventions are produced by:

```text
StructuralTimerEngine
        ↓
DecisionEngine
        ↓
Context and feedback policy
```

Machine-learning models provide supporting analytics for the dashboard.

They help answer questions such as:

- Does the current usage pattern look unusual?
- What broad questionnaire-based risk category is predicted?
- Which behavioural cluster is the user closest to?
- What level of usage may occur next?

These outputs improve awareness and explanation, but they do not directly decide whether the Chrome extension displays a notification or overlay.

---

## 2. Model Overview

HabitGuard currently contains four analytics models.

| Model | Algorithm | Purpose | Live intervention control |
|---|---|---|---|
| Risk classifier | Random Forest Classifier | Estimate broad questionnaire-based risk | No |
| User segmentation | KMeans clustering | Group users into behavioural profiles | No |
| Anomaly detector | Isolation Forest | Detect unusual usage patterns | No |
| Usage forecaster | Random Forest Regressor | Estimate future usage | No |

The saved models are stored under the machine-learning model directory.

Representative location:

```text
ml/saved_models/
```

---

## 3. Why ML Is Kept Separate

Using ML directly inside the intervention loop would create several problems:

- model failure could block interventions,
- predictions may be difficult to explain,
- public datasets may not match real extension users,
- browser features may differ from training features,
- a forecast error could cause unnecessary friction,
- model retraining could unexpectedly change behaviour.

HabitGuard therefore keeps the live intervention system deterministic and explainable.

```text
Core intervention logic:
personal baseline
+ overuse gap
+ context
+ feedback
+ cooldown
```

ML results remain optional dashboard insights.

---

## 4. Risk Classifier

### 4.1 Purpose

The risk classifier estimates a broad addiction-risk category from questionnaire-based demographic and behavioural features.

It is not a clinical diagnosis.

### 4.2 Algorithm

```text
RandomForestClassifier
```

Random forests combine multiple decision trees and aggregate their predictions.

Advantages for this project include:

- support for nonlinear feature relationships,
- limited preprocessing requirements,
- robustness to feature interactions,
- probability-based confidence output,
- interpretability through feature importance.

### 4.3 Input Features

The model uses profile features such as:

- age,
- sleep hours,
- stress level,
- social-media usage,
- gaming usage,
- app-opening frequency,
- productivity-related behaviour,
- other demographic and behavioural indicators available in the cleaned dataset.

The current training design uses approximately 13 profile indicators.

The exact feature order must remain consistent between training and inference.

### 4.4 Preprocessing Pipeline

The revised risk pipeline includes preprocessing and prediction in one persisted object.

Conceptually:

```text
Raw questionnaire values
        ↓
Missing-value handling
        ↓
Feature scaling where required
        ↓
RandomForestClassifier
        ↓
Risk prediction
```

Persisting preprocessing with the model reduces the risk of training-serving mismatch.

### 4.5 Output

The dashboard uses binary labels:

```text
0 → LOW
1 → HIGH
```

Representative response:

```json
{
  "prediction": 1,
  "risk_level": "HIGH",
  "confidence": 0.82,
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

### 4.6 Previous Evaluation

A previous training run produced:

```text
Dataset size: 7500 rows
Accuracy: 0.9333
```

Confusion matrix:

```text
[[392, 46],
 [54, 1008]]
```

This means:

- 392 low-risk samples were classified correctly,
- 46 low-risk samples were classified as high risk,
- 54 high-risk samples were classified as low risk,
- 1008 high-risk samples were classified correctly.

Accuracy alone should not be treated as complete proof of generalisation.

The result depends on:

- dataset quality,
- label construction,
- train-test split,
- class balance,
- similarity between dataset users and real HabitGuard users.

### 4.7 Limitations

The risk model:

- is trained on public or external data,
- may not represent every user population,
- uses self-reported or derived features,
- produces a broad category rather than a clinical assessment,
- should not determine intervention intensity.

---

## 5. User Segmentation

### 5.1 Purpose

User segmentation groups users with similar behavioural questionnaire patterns.

Segmentation does not predict a medically meaningful class.

It identifies broad behavioural clusters that may help explain user patterns.

### 5.2 Algorithm

```text
KMeans
```

KMeans attempts to divide data into clusters by minimising the distance between each sample and its assigned cluster centre.

### 5.3 Input Features

The segmentation model uses a profile feature set aligned with the questionnaire, such as:

- age,
- sleep,
- stress,
- social-media usage,
- gaming usage,
- app-opening behaviour,
- productivity-related indicators.

### 5.4 Preprocessing

Distance-based clustering is sensitive to feature scale.

For example:

```text
age = 21
daily usage minutes = 240
stress level = 8
```

Without scaling, the usage feature may dominate distance calculations.

The revised segmentation pipeline therefore includes:

```text
Raw questionnaire values
        ↓
Missing-value imputation
        ↓
StandardScaler
        ↓
KMeans
```

### 5.5 Segment Names

Representative human-readable names may include:

- Casual User,
- Productivity Focused,
- Heavy Distracted,
- Late Night / High Usage.

These labels are descriptive mappings applied after inspecting cluster centres.

KMeans itself produces only numeric cluster identifiers.

Example:

```text
cluster = 2
```

The service may map that cluster to:

```text
Heavy Distracted
```

### 5.6 Verification Status

The segmentation training and inference code were revised to use a persisted preprocessing pipeline.

However, final retraining and end-to-end verification were not completed in the documented workflow.

Therefore:

```text
Segmentation implementation: revised
Final retraining: still required
Final live endpoint verification: still required
Stable final labels: not yet confirmed
```

This limitation must remain visible in the project documentation.

### 5.7 Required Final Verification

Before final release:

1. Retrain the segmentation pipeline.
2. Save the complete pipeline.
3. Restart the backend.
4. Submit a complete questionnaire.
5. Confirm a valid cluster is returned.
6. Confirm the segment name matches the saved cluster mapping.
7. Test missing and invalid input.
8. Add an automated endpoint test.

---

## 6. Anomaly Detector

### 6.1 Purpose

The anomaly detector identifies usage patterns that differ significantly from the patterns present in its training data.

It may help flag:

- unusually high screen time,
- unusual launch frequency,
- unusually intense interaction estimates,
- usage patterns inconsistent with productive behaviour.

### 6.2 Algorithm

```text
IsolationForest
```

Isolation Forest detects anomalies by measuring how easily a data point can be isolated through random partitions.

Unusual points are generally isolated more quickly.

### 6.3 Features

The model uses:

```text
screen_time_min
launches
interactions
is_productive
```

### 6.4 Browser Feature Mismatch

The Chrome extension directly records browser sessions and durations.

It does not directly record:

- every device-level app launch,
- every click,
- every keystroke,
- every physical interaction.

Therefore, the backend may approximate:

```text
launches
interactions
```

from browser session information.

Representative strategy:

```text
launches ≈ number of observed sessions
interactions ≈ screen_time_minutes × multiplier
```

These are modelling proxies, not literal measurements.

### 6.5 Output

Representative response:

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

Possible result values include:

```text
NORMAL
ANOMALY
```

### 6.6 Previous Manual Checks

Representative manual tests included:

```text
Normal pattern:
screen time = 25
launches = 3
interactions = 5
result = NORMAL
```

```text
Spike pattern:
screen time = 180
launches = 1
interactions = 4
result = ANOMALY
```

These checks confirm that the model responds differently to clearly different inputs.

They do not establish real-world clinical validity.

### 6.7 Limitations

The anomaly result is limited by:

- estimated features,
- training-data distribution,
- browser-only tracking,
- lack of long-term personal retraining,
- possible false positives during legitimate long sessions.

An anomaly means:

```text
unusual relative to the model's learned data
```

It does not mean:

```text
addicted
harmful
clinically abnormal
```

---

## 7. Usage Forecaster

### 7.1 Purpose

The usage forecaster estimates a future usage value for dashboard awareness.

It is intended to support reflection, not to enforce a timer.

### 7.2 Algorithm

```text
RandomForestRegressor
```

### 7.3 Features

Representative forecasting features include:

```text
usage_lag_1
usage_lag_2
usage_lag_3
usage_rolling_mean_3
launches_lag_1
interactions_lag_1
is_productive
```

These features represent recent history and short-term usage trends.

### 7.4 Output

Representative response:

```json
{
  "predicted_usage_minutes": 48.0,
  "confidence": "LOW",
  "fallback_used": false,
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

### 7.5 Fallback Behaviour

When insufficient history is available, the service may use a moving average.

Example:

```text
available history < required lag history
→ calculate recent average
→ return fallback prediction
→ mark confidence as LOW
```

This is preferable to returning a fabricated high-confidence prediction.

### 7.6 Previous Evaluation

Two previous forecasting runs produced limited results.

Run A:

```text
MAE = 12.77
MSE = 231.01
R² = -0.20
```

Run B:

```text
MAE = 23.27
MSE = 877.99
R² = -0.208
```

A negative R² means the model performed worse than a simple mean-based baseline on the corresponding test split.

Therefore, the current forecast must be described as:

```text
experimental
exploratory
low-confidence
not suitable for intervention control
```

### 7.7 Limitations

Forecasting is difficult because usage changes with:

- exams,
- holidays,
- deadlines,
- mood,
- work requirements,
- social events,
- device switching,
- new applications,
- incomplete browser data.

Future versions should compare the Random Forest with:

- naive last-value forecasting,
- moving averages,
- exponential smoothing,
- gradient boosting,
- time-series cross-validation,
- personalised per-user models.

---

## 8. Model Service Design

Each backend ML service should:

- load its model safely,
- validate input features,
- preserve feature order,
- return a clear prediction,
- expose model role,
- state whether it is used in the live loop,
- fail without breaking core HabitGuard functions.

Representative metadata:

```json
{
  "model_role": "supporting_dashboard_analytics",
  "used_in_live_intervention_loop": false
}
```

This prevents the dashboard from implying that analytics models control interventions.

---

## 9. Safe Model Loading

Saved scikit-learn models may fail to load because of:

- missing files,
- incompatible library versions,
- changed feature order,
- changed preprocessing,
- corrupted pickle files.

Services should handle this by:

```text
attempt model load
        ↓
validate object
        ↓
record diagnostics
        ↓
return unavailable or fallback state if necessary
```

Core usage and intervention endpoints should remain operational when an optional model is unavailable.

---

## 10. Training-Serving Consistency

A common ML failure occurs when training and inference use different preprocessing.

Example:

```text
Training:
fill missing values
scale features
train model
```

but inference sends:

```text
raw unscaled values directly to model
```

This can produce invalid results even when the endpoint runs without an exception.

HabitGuard reduces this risk by persisting pipelines that include:

- imputation,
- scaling where needed,
- model prediction.

Conceptually:

```text
pipeline.predict(raw_input)
```

is safer than manually recreating preprocessing in multiple files.

---

## 11. Questionnaire Handling

The dashboard questionnaire provides model features.

The system should validate:

- required fields,
- numeric ranges,
- missing values,
- impossible values,
- feature order.

Examples of invalid data include:

```text
age = -5
sleep_hours = 40
stress_level = 1000
```

Validation should reject or safely normalise invalid input rather than silently passing it to the model.

Questionnaire results should not be stored as medical records or presented as diagnoses.

---

## 12. Diagnostics

The diagnostics service should report:

```text
model file exists
model loaded
pipeline type
expected feature count
model version where available
fallback active
last load error
```

Representative response:

```json
{
  "risk_classifier": {
    "loaded": true,
    "pipeline": true,
    "status": "ready"
  },
  "user_segmentation": {
    "loaded": false,
    "status": "retraining_required"
  },
  "anomaly_detector": {
    "loaded": true,
    "status": "ready"
  },
  "usage_forecaster": {
    "loaded": true,
    "status": "experimental"
  }
}
```

---

## 13. Evaluation Principles

Model evaluation should include more than accuracy.

### Risk classifier

Useful metrics include:

- accuracy,
- precision,
- recall,
- F1-score,
- confusion matrix,
- class distribution,
- probability calibration.

### Segmentation

Useful checks include:

- silhouette score,
- inertia,
- cluster size balance,
- cluster-centre interpretation,
- stability across random seeds.

### Anomaly detection

Useful checks include:

- expected anomaly rate,
- manual normal and spike cases,
- sensitivity to proxy features,
- false-positive review.

### Forecasting

Useful metrics include:

- MAE,
- RMSE,
- R²,
- comparison with naive baseline,
- time-series cross-validation,
- error by user.

---

## 14. Data Leakage Prevention

Data leakage occurs when information from the test set influences model training.

HabitGuard training scripts should ensure:

- train-test split occurs before fitting preprocessing,
- scalers are fitted only on training data,
- future values are not used to create past forecasting features,
- the same user's near-duplicate rows are handled carefully,
- target-derived columns are excluded from inputs.

Using a scikit-learn pipeline helps prevent preprocessing leakage.

---

## 15. Ethical Interpretation

The analytics must be described carefully.

Correct wording:

```text
The model estimates a broad risk category.
```

Incorrect wording:

```text
The model proves the user is addicted.
```

Correct wording:

```text
The anomaly detector found an unusual pattern.
```

Incorrect wording:

```text
The user has abnormal behaviour.
```

Correct wording:

```text
The forecast is an experimental estimate.
```

Incorrect wording:

```text
The system knows tomorrow's exact usage.
```

---

## 16. Model Limitations

The current ML layer has these limitations:

- public datasets may not match extension users,
- questionnaire values may be self-reported,
- browser data does not represent complete device usage,
- anomaly features include estimates,
- forecast performance is weak,
- segmentation requires final verification,
- saved models may be sensitive to scikit-learn version changes,
- no longitudinal user study has been completed,
- no clinical validation has been performed.

---

## 17. Final Verification Checklist

Before release, complete the following:

### Risk classifier

- Confirm the saved pipeline loads.
- Submit a low-risk example.
- Submit a high-risk example.
- Confirm binary labels are correct.
- Confirm invalid input is rejected.
- Add endpoint tests.

### Segmentation

- Retrain the complete pipeline.
- Save cluster names with the model.
- Restart the backend.
- Submit a questionnaire.
- Confirm cluster and name are returned.
- Test all expected input fields.
- Add endpoint tests.

### Anomaly detector

- Test normal usage.
- Test obvious spike usage.
- Confirm estimated features are disclosed.
- Confirm model failure does not break the dashboard summary.

### Forecaster

- Confirm lag feature order.
- Test sufficient-history mode.
- Test fallback mode.
- Display low confidence honestly.
- Compare against a naive baseline.

---

## 18. Summary

HabitGuard uses ML as an optional analytics layer:

```text
Risk classifier
→ broad questionnaire-based risk

Segmentation
→ behavioural grouping

Anomaly detector
→ unusual usage detection

Forecaster
→ exploratory future-usage estimate
```

The live behavioural intervention system remains independent:

```text
StructuralTimerEngine
→ DecisionEngine
→ context
→ feedback
→ delivery policy
```

This design keeps the core system explainable and usable even when an ML model is unavailable or unreliable.
