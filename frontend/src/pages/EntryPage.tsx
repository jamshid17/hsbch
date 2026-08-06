import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { getJoinCode, tg } from "../telegram";

export default function EntryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
  });

  // Deep link (?join=CODE or Telegram startapp) → jump straight to join.
  useEffect(() => {
    const code = getJoinCode();
    if (code) navigate(`/join?code=${code}`, { replace: true });
  }, [navigate]);

  function handleSubscribe() {
    tg.openTelegramLink(`https://t.me/${config?.bot_username ?? "hsbchbot"}?start=subscribe`);
  }

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
      <button className="btn btn-ghost" onClick={handleSubscribe}>
        {t("entry.subscribeBtn")}
      </button>
    </div>
  );
}
