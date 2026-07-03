import { useEffect, useState } from "react";
import { fetchUsageSummary } from "./api/usageApi";
import MetricCard from "./components/MetricCard";
import UsageTrend from "./components/UsageTrend";
import DomainTable from "./components/DomainTable";
import KeyValueCard from "./components/KeyValueCard";
import { formatMinutes } from "./utils/formatters";

export default function App() {
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  async function loadDashboard() {
    try {
      setStatus("loading");
      setError("");

      const data = await fetchUsageSummary();

      setSummary(data);
      setStatus("ready");
    } catch (err) {
      setError(err.message || "Unable to load dashboard data.");
      setStatus("error");
    }
  }

  useEffect(() => {
    let ignore = false;

    async function load() {
      try {
        setStatus("loading");
        const data = await fetchUsageSummary();

        if (!ignore) {
          setSummary(data);
          setStatus("ready");
        }
      } catch (err) {
        if (!ignore) {
          setError(err.message || "Unable to load dashboard data.");
          setStatus("error");
        }
      }
    }

    load();

    return () => {
      ignore = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">HabitGuard Dashboard</p>
          <h1>Usage, sessions, and interventions</h1>
          <p className="hero-text">
            Local dashboard connected to your FastAPI summary endpoint.
          </p>
        </div>

        <button onClick={loadDashboard}>Refresh</button>
      </header>

      {status === "loading" && (
        <section className="status-card">Loading HabitGuard data...</section>
      )}

      {status === "error" && (
        <section className="status-card error-card">
          <h2>Dashboard could not connect</h2>
          <p>{error}</p>
          <p className="muted">
            Make sure FastAPI is running on port 8000.
          </p>
        </section>
      )}

      {status === "ready" && summary && (
        <>
          <section className="grid metrics-grid">
            <MetricCard
              title="Today total usage"
              value={formatMinutes(summary.todayTotalMinutes)}
              subtitle="Total tracked usage today"
            />

            <MetricCard
              title="Domains today"
              value={summary.topDomainsToday.length}
              subtitle="Unique domains tracked today"
            />

            <MetricCard
              title="All-time domains"
              value={summary.topDomainsAllTime.length}
              subtitle="Domains seen in stored snapshots"
            />
          </section>

          <UsageTrend data={summary.sevenDayTrend} />

          <section className="grid two-column-grid">
            <DomainTable
              title="Today"
              domains={summary.topDomainsToday}
            />

            <DomainTable
              title="All time"
              domains={summary.topDomainsAllTime}
            />
          </section>

          <section className="grid two-column-grid">
            <KeyValueCard
              title="Live state"
              heading="Current session"
              data={summary.currentSession}
            />

            <KeyValueCard
              title="Intervention"
              heading="Latest intervention"
              data={summary.latestIntervention}
            />
          </section>

          <section className="grid three-column-grid">
            <KeyValueCard
              title="Sessions"
              heading="Session stats"
              data={summary.sessionStats}
            />

            <KeyValueCard
              title="Interventions"
              heading="Intervention stats"
              data={summary.interventionStats}
            />

            <KeyValueCard
              title="Extension"
              heading="Event stats"
              data={summary.extensionEventStats}
            />
          </section>
        </>
      )}
    </main>
  );
}