import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api, SummaryOut } from "../api";
import Skeleton from "../components/Skeleton";

export default function SummaryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<SummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.getSummary(sessionId!)
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [sessionId]);

  function buildShareText(s: SummaryOut) {
    const lines = s.people.map(
      (p) => `${p.name}: ${s.currency}${p.total}`
    );
    return `Bill split 🧾\n${lines.join("\n")}`;
  }

  async function handleShare() {
    if (!summary) return;
    const text = buildShareText(summary);

    // 1. Native share sheet (mobile browsers + Telegram WebView)
    if (navigator.share) {
      try {
        await navigator.share({ text });
        return;
      } catch {
        // user cancelled or not supported — fall through
      }
    }

    // 2. Clipboard copy
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // clipboard also blocked — show the text in an alert
      window.alert(text);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Who owes what</h1>
        <Skeleton count={3} height={120} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <p className="error">{error}</p>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="page">
      <h1>Who owes what</h1>

      {summary.people.map((person) => (
        <div className="card" key={person.person_id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span style={{ fontWeight: 700, fontSize: 17 }}>{person.name}</span>
            <span style={{ fontWeight: 700, fontSize: 17 }}>
              {summary.currency}{person.total}
            </span>
          </div>

          <div style={{ borderTop: "1px solid var(--secondary-bg)", paddingTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            {person.items.map((item, idx) => (
              <div className="row" key={idx} style={{ justifyContent: "space-between" }}>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>{item.name}</span>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>
                  {summary.currency}{item.share}
                </span>
              </div>
            ))}
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--hint)", fontSize: 13 }}>Tax + tip share</span>
              <span style={{ color: "var(--hint)", fontSize: 13 }}>
                {summary.currency}{person.extras}
              </span>
            </div>
          </div>
        </div>
      ))}

      <button className="btn btn-ghost" onClick={handleShare}>
        Share results
      </button>

      <button
        className="btn"
        style={{ background: "var(--secondary-bg)", color: "var(--text)" }}
        onClick={() => navigate("/")}
      >
        Split another bill
      </button>

      {/* Copied toast */}
      <AnimatePresence>
        {copied && (
          <motion.div
            className="toast"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
          >
            ✓ Copied to clipboard
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
