import { useState } from "react";
import { addReviews } from "../api";

// The dependable way to get reviews: the visitor copies them from the shop page in their own browser and pastes them here.
export default function PasteReviews({ productId, open, onUpdate }) {
  const [text, setText] = useState("");
  const [state, setState] = useState({ kind: "idle", text: "" });

  async function submit(e) {
    e.preventDefault();
    setState({ kind: "busy", text: "" });
    try {
      const next = await addReviews(productId, text);
      setText("");
      setState({ kind: "ok", text: next.notice || "Reviews added." });
      onUpdate(next);
    } catch (x) {
      setState({ kind: "err", text: x.message });
    }
  }

  return (
    <details open={open} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 md:col-span-12">
      <summary className="cursor-pointer text-slate-50 font-semibold">
        Add reviews yourself {open && <span className="ml-2 text-xs font-normal text-amber-400">recommended: none could be read automatically</span>}
      </summary>
      <ol className="mt-3 text-xs text-slate-400 list-decimal pl-5 space-y-1">
        <li>Open the product on the shop's website and scroll to the customer reviews.</li>
        <li>Select the reviews with your mouse (include the lines like "5.0 out of 5 stars") and copy them.</li>
        <li>Paste below. Reviewer names are dropped and the verdict and bars update right away.</li>
      </ol>
      <form onSubmit={submit} className="mt-3">
        <textarea value={text} onChange={(e) => setText(e.target.value)} required minLength={40} maxLength={20000} rows={6}
          aria-label="Pasted reviews" placeholder={"5.0 out of 5 stars  Great battery\nBattery easily lasts two days...\n\n2.0 out of 5 stars  Gets hot\n..."}
          className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-50 placeholder-slate-600" />
        <button disabled={state.kind === "busy"} className="mt-2 bg-indigo-500 hover:bg-indigo-400 disabled:opacity-60 text-white text-sm rounded-xl px-5 py-2 transition">
          {state.kind === "busy" ? "Reading..." : "Add reviews"}
        </button>
      </form>
      {state.text && <p className={`text-xs mt-2 ${state.kind === "ok" ? "text-emerald-400" : "text-red-400"}`} role="status">{state.text}</p>}
    </details>
  );
}
