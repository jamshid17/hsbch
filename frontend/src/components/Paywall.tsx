import { useTranslation } from "react-i18next";
import type { MeOut } from "../api";
import { tg } from "../telegram";
import CardPayment from "./CardPayment";

/** Shown wherever scanning is blocked: says why, what it costs, and the exact
 * steps to get unblocked. */
export default function Paywall({ me }: { me: MeOut }) {
  const { t } = useTranslation();
  const admin = me.card?.admin_contact ?? "hsbchadmin";

  return (
    <div className="paywall">
      <div className="paywall-head">
        <div className="paywall-icon">🔒</div>
        <h2 className="paywall-title">{t("paywall.title")}</h2>
        <p className="paywall-body">
          {t("paywall.body", {
            total: me.free_total_scans,
            days: me.subscription_days,
          })}
        </p>
      </div>

      <div className="paywall-steps">
        <div className="label">{t("paywall.how")}</div>
        <ol>
          <li>
            {me.card
              ? t("paywall.step1", {
                  amount: me.card.price_uzs.toLocaleString("ru-RU"),
                })
              : t("paywall.step1NoCard", { admin })}
          </li>
          <li>{t("paywall.step2", { admin })}</li>
          <li>{t("paywall.step3")}</li>
        </ol>
      </div>

      {me.card ? (
        <CardPayment card={me.card} />
      ) : (
        <button
          className="btn"
          onClick={() => tg.openTelegramLink(`https://t.me/${admin}`)}
        >
          {t("card.sendReceipt", { admin })}
        </button>
      )}
    </div>
  );
}
