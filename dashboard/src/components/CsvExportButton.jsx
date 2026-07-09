/**
 * CsvExportButton.jsx
 *
 * A button that exports the current dashboard data to a downloadable CSV file.
 * Exports: date, daily total minutes, top domain, screen time, overuse gap, interventions.
 */
import { Download } from "lucide-react";

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function escapeCSV(value) {
  const str = String(value ?? "");
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export default function CsvExportButton({ weeklyTrend, domainBreakdown, liveUsage, latestIntervention, accents }) {
  function handleExport() {
    const rows = [];

    // Header
    rows.push([
      "Day",
      "Screen Time (min)",
      "Status",
    ].join(","));

    // Weekly trend rows
    if (weeklyTrend && weeklyTrend.length > 0) {
      weeklyTrend.forEach((day) => {
        rows.push([
          escapeCSV(day.day),
          toNumber(day.minutes),
          day.minutes > 300 ? "Heavy" : day.minutes > 180 ? "Moderate" : "Light",
        ].join(","));
      });
    }

    // Separator
    rows.push("");
    rows.push("--- Domain Breakdown ---");
    rows.push(["Domain", "Minutes"].join(","));

    if (domainBreakdown && domainBreakdown.length > 0) {
      domainBreakdown.forEach((d) => {
        rows.push([escapeCSV(d.app), toNumber(d.minutes)].join(","));
      });
    }

    // Summary section
    rows.push("");
    rows.push("--- Today Summary ---");
    rows.push(`Total Screen Time,${toNumber(liveUsage?.screenTimeMinutes)}`);
    rows.push(`Overuse Gap,${toNumber(liveUsage?.overuseGapMinutes)}`);
    rows.push(`Interventions Today,${toNumber(liveUsage?.interventionsToday)}`);
    rows.push(`Usage Status,${escapeCSV(latestIntervention?.usage_status || "N/A")}`);
    rows.push(`Friction Type,${escapeCSV(latestIntervention?.friction_type || "N/A")}`);

    const csvContent = rows.join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = `habitguard_export_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();

    URL.revokeObjectURL(url);
  }

  return (
    <button
      type="button"
      onClick={handleExport}
      className="hg-btn-secondary flex items-center gap-2"
      title="Export dashboard data as CSV"
    >
      <Download size={14} />
      Export CSV
    </button>
  );
}
