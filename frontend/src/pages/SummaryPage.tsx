import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, SummaryOut } from "../api";
import { tg } from "../telegram";
import Skeleton from "../components/Skeleton";

export default function SummaryPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<SummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.getSummary(sessionId!)
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : t("summary.failedLoad")))
      .finally(() => setLoading(false));
  }, [sessionId]);

  async function handleShare() {
    if (!summary) return;

    if (tg.initData) {
      tg.switchInlineQuery(sessionId!, ["users", "groups"]);
      return;
    }

    const lines = summary.people.map((p) => `${p.name}: ${summary.currency}${p.total}`);
    const text = `🧾 Bill split\n${lines.join("\n")}`;

    if (navigator.share) {
      try { await navigator.share({ text }); return; } catch { /* cancelled */ }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      window.alert(text);
    }
  }

  if (loading) return <div className="page"><h1>{t("summary.title")}</h1><Skeleton count={3} height={120} /></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!summary) return null;

  return (
    <div className="page">
      <h1>{t("summary.title")}</h1>

      {summary.people.map((person) => (
        <div className="card" key={person.person_id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span style={{ fontWeight: 700, fontSize: 17 }}>{person.name}</span>
            <span style={{ fontWeight: 700, fontSize: 17 }}>{summary.currency}{person.total}</span>
          </div>
          <div style={{ borderTop: "1px solid var(--secondary-bg)", paddingTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            {person.items.map((item, idx) => (
              <div className="row" key={idx} style={{ justifyContent: "space-between" }}>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>{item.name}</span>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>{summary.currency}{item.share}</span>
              </div>
            ))}
            {parseFloat(person.extras) > 0 && (
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span style={{ color: "var(--hint)", fontSize: 13 }}>{t("summary.taxTip")}</span>
                <span style={{ color: "var(--hint)", fontSize: 13 }}>{summary.currency}{person.extras}</span>
              </div>
            )}
          </div>
        </div>
      ))}

      <button className="btn" onClick={handleShare}>
        {tg.initData ? t("summary.shareBtn") : t("summary.shareBtnFallback")}
      </button>

      <button className="btn btn-ghost" onClick={() => navigate("/")}>
        {t("summary.splitAnother")}
      </button>

      <AnimatePresence>
        {copied && (
          <motion.div className="toast"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }} transition={{ duration: 0.2 }}
          >
            {t("summary.copied")}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
