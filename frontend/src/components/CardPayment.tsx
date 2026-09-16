import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { MeOut } from "../api";
import { tg } from "../telegram";

/** Manual card payment: the user transfers the amount, then sends the receipt
 * to the admin, who enables the subscription by hand. */
export default function CardPayment({ card }: { card: NonNullable<MeOut["card"]> }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  async function copyCard() {
    try {
      await navigator.clipboard.writeText(card.number.replace(/\s/g, ""));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* Clipboard can be blocked in the in-app browser — the number is on
         screen anyway. */
    }
  }

  return (
    <div className="card" style={{ gap: 10 }}>
      <div className="label">{t("card.title")}</div>

      <div className="card-number-row" onClick={copyCard}>
        <span className="card-number">{card.number}</span>
        <span style={{ fontSize: 13, color: "var(--link)", whiteSpace: "nowrap" }}>
          {copied ? t("card.copied") : t("card.copy")}
        </span>
      </div>

      {card.holder && (
        <div style={{ fontSize: 14, fontWeight: 600 }}>{card.holder}</div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15 }}>
        <span style={{ color: "var(--hint)" }}>{t("card.amount")}</span>
        <span style={{ fontWeight: 700 }}>
          {card.price_uzs.toLocaleString("ru-RU")} {t("card.currency")}
        </span>
      </div>

      <p style={{ margin: 0, fontSize: 13, color: "var(--hint)", lineHeight: 1.45 }}>
        {t("card.instruction", { admin: card.admin_contact })}
      </p>

      <button
        className="btn btn-ghost"
        onClick={() => tg.openTelegramLink(`https://t.me/${card.admin_contact}`)}
      >
        {t("card.sendReceipt", { admin: card.admin_contact })}
      </button>
    </div>
  );
}
