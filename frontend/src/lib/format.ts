/** Maximum quantity a user can set for an item. */
export const MAX_QTY = 10;

/** Format a quantity, stripping trailing zeros: "10.000" → "10", "1.500" → "1.5". */
export function fmtQty(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "0";
  return String(Number(n.toFixed(3)));
}

/** Clamp a quantity to the 0..MAX_QTY range (empty string passes through). */
export function clampQty(value: string): string {
  if (value === "") return value;
  const n = Number(value);
  if (!isFinite(n)) return value;
  if (n > MAX_QTY) return String(MAX_QTY);
  return value;
}
