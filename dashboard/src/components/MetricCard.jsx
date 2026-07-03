export default function MetricCard({ title, value, subtitle }) {
  return (
    <section className="card metric-card">
      <p className="card-label">{title}</p>
      <h2>{value}</h2>
      {subtitle && <p className="muted">{subtitle}</p>}
    </section>
  );
}