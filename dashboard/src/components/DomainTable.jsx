import { formatMinutes } from "../utils/formatters";

export default function DomainTable({ title, domains }) {
  return (
    <section className="card">
      <p className="card-label">{title}</p>
      <h2>Top domains</h2>

      {domains.length === 0 ? (
        <p className="empty-text">No domain data available yet.</p>
      ) : (
        <div className="domain-list">
          {domains.slice(0, 8).map((item) => (
            <div className="domain-row" key={item.domain}>
              <div>
                <strong>{item.domain}</strong>
                {item.sessions > 0 && (
                  <p className="muted">{item.sessions} sessions</p>
                )}
              </div>

              <span>{formatMinutes(item.minutes)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}