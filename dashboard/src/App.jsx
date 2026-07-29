import { useState, useEffect } from "react";
import HabitGuardAvatar from "./designs/HabitGuardAvatar.jsx";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function ResearchDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadResearch() {
      try {
        const [optRes, paramRes, outcomeRes] = await Promise.all([
          fetch(`${API_BASE_URL}/dashboard/research/local_user/optimization`),
          fetch(`${API_BASE_URL}/dashboard/research/local_user/parameters`),
          fetch(`${API_BASE_URL}/dashboard/research/local_user/outcomes`)
        ]);
        const opt = await optRes.json();
        const param = await paramRes.json();
        const outcome = await outcomeRes.json();
        setData({ opt, param, outcome });
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    loadResearch();
  }, []);

  if (loading) return <div style={{ padding: 32 }}>Loading Research Data...</div>;
  if (error) return <div style={{ padding: 32, color: "red" }}>Error loading research: {error}</div>;

  return (
    <div style={{ padding: 32, fontFamily: "sans-serif", background: "#f8f9fa", minHeight: "100vh" }}>
      <h1>HabitGuard Research Portal</h1>
      <p style={{ color: "#6c757d" }}>Separated research route exposing optimization derivations, parameters, and outcomes.</p>

      <section style={{ marginTop: 24, background: "#fff", padding: 20, borderRadius: 12, border: "1px solid #dee2e6" }}>
        <h2>Temptation Formula & Weights</h2>
        <pre style={{ background: "#f1f3f5", padding: 12, borderRadius: 8 }}>{JSON.stringify(data?.opt?.temptation_formula, null, 2)}</pre>
      </section>

      <section style={{ marginTop: 24, background: "#fff", padding: 20, borderRadius: 12, border: "1px solid #dee2e6" }}>
        <h2>Cross-Domain Context</h2>
        <pre style={{ background: "#f1f3f5", padding: 12, borderRadius: 8 }}>{JSON.stringify(data?.opt?.cross_domain_context, null, 2)}</pre>
      </section>

      <section style={{ marginTop: 24, background: "#fff", padding: 20, borderRadius: 12, border: "1px solid #dee2e6" }}>
        <h2>Recent Optimization Runs ({data?.opt?.optimization_runs?.length || 0})</h2>
        <pre style={{ background: "#f1f3f5", padding: 12, borderRadius: 8, maxHeight: 300, overflow: "auto" }}>{JSON.stringify(data?.opt?.optimization_runs, null, 2)}</pre>
      </section>
    </div>
  );
}

function DebugDashboard() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/dashboard/debug/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "error" }));
  }, []);

  return (
    <div>
      <div style={{ background: "#343a40", color: "#fff", padding: "12px 32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong>HabitGuard Debug Mode</strong>
        <span>Status: {health?.status || "Checking..."} | Version: {health?.version || "2.0.0"}</span>
      </div>
      <HabitGuardAvatar showDebug={true} />
    </div>
  );
}

export default function App() {
  const path = typeof window !== "undefined" ? window.location.pathname : "/";

  if (path === "/dashboard/research") {
    return <ResearchDashboard />;
  }
  if (path === "/dashboard/debug") {
    return <DebugDashboard />;
  }

  return <HabitGuardAvatar showDebug={false} />;
}
