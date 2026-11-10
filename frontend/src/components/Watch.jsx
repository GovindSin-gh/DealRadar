import { useState } from "react";
import { watch } from "../api";
import { inr } from "./PriceChart";

// Price-drop email alert. The backend emails once when the price reaches the target, with an unsubscribe link.
export default function Watch({ productId, currentPrice }) {
  const [email, setEmail] = useState("");
  const [target, setTarget] = useState(Math.round((currentPrice * 0.95) / 10) * 10);
  const [state, setState] = useState({ kind: "idle", text: "" });

  async function submit(e) {
    e.preventDefault();
    setState({ kind: "busy", text: "" });
    try { setState({ kind: "ok", text: await watch(productId, email, Number(target)) }); }
    catch (x) { setState({ kind: "err", text: x.message }); }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 md:col-span-12">
      <h3 className="text-slate-50 font-semibold">Get a price-drop email</h3>
      <p className="text-xs text-slate-500 mb-3">Optional, no account. Now {inr(currentPrice)}. We email once when it reaches your target, and every email has an unsubscribe link.</p>
      <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3 text-sm">
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" aria-label="Email address"
          className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-slate-50 placeholder-slate-600" />
        <input type="number" required min="1" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Target price in rupees"
          className="w-full sm:w-36 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-slate-50" />
        <button disabled={state.kind === "busy"} className="bg-slate-800 hover:bg-slate-700 disabled:opacity-60 text-slate-100 rounded-xl px-5 py-2 transition">
          {state.kind === "busy" ? "Saving..." : "Watch price"}
        </button>
      </form>
      {state.text && <p className={`text-xs mt-2 ${state.kind === "ok" ? "text-emerald-400" : "text-red-400"}`} role="status">{state.text}</p>}
    </div>
  );
}
