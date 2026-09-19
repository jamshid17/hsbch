/**
 * Draws the finished split as a shareable picture.
 *
 * Canvas rather than a DOM screenshot: the app is themed by Telegram, so a
 * screenshot would come out black-on-black for half the group and needs a
 * heavy html-to-image dependency. This paints a fixed light card that reads
 * the same in every chat, and stays a few KB of code.
 */
import type { SummaryOut } from "../api";

export interface ReceiptImageLabels {
  /** Row label for each person's slice of tax + tip. */
  taxTip: string;
  /** Label of the closing total bar. */
  grandTotal: string;
  /** Small line under the header, e.g. "Kim qancha to'laydi". */
  subtitle: string;
  /** Footer credit. */
  brand: string;
}

const SCALE = 2; // device pixels per unit below — a crisp image on phones
const W = 640;
const PAD = 28;
const CARD_PAD = 20;
const RADIUS = 18;

const HEADER_TOP = 30;
const TITLE_SIZE = 30;
const SUBTITLE_SIZE = 15;
const HEADER_H = HEADER_TOP + TITLE_SIZE + 10 + SUBTITLE_SIZE + 26;

const NAME_ROW_H = 50; // name + total line, divider sits just under it
const ROW_TOP = 70; // baseline of the first breakdown row
const ITEM_ROW_H = 28;
const CARD_BOTTOM = 18; // breathing room under the last row
const CARD_GAP = 14;
const TOTAL_BAR_H = 66;
const FOOTER_H = 46;

const C = {
  page: "#eef1f5",
  card: "#ffffff",
  border: "#e2e6ec",
  text: "#14181f",
  muted: "#7b8796",
  accent: "#2481cc",
  bar: "#14181f",
  barText: "#ffffff",
};

const FONT = `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`;
const font = (weight: number, size: number) => `${weight} ${size}px ${FONT}`;

/** Space-separated thousands, decimals only when there are any. */
function fmt(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(num)) return "0";
  return num.toLocaleString("ru-RU", {
    minimumFractionDigits: num % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Cut a label down to `max` units, ending in an ellipsis rather than running
 * under the amount on its right. */
function ellipsize(ctx: CanvasRenderingContext2D, text: string, max: number): string {
  if (ctx.measureText(text).width <= max) return text;
  let out = text;
  while (out.length > 1 && ctx.measureText(`${out}…`).width > max) {
    out = out.slice(0, -1);
  }
  return `${out.trim()}…`;
}

function rowCount(person: SummaryOut["people"][number]): number {
  return person.items.length + (parseFloat(person.extras) > 0 ? 1 : 0);
}

function cardHeight(person: SummaryOut["people"][number]): number {
  const rows = rowCount(person);
  if (rows === 0) return NAME_ROW_H + CARD_BOTTOM;
  return ROW_TOP + (rows - 1) * ITEM_ROW_H + CARD_BOTTOM;
}

export function renderSummaryCanvas(
  summary: SummaryOut,
  labels: ReceiptImageLabels
): HTMLCanvasElement {
  const cardHeights = summary.people.map(cardHeight);
  const height =
    HEADER_H +
    cardHeights.reduce((sum, h) => sum + h + CARD_GAP, 0) +
    TOTAL_BAR_H +
    FOOTER_H +
    PAD;

  const canvas = document.createElement("canvas");
  canvas.width = W * SCALE;
  canvas.height = Math.ceil(height) * SCALE;
  const ctx = canvas.getContext("2d")!;
  ctx.scale(SCALE, SCALE);
  ctx.textBaseline = "alphabetic";

  ctx.fillStyle = C.page;
  ctx.fillRect(0, 0, W, height);

  const left = PAD;
  const right = W - PAD;
  const innerLeft = left + CARD_PAD;
  const innerRight = right - CARD_PAD;

  // ── Header ──
  ctx.fillStyle = C.text;
  ctx.font = font(800, TITLE_SIZE);
  ctx.textAlign = "left";
  ctx.fillText(
    ellipsize(ctx, summary.title || labels.subtitle, right - left),
    left,
    HEADER_TOP + TITLE_SIZE
  );

  ctx.fillStyle = C.muted;
  ctx.font = font(500, SUBTITLE_SIZE);
  const date = new Date().toLocaleDateString("ru-RU");
  ctx.fillText(
    `${labels.subtitle} · ${date}`,
    left,
    HEADER_TOP + TITLE_SIZE + 10 + SUBTITLE_SIZE
  );

  // ── One card per person ──
  let y = HEADER_H;
  summary.people.forEach((person, i) => {
    const h = cardHeights[i];

    ctx.fillStyle = C.card;
    roundRect(ctx, left, y, right - left, h, RADIUS);
    ctx.fill();
    ctx.strokeStyle = C.border;
    ctx.lineWidth = 1;
    ctx.stroke();

    // Name (left) and what they owe (right), on one line.
    const nameBaseline = y + 30;
    ctx.textAlign = "right";
    ctx.font = font(800, 23);
    ctx.fillStyle = C.accent;
    const amount = `${fmt(person.total)} ${summary.currency}`.trim();
    ctx.fillText(amount, innerRight, nameBaseline);
    const amountW = ctx.measureText(amount).width;

    ctx.textAlign = "left";
    ctx.font = font(700, 17);
    ctx.fillStyle = C.text;
    ctx.fillText(
      ellipsize(ctx, person.name, innerRight - innerLeft - amountW - 16),
      innerLeft,
      nameBaseline
    );

    // Divider between the name and the breakdown.
    ctx.strokeStyle = C.border;
    ctx.beginPath();
    ctx.moveTo(innerLeft, y + NAME_ROW_H - 8);
    ctx.lineTo(innerRight, y + NAME_ROW_H - 8);
    ctx.stroke();

    // What they're paying for.
    let rowY = y + ROW_TOP;
    person.items.forEach((item) => {
      ctx.textAlign = "right";
      ctx.font = font(600, 14);
      ctx.fillStyle = C.text;
      const share = fmt(item.share);
      ctx.fillText(share, innerRight, rowY);
      const shareW = ctx.measureText(share).width;

      ctx.textAlign = "left";
      ctx.font = font(400, 14);
      ctx.fillStyle = "#3d4754";
      ctx.fillText(
        ellipsize(ctx, item.name, innerRight - innerLeft - shareW - 16),
        innerLeft,
        rowY
      );
      rowY += ITEM_ROW_H;
    });

    // Their slice of tax + tip, sized to what they ate.
    if (parseFloat(person.extras) > 0) {
      ctx.fillStyle = C.muted;
      ctx.font = font(400, 13);
      ctx.textAlign = "left";
      ctx.fillText(labels.taxTip, innerLeft, rowY);
      ctx.textAlign = "right";
      ctx.fillText(fmt(person.extras), innerRight, rowY);
    }

    y += h + CARD_GAP;
  });

  // ── Grand total ──
  const grand = summary.people.reduce((sum, p) => sum + parseFloat(p.total), 0);
  ctx.fillStyle = C.bar;
  roundRect(ctx, left, y, right - left, TOTAL_BAR_H - CARD_GAP, RADIUS);
  ctx.fill();

  const barBaseline = y + (TOTAL_BAR_H - CARD_GAP) / 2 + 7;
  ctx.fillStyle = C.barText;
  ctx.textAlign = "left";
  ctx.font = font(700, 17);
  ctx.fillText(labels.grandTotal, innerLeft, barBaseline);
  ctx.textAlign = "right";
  ctx.font = font(800, 21);
  ctx.fillText(`${fmt(grand)} ${summary.currency}`.trim(), innerRight, barBaseline);

  y += TOTAL_BAR_H;

  // ── Footer ──
  ctx.fillStyle = C.muted;
  ctx.font = font(500, 13);
  ctx.textAlign = "center";
  ctx.fillText(labels.brand, W / 2, y + 16);

  return canvas;
}

export function renderSummaryImage(
  summary: SummaryOut,
  labels: ReceiptImageLabels
): Promise<Blob> {
  const canvas = renderSummaryCanvas(summary, labels);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) =>
        blob ? resolve(blob) : reject(new Error("Canvas rendering failed")),
      "image/png"
    );
  });
}
