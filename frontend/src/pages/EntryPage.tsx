import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { getJoinCode } from "../telegram";
import { useSubscribe } from "../lib/useSubscribe";
import CardPayment from "../components/CardPayment";

export default function EntryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
  });

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  const { subscribe, state: subState } = useSubscribe(config?.bot_username);

  // Deep link (?join=CODE or Telegram startapp) → jump straight to join.
  useEffect(() => {
    const code = getJoinCode();
    if (code) navigate(`/join?code=${code}`, { replace: true });
  }, [navigate]);

  const subUntil = me?.subscription_until
    ? new Date(me.subscription_until).toLocaleDateString()
    : null;

  return (
    <div className="page">
      <h1>{t("entry.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("entry.subtitle")}</p>

      <button className="btn" onClick={() => navigate("/scan")}>
        {t("entry.scanBtn")}
      </button>
      <button className="btn btn-ghost" onClick={() => navigate("/join")}>
        {t("entry.joinBtn")}
      </button>

      {me?.is_subscribed && (
        <p style={{ color: "var(--hint)", fontSize: 14, textAlign: "center" }}>
          {t("entry.subActive", { date: subUntil })}
        </p>
      )}

      {/* Free scans left — no upsell while the user still has some. */}
      {me && !me.is_subscribed && me.scans_left > 0 && (
        <p style={{ color: "var(--hint)", fontSize: 13, textAlign: "center" }}>
          {t("entry.scansLeft", {
            left: me.scans_left,
            total: me.free_total_scans,
          })}
        </p>
      )}

      {/* Out of free scans: this is where the subscription is offered. */}
      {me && !me.is_subscribed && me.scans_left === 0 && (
        <>
          <p style={{ color: "var(--hint)", fontSize: 13, textAlign: "center" }}>
            {t("entry.freeUsedUp", { total: me.free_total_scans })}
          </p>
          <button
            className="btn"
            disabled={subState === "opening"}
            onClick={subscribe}
          >
            {t("entry.subscribeStars", {
              stars: me.price_stars,
              days: me.subscription_days,
            })}
          </button>

          {me.card && (
            <>
              <div className="or-divider">{t("card.or")}</div>
              <CardPayment card={me.card} />
            </>
          )}
        </>
      )}

      {subState === "cancelled" && <p className="error">{t("pay.cancelled")}</p>}
      {subState === "failed" && <p className="error">{t("pay.failed")}</p>}
      {subState === "paid" && <p className="success">{t("pay.activated")}</p>}
    </div>
  );
}
