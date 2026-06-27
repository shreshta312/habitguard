const API_URL = "http://127.0.0.1:8000/habitguard/user/1000/intervention";

const usageStatusEl = document.getElementById("usageStatus");
const frictionTypeEl = document.getElementById("frictionType");
const timerEl = document.getElementById("timer");
const messageEl = document.getElementById("message");
const refreshBtn = document.getElementById("refreshBtn");

async function fetchIntervention() {
  usageStatusEl.textContent = "Loading...";
  frictionTypeEl.textContent = "Loading...";
  timerEl.textContent = "Loading...";
  messageEl.textContent = "Checking your usage pattern...";

  try {
    const response = await fetch(API_URL);

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();

    if (data.error) {
      usageStatusEl.textContent = "ERROR";
      frictionTypeEl.textContent = "NONE";
      timerEl.textContent = "-";
      messageEl.textContent = data.error;
      return;
    }

    usageStatusEl.textContent = data.usage_status || "UNKNOWN";
    frictionTypeEl.textContent = data.friction_type || "NONE";

    if (
      data.recommended_timer_minutes === null ||
      data.recommended_timer_minutes === undefined
    ) {
      timerEl.textContent = "Not active";
    } else {
      timerEl.textContent = `${data.recommended_timer_minutes} min`;
    }

    messageEl.textContent = data.message || "No message available.";
  } catch (error) {
    usageStatusEl.textContent = "OFFLINE";
    frictionTypeEl.textContent = "-";
    timerEl.textContent = "-";
    messageEl.textContent =
      "Could not connect to HabitGuard backend. Make sure FastAPI is running.";

    console.error(error);
  }
}

refreshBtn.addEventListener("click", fetchIntervention);

fetchIntervention();