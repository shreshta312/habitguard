const API_URL = "http://127.0.0.1:8000/habitguard/custom/intervention";

const usageStatusEl = document.getElementById("usageStatus");
const frictionTypeEl = document.getElementById("frictionType");
const timerEl = document.getElementById("timer");
const usageDetailsEl = document.getElementById("usageDetails");
const messageEl = document.getElementById("message");

const stableBtn = document.getElementById("stableBtn");
const highBtn = document.getElementById("highBtn");
const riskyBtn = document.getElementById("riskyBtn");
const calibrationBtn = document.getElementById("calibrationBtn");

const usageSamples = {
  stable: [
    30, 32, 31, 29, 33,
    30, 31, 32, 30, 31,
    30, 32, 31
  ],

  high: [
    20, 22, 24, 21, 23,
    25, 20, 22, 24, 21,
    45, 50, 52
  ],

  risky: [
    20, 22, 24, 21, 23,
    25, 20, 22, 24, 21,
    80, 90, 100
  ],

  calibration: [
    20, 22, 24, 21, 23
  ]
};

function setLoading(label) {
  usageStatusEl.textContent = "Loading...";
  frictionTypeEl.textContent = "Loading...";
  timerEl.textContent = "Loading...";
  usageDetailsEl.textContent = `Testing ${label} pattern...`;
  messageEl.textContent = "Sending usage history to HabitGuard backend...";
}

function renderResult(data) {
  if (data.error) {
    usageStatusEl.textContent = "ERROR";
    frictionTypeEl.textContent = "-";
    timerEl.textContent = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent = data.error;
    return;
  }

  usageStatusEl.textContent = data.usage_status || data.mode || "UNKNOWN";
  frictionTypeEl.textContent = data.friction_type || "NONE";

  if (
    data.recommended_timer_minutes === null ||
    data.recommended_timer_minutes === undefined
  ) {
    timerEl.textContent = "Not active";
  } else {
    timerEl.textContent = `${data.recommended_timer_minutes} min`;
  }

  const baseline = data.baseline_usage_minutes;
  const recent = data.recent_usage_minutes;
  const overuse = data.overuse_gap_minutes;

  if (
    baseline === undefined ||
    recent === undefined ||
    overuse === undefined
  ) {
    usageDetailsEl.textContent = "Baseline still being collected.";
  } else {
    usageDetailsEl.textContent =
      `Baseline: ${baseline} min | Recent: ${recent} min | Overuse: ${overuse} min`;
  }

  messageEl.textContent = data.message || "No message returned.";
}

async function sendUsageHistory(label, usageHistory) {
  setLoading(label);

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        usage_history_minutes: usageHistory
      })
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    renderResult(data);
  } catch (error) {
    usageStatusEl.textContent = "OFFLINE";
    frictionTypeEl.textContent = "-";
    timerEl.textContent = "-";
    usageDetailsEl.textContent = "-";
    messageEl.textContent =
      "Could not connect to HabitGuard backend. Make sure FastAPI is running.";

    console.error(error);
  }
}

stableBtn.addEventListener("click", () => {
  sendUsageHistory("Stable", usageSamples.stable);
});

highBtn.addEventListener("click", () => {
  sendUsageHistory("High Usage", usageSamples.high);
});

riskyBtn.addEventListener("click", () => {
  sendUsageHistory("Risky Spike", usageSamples.risky);
});

calibrationBtn.addEventListener("click", () => {
  sendUsageHistory("Calibration", usageSamples.calibration);
});

sendUsageHistory("High Usage", usageSamples.high);