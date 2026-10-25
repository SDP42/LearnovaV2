/** "3 minutes ago" style relative time from an ISO string / epoch (s or ms). */
export function relativeTime(value) {
  if (!value) return "";
  let t = typeof value === "number" ? (value < 1e12 ? value * 1000 : value) : Date.parse(value);
  if (!Number.isFinite(t)) return "";
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 45) return "just now";
  const units = [
    [60, "minute"],
    [3600, "hour"],
    [86400, "day"],
    [604800, "week"],
    [2592000, "month"],
    [31536000, "year"],
  ];
  let best = ["second", 1];
  let div = 1;
  for (const [sec, name] of units) {
    if (s >= sec) {
      best = name;
      div = sec;
    }
  }
  const n = Math.max(1, Math.floor(s / div));
  return `${n} ${best}${n === 1 ? "" : "s"} ago`;
}

export function greeting(date = new Date()) {
  const h = date.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export const deckUpdated = (d) =>
  d?.updated_at ?? d?.modified_at ?? d?.edited_at ?? d?.created_at ?? d?.created ?? null;
export const deckSlides = (d) => d?.slide_count ?? d?.slides ?? 0;
