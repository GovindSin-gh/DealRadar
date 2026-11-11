import { useEffect, useState } from "react";
import { analyze, ping } from "./api";
import Result from "./components/Result";

const EXAMPLES = [
  ["Amazon.in phone", "https://www.amazon.in/Nova-X-Pro/dp/B0EXAMPLE1"],
  ["Flipkart laptop", "https://www.flipkart.com/vertex-book-14/p/itmEXAMPLE2"],
];
const STEPS = ["Fetching the product page", "Reading price history", "Reading reviews", "Writing the verdict", "Almost done"];

export default function App() {
  const [url, setUrl] = useState("");
  const [state, setState] = useState("idle");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [secs, setSecs] = useState(0);
  const [pending, setPending] = useState("");

  useEffect(() => { ping(); }, []);
  useEffect(() => {
    if (state !== "loading") return;
    setSecs(0);
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [state]);

  async function submit(e) {
    e.preventDefault();
    if (state === "loading") return;
    setState("loading"); setError(""); setPending("");
    try {
      const deadline = Date.now() + 4 * 60 * 1000;
      let r = await analyze(url);
      while (r.pending) {  // the page is being fetched by a background worker: ask again until it is ready
        if (Date.now() > deadline) throw new Error("This is taking longer than expected. Please try again in a few minutes.");
        setPending(r.message);
        await new Promise((ok) => setTimeout(ok, r.retryAfter * 1000));
        r = await analyze(url);
      }
      setData(r); setState("done");
    }
    catch (x) { setError(x.message); setState("error"); }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-5 py-4 flex items-center gap-3">
          <svg width="30" height="30" viewBox="0 0 34 34" aria-hidden="true"><circle cx="17" cy="17" r="15" fill="none" stroke="#6366f1" strokeWidth="2"/><circle cx="17" cy="17" r="8" fill="none" stroke="#6366f1" strokeOpacity=".5" strokeWidth="2"/><path d="M17 17 L28 9" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round"/><circle cx="17" cy="17" r="2.5" fill="#34d399"/></svg>
          <span className="text-lg font-bold text-slate-50">DealRadar</span>
        </div>
      </header>

      <main className="max-w-6xl w-full mx-auto px-5 py-10 flex-1">
        <h1 className="text-3xl md:text-4xl font-bold text-slate-50 max-w-2xl">Should you buy it now? Paste a link and find out.</h1>
        <p className="mt-2 text-slate-400 max-w-xl">Price history, what owners complain about, and a plain verdict for smartphones and laptops on Amazon.in and Flipkart.</p>

        <form onSubmit={submit} className="mt-6 flex flex-col sm:flex-row gap-3">
          <input value={url} onChange={(e) => setUrl(e.target.value)} required type="url" aria-label="Product link"
            placeholder="https://www.amazon.in/..."
            className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-50 placeholder-slate-600" />
          <button disabled={state === "loading"}
            className="bg-indigo-500 hover:bg-indigo-400 disabled:opacity-60 text-white font-medium rounded-xl px-6 py-3 text-sm transition">
            {state === "loading" ? "Analyzing..." : "Analyze product"}
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500 items-center">
          Try an example:
          {EXAMPLES.map(([label, link]) => (
            <button key={label} type="button" onClick={() => setUrl(link)}
              className="rounded-full px-3 py-1 border border-slate-700 hover:border-indigo-500/60 text-slate-300 transition">{label}</button>
          ))}
        </div>

        <div className="mt-8" aria-live="polite">
          {state === "loading" && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
              <div className="h-1.5 bg-slate-800 rounded-full mb-4 overflow-hidden">
                <div className="h-1.5 bg-indigo-500 rounded-full transition-all duration-1000" style={{ width: `${Math.min(95, 10 + secs * 8)}%` }} />
              </div>
              <p className="font-mono text-sm text-indigo-400">{pending || `${STEPS[Math.min(Math.floor(secs / 2), STEPS.length - 1)]}...`}</p>
              {!pending && secs >= 5 && <p className="mt-3 text-sm text-amber-400">Waking up backend server, please wait 30s... (the free server sleeps when idle)</p>}
            </div>
          )}
          {state === "error" && (
            <div className="bg-red-400/10 border border-red-400/30 text-red-400 rounded-2xl p-5 text-sm">{error}</div>
          )}
          {state === "done" && data && <Result data={data} />}
        </div>
      </main>

      <footer className="border-t border-slate-800 text-center text-xs text-slate-500 py-6 px-4">
        Prices and availability fluctuate; data scraped dynamically for educational/demonstration purposes. Not affiliated with Amazon or Flipkart.
      </footer>
    </div>
  );
}
