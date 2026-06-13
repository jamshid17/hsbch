import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, SummaryOut } from "../api";
import { tg } from "../telegram";
import Skeleton from "../components/Skeleton";

function fmt(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  const dec = num % 1 !== 0;
  return num.toLocaleString("ru-RU", {
    minimumFractionDigits: dec ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

export default function HostLivePage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId!),
  });

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
    staleTime: Infinity,
  });

  // Poll the live breakdown so the host sees picks as they come in.
  const { data: summary, isLoading } = useQuery<SummaryOut>({
    queryKey: ["live-summary", sessionId],
    queryFn: () => api.getSummary(sessionId!),
    refetchInterval: 3000,
  });

  const finalizeMutation = useMutation({
    mutationFn: () => api.finalizeSession(sessionId!),
    onSuccess: () => navigate(`/summary/${sessionId}`),
  });

  const code = session?.code || "";
  const cur = summary?.currency || "";

  // Deep link that opens the Mini App and auto-joins this session. Tapping it
  // sets Telegram's start_param=<code>, which the app reads to jump to /join.
  const inviteLink = config?.bot_username
    ? `https://t.me/${config.bot_username}?startapp=${code}`
    : `${window.location.origin}/?join=${code}`;

  async function shareCode() {
    if (tg.initData) {
      // Open Telegram's "share to chat" sheet with the clickable invite link.
      const text = t("host.inviteText", { code });
      tg.openTelegramLink(
        `https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent(text)}`
      );
      return;
    }
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.alert(inviteLink);
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="page">
      <h1>{t("host.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("host.subtitle")}</p>

      {/* Code card */}
      <div className="card" style={{ alignItems: "center", gap: 8 }}>
        <div className="label">{t("host.codeLabel")}</div>
        <div
          style={{ fontSize: 40, fontWeight: 800, letterSpacing: 8, cursor: "pointer" }}
          onClick={copyCode}
        >
          {code || "······"}
        </div>
        <div className="row" style={{ gap: 8, width: "100%", alignItems: "stretch" }}>
          <button className="btn btn-ghost" style={{ flex: 1, margin: 0 }} onClick={copyCode}>
            {copied ? t("host.copied") : t("host.copy")}
          </button>
          <button className="btn" style={{ flex: 1, margin: 0 }} onClick={shareCode}>
            {t("host.share")}
          </button>
        </div>
      </div>

      {/* Participants */}
      <h3 style={{ marginBottom: 4 }}>{t("host.people")}</h3>
      {isLoading ? (
        <Skeleton count={3} height={72} />
      ) : !summary || summary.people.length === 0 ? (
        <p style={{ color: "var(--hint)" }}>{t("host.waiting")}</p>
      ) : (
        summary.people.map((p) => (
          <div key={p.person_id} className="summary-card">
            <div className="summary-header">
              <span className="summary-name">👤 {p.name}</span>
              <div className="summary-total-block">
                <span className="summary-total">{fmt(p.total)}</span>
                <span className="summary-cur">{cur}</span>
              </div>
            </div>
            <div className="summary-rows">
              {p.items.length === 0 ? (
                <div className="summary-row summary-row-extra">
                  <span>{t("host.nothingYet")}</span>
                </div>
              ) : (
                p.items.map((it, idx) => (
                  <div className="summary-row" key={idx}>
                    <span className="summary-row-name">{it.name}</span>
                    <span className="summary-row-amt">{fmt(it.share)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        ))
      )}

      <button
        className="btn btn-ghost"
        onClick={() => navigate(`/pick/${sessionId}`)}
      >
        {t("host.pickMine")}
      </button>

      <button
        className="btn"
        disabled={finalizeMutation.isPending}
        onClick={() => finalizeMutation.mutate()}
      >
        {finalizeMutation.isPending ? t("host.finalizing") : t("host.finalize")}
      </button>

      <AnimatePresence>
        {copied && (
          <motion.div
            className="toast"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
          >
            {t("host.copied")}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
