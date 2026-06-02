import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, SummaryOut } from "../api";
import { tg } from "../telegram";
import Skeleton from "../components/Skeleton";

// Format number with space as thousands separator, strip trailing .00
function fmt(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  const hasDecimals = num % 1 !== 0;
  return num.toLocaleString("ru-RU", {
    minimumFractionDigits: hasDecimals ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

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
    const lines = summary.people.map((p) => `${p.name}: ${fmt(p.total)} ${summary.currency}`);
    const text = `🧾 Bill split\n${lines.join("\n")}`;
    if (navigator.share) {
      try { await navigator.share({ text }); return; } catch { /* cancelled */ }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch { window.alert(text); }
  }

  if (loading) return <div className="page"><h1>{t("summary.title")}</h1><Skeleton count={3} height={130} /></div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!summary) return null;

  const grandTotal = summary.people.reduce((sum, p) => sum + parseFloat(p.total), 0);

  return (
    <div className="page">
      <h1>{t("summary.title")}</h1>

      {summary.people.map((person, i) => (
        <motion.div
          key={person.person_id}
          className="summary-card"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06 }}
        >
          {/* Header: name + total */}
          <div className="summary-header">
            <span className="summary-name">👤 {person.name}</span>
            <div className="summary-total-block">
              <span className="summary-total">{fmt(person.total)}</span>
              <span className="summary-cur">{summary.currency}</span>
            </div>
          </div>

          {/* Item rows */}
          <div className="summary-rows">
            {person.items.map((item, idx) => (
              <div className="summary-row" key={idx}>
                <span className="summary-row-name">{item.name}</span>
                <span className="summary-row-amt">{fmt(item.share)}</span>
              </div>
            ))}
            {parseFloat(person.extras) > 0 && (
              <div className="summary-row summary-row-extra">
                <span>{t("summary.taxTip")}</span>
                <span>{fmt(person.extras)}</span>
              </div>
            )}
          </div>
        </motion.div>
      ))}

      {/* Grand total */}
      <div className="grand-total">
        <span>{t("summary.grandTotal")}</span>
        <span>{fmt(grandTotal)} {summary.currency}</span>
      </div>

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
