import { formatMinutes } from "../utils/formatters";

export default function UsageTrend({ data }) {
  const maxMinutes = Math.max(...data.map((item) => item.minutes), 1);

  return (
    <section className="card wide-card">
      <div className="card-header">
        <div>
          <p className="card-label">7-day trend</p>
          <h2>Usage pattern</h2>
        </div>
      </div>

      {data.length === 0 ? (
        <p className="empty-text">No 7-day trend data available yet.</p>
      ) : (
        <div className="trend-chart">
          {data.map((item) => {
            const height = Math.max((item.minutes / maxMinutes) * 100, 6);

            return (
              <div className="trend-item" key={item.date}>
                <div className="bar-track">
                  <div className="bar-fill" style={{ height: `${height}%` }} />
                </div>
                <p className="trend-value">{formatMinutes(item.minutes)}</p>
                <p className="trend-label">{item.date}</p>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}