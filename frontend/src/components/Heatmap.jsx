export default function Heatmap({ data }) {
  if (!data?.values?.length) return <p className="text-muted small">No heatmap data</p>;

  const maxVal = Math.max(...data.values.flat(), 0.001);

  const color = (v) => {
    const t = v / maxVal;
    const r = Math.round(13 + t * 200);
    const g = Math.round(71 + t * 80);
    const b = Math.round(161 - t * 60);
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div className="heatmap-grid">
      <div></div>
      {data.hours.map((h) => (
        <div key={h} className="text-center text-muted">
          {h % 4 === 0 ? `${h}` : ""}
        </div>
      ))}
      {data.days.map((day, di) => (
        <div key={day} style={{ display: "contents" }}>
          <div className="text-muted">{day}</div>
          {data.values[di].map((v, hi) => (
            <div
              key={`${di}-${hi}`}
              className="heatmap-cell"
              style={{ background: color(v) }}
              title={`${day} ${data.hours[hi]}:00 — ${v} kW`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
