import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { UnclaimedItem } from "../api";

interface Props {
  items: UnclaimedItem[];
  total: string;
  currency: string;
  busy?: boolean;
  /** Give the leftovers to everyone in equal parts, then finish. */
  onSplitEvenly: () => void;
  /** Finish knowing the bill will come out short. */
  onIgnore: () => void;
  onCancel: () => void;
}

function fmt(value: string): string {
  const num = parseFloat(value);
  return num.toLocaleString("ru-RU", {
    minimumFractionDigits: num % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

/**
 * The last stop before a bill is finalized with items nobody picked.
 *
 * Their cost is charged to nobody, so the totals would quietly add up to less
 * than the receipt — the one failure of this app a table notices only when
 * the cash is short. The host is shown exactly what and how much, and either
 * shares it out or accepts the gap on purpose.
 */
export default function UnclaimedSheet({
  items,
  total,
  currency,
  busy,
  onSplitEvenly,
  onIgnore,
  onCancel,
}: Props) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);

  return (
    <>
      <div className="overlay" onClick={busy ? undefined : onCancel} />
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={t("unclaimed.title", { count: items.length })}
      >
        <div className="sheet-handle" />
        <h3>{t("unclaimed.title", { count: items.length })}</h3>
        <p style={{ margin: 0, fontSize: 14, color: "var(--hint)", lineHeight: 1.45 }}>
          {t("unclaimed.body", { amount: `${fmt(total)} ${currency}`.trim() })}
        </p>

        <div className="card" style={{ gap: 6 }}>
          {items.map((item) => (
            <div className="summary-row" style={{ padding: 0 }} key={item.item_id}>
              <span className="summary-row-name">{item.name}</span>
              <span className="summary-row-amt">{fmt(item.amount)}</span>
            </div>
          ))}
        </div>

        <button className="btn" disabled={busy} onClick={onSplitEvenly}>
          {busy ? "…" : t("unclaimed.splitEvenly")}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onIgnore}>
          {t("unclaimed.ignore")}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          {t("unclaimed.back")}
        </button>
      </div>
    </>
  );
}
