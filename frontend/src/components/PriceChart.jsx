import { useState } from "react";

export const inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
const day = (s) => new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export default function PriceChart({ history }) {
  const [days, setDays] = useState(90);
  const [hover, setHover] = useState(null);
  if (history.length < 2)
    return <p className="text-sm text-slate-400 mt-3">Tracking started today. The price chart appears after a few daily updates.</p>;
  const d = history.slice(-days);
  const prices = d.map((p) => p.price);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const avg = prices.reduce((a, b) => a + b, 0) / prices.length;
  const W = 600, H = 190, pad = (hi - lo) * 0.15 || 100;
  const X = (i) => (i / (d.length - 1)) * W;
  const Y = (v) => H - 12 - ((v - (lo - pad)) / (hi + pad - (lo - pad))) * (H - 24);
  const line = d.map((p, i) => `${X(i).toFixed(1)},${Y(p.price).toFixed(1)}`).join(" ");
  const low = prices.indexOf(lo);

  const move = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
    setHover(Math.max(0, Math.min(d.length - 1, Math.round((x / r.width) * (d.length - 1)))));
  };

  return (
    <div>
      <div className="flex gap-2 text-xs mb-2">
        {[30, 60, 90].map((n) => (
          <button key={n} onClick={() => setDays(n)}
            className={`px-3 py-1 rounded-lg border transition ${days === n ? "bg-indigo-500 border-indigo-500 text-white" : "border-slate-700 hover:border-indigo-500/60"}`}>
            {n} days
          </button>
        ))}
      </div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full touch-none" role="img" aria-label="Price history chart"
          onMouseMove={move} onTouchMove={move} onMouseLeave={() => setHover(null)}>
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="#6366f1" stopOpacity=".35" /><stop offset="1" stopColor="#6366f1" stopOpacity="0" />
            </linearGradient>
          </defs>
          <line x1="0" x2={W} y1={Y(avg)} y2={Y(avg)} stroke="#fbbf24" strokeDasharray="4 4" strokeOpacity=".6" />
          <text x="4" y={Y(avg) - 4} fill="#fbbf24" fontSize="10">average {inr(avg)}</text>
          <polygon points={`0,${H} ${line} ${W},${H}`} fill="url(#fill)" />
          <polyline points={line} fill="none" stroke="#6366f1" strokeWidth="2.5" strokeLinejoin="round" />
          <circle cx={X(low)} cy={Y(lo)} r="4.5" fill="#34d399" />
          <text x={Math.min(X(low), W - 70)} y={Y(lo) + 16} fill="#34d399" fontSize="10">period low</text>
          {hover !== null && (<>
            <line x1={X(hover)} x2={X(hover)} y1="0" y2={H} stroke="#94a3b8" strokeOpacity=".5" />
            <circle cx={X(hover)} cy={Y(d[hover].price)} r="4" fill="#f8fafc" />
          </>)}
        </svg>
        {hover !== null && (
          <div className="absolute top-0 pointer-events-none bg-slate-800 border border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-100 font-mono"
            style={{ left: `${Math.min(80, Math.max(0, (X(hover) / W) * 100 - 8))}%` }}>
            {day(d[hover].date)} · {inr(d[hover].price)}
          </div>
        )}
      </div>
    </div>
  );
}
