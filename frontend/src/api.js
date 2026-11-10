const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Quiet request on page load so a sleeping free server starts waking up early.
export const ping = () => fetch(`${BASE}/api/health`).catch(() => {});

export async function analyze(url) {
  let res;
  try {
    res = await fetch(`${BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    throw new Error("Cannot reach the server. If it was asleep, wait 30 seconds and try again.");
  }
  if (!res.ok) {
    let msg = "Something went wrong. Please try again.";
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : "Please check the link and try again.";
    } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export async function watch(productId, email, targetPrice) {
  let res;
  try {
    res = await fetch(`${BASE}/api/watch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, email, target_price: targetPrice }),
    });
  } catch {
    throw new Error("Cannot reach the server. Please try again in a moment.");
  }
  const j = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = j.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d[0]?.msg?.replace("Value error, ", "") || "Please check your details." : "Something went wrong.");
  }
  return j.message;
}
