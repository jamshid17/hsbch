/** Maximum quantity a user can set for an item. */
export const MAX_QTY = 10;

/** Format a quantity, stripping trailing zeros: "10.000" → "10", "1.500" → "1.5". */
export function fmtQty(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "0";
  return String(Number(n.toFixed(3)));
}

/**
 * How many units of an item can be claimed in total, or null for no limit.
 *
 * An item with a count is a count: eight skewers are eight, and a ninth
 * being claimed makes the split describe a meal that didn't happen. One unit
 * or less is a dish rather than a count, and dishes get shared — two people
 * ticking one lagmon is what the proportional split is for — so those stay
 * uncapped.
 */
export function claimCapacity(quantity: string | number): number | null {
  const n = typeof quantity === "string" ? parseFloat(quantity) : quantity;
  if (!isFinite(n) || n <= 1) return null;
  return Math.floor(n);
}

/** Clamp a quantity to the 0..MAX_QTY range (empty string passes through). */
export function clampQty(value: string): string {
  if (value === "") return value;
  const n = Number(value);
  if (!isFinite(n)) return value;
  if (n > MAX_QTY) return String(MAX_QTY);
  return value;
}

/* The admin API sends timestamps as naive UTC ISO strings (no offset), so
 * these helpers append "Z" before parsing — otherwise a browser in UTC+5
 * reads 09:00 UTC as 09:00 local and every "bugun" is five hours off. */
function parse(iso: string): Date {
  return new Date(/[Z+]|-\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
}

/** Thousands-separated integer: 25000 → "25 000". */
export function fmtNum(n: number): string {
  return n.toLocaleString("ru-RU");
}

/** dd.mm.yyyy — the app has three UI languages, so month names are avoided. */
export function fmtDate(iso: string): string {
  const d = parse(iso);
  return [d.getDate(), d.getMonth() + 1, d.getFullYear()]
    .map((v, i) => (i < 2 ? String(v).padStart(2, "0") : v))
    .join(".");
}

/** dd.mm.yyyy hh:mm, in the viewer's own timezone. */
export function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = parse(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${fmtDate(iso)} ${hh}:${mm}`;
}

/** "bugun" / "3 kun oldin" / a plain date once it stops being recent. */
export function relDate(iso: string | null): string {
  if (!iso) return "—";
  const days = Math.floor((Date.now() - parse(iso).getTime()) / 86400000);
  if (days === 0) return "bugun";
  if (days === 1) return "kecha";
  if (days < 30) return `${days} kun oldin`;
  return fmtDate(iso);
}
