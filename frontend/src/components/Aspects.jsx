import { useState } from "react";

const label = (a) => "#" + a;
const tone = (a) =>
  a.negative_pct >= 50 ? "bg-red-400/10 text-red-400 ring-red-400/30"
  : a.positive_pct >= 70 ? "bg-emerald-400/10 text-emerald-400 ring-emerald-400/30"
  : "bg-amber-400/10 text-amber-400 ring-amber-400/30";

export default function Aspects({ aspects, version }) {
  const [sel, setSel] = useState(aspects[0]?.aspect);
  const cur = aspects.find((a) => a.aspect === sel) || aspects[0];
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 md:col-span-12">
      <div className="flex flex-wrap justify-between gap-2">
        <h3 className="text-slate-50 font-semibold">What reviewers say about each part</h3>
        <span className="rounded-full px-2.5 py-0.5 text-xs font-mono ring-1 bg-emerald-400/10 text-emerald-400 ring-emerald-400/30">classifier {version}</span>
      </div>
      <p className="text-xs text-slate-500 mb-4">Share of positive and negative mentions. Click a tag to read example reviews.</p>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-3">
          {aspects.map((a) => (
            <div key={a.aspect}>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-mono">{label(a.aspect)}</span>
                <span className="font-mono text-slate-400">{a.positive_pct}% positive · {a.negative_pct}% negative · {a.mentions} mentions</span>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden flex bg-slate-800" role="img" aria-label={`${a.aspect}: ${a.positive_pct}% positive`}>
                <div className="bg-emerald-400" style={{ width: `${a.positive_pct}%` }} />
                <div className="bg-red-400" style={{ width: `${a.negative_pct}%` }} />
              </div>
            </div>
          ))}
        </div>
        <div>
          <div className="flex flex-wrap gap-2 mb-3">
            {aspects.map((a) => (
              <button key={a.aspect} onClick={() => setSel(a.aspect)}
                className={`rounded-full px-2.5 py-0.5 text-xs font-mono ring-1 transition hover:brightness-125 ${tone(a)} ${cur.aspect === a.aspect ? "outline outline-2 outline-offset-2 outline-slate-500" : ""}`}>
                {label(a.aspect)}
              </button>
            ))}
          </div>
          <div className="space-y-2 text-sm">
            {cur.snippets.map((t) => <blockquote key={t} className="border-l-2 border-slate-700 pl-3 text-slate-300">“{t}”</blockquote>)}
          </div>
        </div>
      </div>
    </div>
  );
}
