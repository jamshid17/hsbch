import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { getJoinToken } from "../telegram";
import CardPayment from "../components/CardPayment";
import PaywallSheet from "../components/PaywallSheet";
import LanguageSwitcher from "../components/LanguageSwitcher";
import SessionHistory from "../components/SessionHistory";

export default function EntryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  const [showPaywall, setShowPaywall] = useState(false);
  // Scanning is the only gated action — joining someone else's bill stays free.
  // With the paid tier switched off nothing is gated at all, so the lock, the
  // remaining-scans line and the card block all disappear together.
  const paid = !!me?.subscriptions_enabled;
  const locked = paid && !!me && !me.is_subscribed && me.scans_left === 0;

  // Deep link (?join=<token> or Telegram startapp) → jump straight to join.
  useEffect(() => {
    const token = getJoinToken();
    if (token) navigate(`/join?code=${encodeURIComponent(token)}`, { replace: true });
  }, [navigate]);

  const subUntil = me?.subscription_until
    ? new Date(me.subscription_until).toLocaleDateString()
    : null;

  return (
    <div className="page">
      <h1>{t("entry.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("entry.subtitle")}</p>

      <button
        className={`btn ${locked ? "btn-locked" : ""}`}
        onClick={() => (locked ? setShowPaywall(true) : navigate("/scan"))}
        aria-disabled={locked}
      >
        {locked ? `🔒 ${t("entry.scanBtn")}` : t("entry.scanBtn")}
      </button>
      <button className="btn btn-ghost" onClick={() => navigate("/join")}>
        {t("entry.joinBtn")}
      </button>

      {me?.is_admin && (
        <button className="btn btn-ghost" onClick={() => navigate("/admin")}>
          {t("entry.adminBtn")}
        </button>
      )}

      {paid && me?.is_subscribed && (
        <p style={{ color: "var(--hint)", fontSize: 14, textAlign: "center" }}>
          {t("entry.subActive", { date: subUntil })}
        </p>
      )}

      {/* Free scans left — no upsell while the user still has some. */}
      {paid && me && !me.is_subscribed && me.scans_left > 0 && (
        <p style={{ color: "var(--hint)", fontSize: 13, textAlign: "center" }}>
          {t("entry.scansLeft", {
            left: me.scans_left,
            total: me.free_total_scans,
          })}
        </p>
      )}

      {/* Out of free scans: this is where the subscription is offered. */}
      {locked && me && (
        <>
          <p style={{ color: "var(--hint)", fontSize: 13, textAlign: "center" }}>
            {t("entry.freeUsedUp", { total: me.free_total_scans })}
          </p>
          {me.card && <CardPayment card={me.card} />}
        </>
      )}

      <SessionHistory />

      {showPaywall && me && (
        <PaywallSheet me={me} onClose={() => setShowPaywall(false)} />
      )}

      {/* The language is picked once, and the build number is only ever
          checked after a deploy — neither belongs on every screen. */}
      <div className="entry-footer">
        <LanguageSwitcher />
        <span className="app-version">
          v{import.meta.env.VITE_APP_VERSION ?? "dev"}
        </span>
      </div>
    </div>
  );
}
