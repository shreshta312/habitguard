import { formatDateTime, formatKey, formatMinutes } from "../utils/formatters";

function isDateLikeKey(key) {
  const lowerKey = key.toLowerCase();

  return (
    lowerKey.endsWith("_at") ||
    lowerKey.endsWith("at") ||
    lowerKey.includes("timestamp") ||
    lowerKey.includes("received_at") ||
    lowerKey.includes("updated_at") ||
    lowerKey.includes("started_at") ||
    lowerKey.includes("created_at")
  );
}

function isMinuteLikeKey(key) {
  const lowerKey = key.toLowerCase();

  return (
    lowerKey.includes("minutes") ||
    lowerKey.includes("duration") ||
    lowerKey.includes("elapsed")
  );
}

function renderObject(value) {
  const entries = Object.entries(value || {});

  if (entries.length === 0) {
    return "No data";
  }

  return (
    <div className="nested-list">
      {entries.map(([nestedKey, nestedValue]) => (
        <div className="nested-row" key={nestedKey}>
          <span>{formatKey(nestedKey)}</span>
          <strong>{String(nestedValue)}</strong>
        </div>
      ))}
    </div>
  );
}

function formatValue(key, value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "object") {
    return renderObject(value);
  }

  if (isMinuteLikeKey(key)) {
    return formatMinutes(value);
  }

  if (isDateLikeKey(key)) {
    return formatDateTime(value);
  }

  return String(value);
}

export default function KeyValueCard({ title, heading, data }) {
  const entries = Object.entries(data || {});

  return (
    <section className="card">
      <p className="card-label">{title}</p>
      <h2>{heading}</h2>

      {entries.length === 0 ? (
        <p className="empty-text">No data available yet.</p>
      ) : (
        <div className="kv-list">
          {entries.map(([key, value]) => (
            <div className="kv-row" key={key}>
              <span>{formatKey(key)}</span>
              <strong>{formatValue(key, value)}</strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}