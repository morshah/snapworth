import React from 'react';

// Dependency-free SVG box plot: whiskers (min–max), box (Q1–Q3), median line,
// and a dot per site price.
export default function PriceChart({ stats }) {
  const vals = stats.price_values || [];
  if (vals.length === 0) return null;

  const min = stats.price_min ?? Math.min(...vals);
  const max = stats.price_max ?? Math.max(...vals);
  const { price_q1: q1, price_q3: q3, price_median: med, currency } = stats;

  const W = 600, H = 120, padX = 44, cy = 52;
  const span = max - min || 1;
  const x = (v) => padX + ((v - min) / span) * (W - 2 * padX);
  const cur = currency ? `${currency} ` : '';
  const fmt = (v) => (v == null ? '' : `${cur}${v}`);

  return (
    <svg className="price-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      <line x1={x(min)} y1={cy} x2={x(max)} y2={cy} className="pc-whisker" />
      <line x1={x(min)} y1={cy - 12} x2={x(min)} y2={cy + 12} className="pc-cap" />
      <line x1={x(max)} y1={cy - 12} x2={x(max)} y2={cy + 12} className="pc-cap" />
      {q1 != null && q3 != null && (
        <rect x={x(q1)} y={cy - 18} width={Math.max(1, x(q3) - x(q1))} height={36} className="pc-box" />
      )}
      {med != null && <line x1={x(med)} y1={cy - 18} x2={x(med)} y2={cy + 18} className="pc-median" />}
      {vals.map((v, i) => <circle key={i} cx={x(v)} cy={cy} r={4.5} className="pc-dot" />)}
      <text x={x(min)} y={cy + 34} className="pc-label" textAnchor="middle">{fmt(min)}</text>
      {med != null && <text x={x(med)} y={cy - 26} className="pc-label" textAnchor="middle">{fmt(med)}</text>}
      <text x={x(max)} y={cy + 34} className="pc-label" textAnchor="middle">{fmt(max)}</text>
    </svg>
  );
}
