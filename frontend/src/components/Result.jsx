import Aspects from "./Aspects";
import Watch from "./Watch";
import PriceChart, { inr } from "./PriceChart";

const Card = ({ className = "", children }) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-2xl p-6 ${className}`}>{children}</div>
);

function Ring({ score }) {
  const color = score >= 7 ? "#34d399" : score >= 5 ? "#fbbf24" : "#f87171";
  return (
    <svg viewBox="0 0 120 120" className="w-36 h-36" role="img" aria-label={`Value score ${score} out of 10`}>
      <circle cx="60" cy="60" r="50" fill="none" stroke="#1e293b" strokeWidth="10" />
      <circle cx="60" cy="60" r="50" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
        strokeDasharray="314" strokeDashoffset={314 * (1 - score / 10)} transform="rotate(-90 60 60)" />
      <text x="60" y="68" textAnchor="middle" fill={color} fontSize="28" fontWeight="700">{score.toFixed(1)}</text>
    </svg>
  );
}

const List = ({ title, items, tone, mark }) => (
  <Card>
    <h3 className={`font-semibold mb-3 ${tone}`}>{title}</h3>
    <ul className="space-y-2 text-sm">{items.map((t) => <li key={t} className="flex gap-2"><span className={tone}>{mark}</span>{t}</li>)}</ul>
  </Card>
);

export default function Result({ data }) {
  const { analysis: a, price_stats: s } = data;
  const below = s.percent_vs_average <= 0;
  const shop = data.shop === "amazon" ? "Amazon.in" : "Flipkart";
  return (
    <div className="grid md:grid-cols-12 gap-4">
      <Card className="md:col-span-8">
        <div className="flex flex-wrap justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-50">{data.title}</h2>
            <p className="text-xs text-slate-500 capitalize">{data.category} · {shop} · {data.review_count} reviews read</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-slate-50">{inr(data.current_price)}</div>
            <div className={`text-xs ${below ? "text-emerald-400" : "text-red-400"}`}>
              {below ? "▼" : "▲"} {Math.abs(s.percent_vs_average)}% vs 90-day average
            </div>
          </div>
        </div>
        <div className="mt-3"><PriceChart history={data.price_history} /></div>
        <p className="text-xs text-slate-500 mt-2">Lowest {inr(s.lowest)} · Highest {inr(s.highest)}</p>
      </Card>

      <Card className="md:col-span-4 flex flex-col items-center justify-center text-center">
        <p className="text-xs text-slate-500 mb-1">Value score</p>
        <Ring score={a.value_score} />
        <p className="text-xs text-slate-400 mt-1">Out of 10</p>
      </Card>

      <Card className="md:col-span-12">
        <div className="flex flex-wrap justify-between gap-2 mb-2">
          <h3 className="text-slate-50 font-semibold">Verdict</h3>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-mono ring-1 ${a.source === "qwen" ? "bg-indigo-500/10 text-indigo-300 ring-indigo-500/30" : "bg-amber-400/10 text-amber-400 ring-amber-400/30"}`}>
            {a.source === "qwen" ? "written by Qwen AI" : "automatic summary"}
          </span>
        </div>
        <p className="text-slate-50 font-medium">{a.verdict}</p>
        <p className="text-sm mt-2">{a.summary}</p>
      </Card>

      {a.aspects?.length > 0 && <Aspects aspects={a.aspects} version={a.model_version} />}

      <div className="md:col-span-6"><List title="Pros" items={a.pros} tone="text-emerald-400" mark="✓" /></div>
      <div className="md:col-span-6"><List title="Cons" items={a.cons} tone="text-red-400" mark="✗" /></div>

      <Watch productId={data.id} currentPrice={data.current_price} />

      <p className="md:col-span-12 text-xs text-slate-500">
        {data.cached ? "Showing a saved analysis from the last 24 hours." : "Fresh analysis."} Analyzed {new Date(data.analyzed_at + "Z").toLocaleString("en-IN")}.
      </p>
    </div>
  );
}
