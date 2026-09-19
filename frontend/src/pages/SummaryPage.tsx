import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, SummaryOut } from "../api";
import { renderSummaryImage } from "../lib/receiptImage";
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

/** How much of the receipt's name goes into the share query — enough to say
 * which bill it is, short enough not to fill the input field. */
const MAX_QUERY_NAME = 20;

/** "<receipt> <code> <lang>", e.g. "Istanbul 0729 uz" — what sits in the
 * input field while a chat is picked. The bot reads it from the end, so the
 * name in front is free to be whatever the receipt is called. */
function inlineQuery(title: string, code: string, lang: string): string {
  let name = title.replace(/\s+/g, " ").trim();
  if (name.length > MAX_QUERY_NAME) {
    // Cut back to a word boundary rather than mid-word.
    name = name.slice(0, MAX_QUERY_NAME).replace(/\s\S*$/, "");
  }
  return [name, code, lang].filter(Boolean).join(" ");
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  // Revoked on the next tick — Safari needs the object URL to outlive the click.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function SummaryPage() {
  const { t, i18n } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<SummaryOut | null>(null);
  const [shareLink, setShareLink] = useState("");
  const [code, setCode] = useState("");
  const [botUsername, setBotUsername] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [imageBusy, setImageBusy] = useState(false);

  useEffect(() => {
    Promise.all([
      api.getSummary(sessionId!),
      api.getSession(sessionId!),
      api.getConfig(),
    ])
      .then(([sum, session, config]) => {
        setSummary(sum);
        setBotUsername(config.bot_username);
        setCode(session.code);
        // Same deep link as the invite — opening a finished session jumps
        // straight to this summary (JoinPage routes `done` sessions here).
        setShareLink(
          config.bot_username
            ? `https://t.me/${config.bot_username}?startapp=${session.code}`
            : `${window.location.origin}/?join=${session.code}`
        );
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : t("summary.failedLoad"))
      )
      .finally(() => setLoading(false));
  }, [sessionId]);

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(""), 2500);
  }

  async function handleShare() {
    if (!summary) return;
    const lines = summary.people.map(
      (p) => `${p.name}: ${fmt(p.total)} ${summary.currency}`
    );
    const text = `🧾 ${t("summary.title")}\n${lines.join("\n")}`;

    if (tg.initData && code) {
      // Inline mode, so the bot composes the message: the share dialog can
      // only send plain text, which leaves the deep link sitting there raw,
      // while the bot can hide it behind "see how it was calculated".
      // The language rides along — the bot can't read the app's own setting.
      try {
        tg.switchInlineQuery(
          inlineQuery(summary.title || "", code, i18n.language),
          ["users", "groups", "channels"]
        );
        return;
      } catch {
        // Inline mode off or an older client — the plain dialog still works.
      }
    }

    if (tg.initData && shareLink) {
      tg.openTelegramLink(
        `https://t.me/share/url?url=${encodeURIComponent(shareLink)}&text=${encodeURIComponent(text)}`
      );
      return;
    }

    const full = shareLink ? `${text}\n${shareLink}` : text;
    if (navigator.share) {
      try { await navigator.share({ text: full }); return; } catch { /* cancelled */ }
    }
    try {
      await navigator.clipboard.writeText(full);
      showToast(t("summary.copied"));
    } catch { window.alert(full); }
  }

  /** Share the split as a picture — the whole breakdown in one glance, with
   * no need for the other person to open anything. */
  async function handleShareImage() {
    if (!summary || imageBusy) return;
    setImageBusy(true);
    try {
      const blob = await renderSummaryImage(summary, {
        taxTip: t("summary.taxTip"),
        grandTotal: t("summary.grandTotal"),
        subtitle: t("summary.title"),
        brand: botUsername ? `@${botUsername}` : t("summary.imageBrand"),
      });

      // A Mini App can't drop a file into a chat, so the bot posts the card to
      // the user's own chat with a share button they tap to pass it on.
      if (tg.initData) {
        const grand = summary.people.reduce((s, p) => s + parseFloat(p.total), 0);
        const caption = `🧾 ${summary.title || t("summary.title")} — ${fmt(grand)} ${summary.currency}`;
        try {
          await api.sendSummaryImage(
            sessionId!,
            blob,
            caption.trim(),
            t("summary.imageShareLabel"),
            i18n.language
          );
          showToast(t("summary.imageSent"));
          return;
        } catch {
          // Bot blocked or never started — fall through to the plain file.
        }
      }

      const file = new File([blob], "hisob.png", { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        try { await navigator.share({ files: [file] }); } catch { /* cancelled */ }
        return;
      }

      downloadBlob(blob, "hisob.png");
      showToast(t("summary.imageSaved"));
    } catch {
      showToast(t("summary.imageFailed"));
    } finally {
      setImageBusy(false);
    }
  }

  if (loading) return <div className="page"><h1>{t("summary.title")}</h1><Skeleton count={3} height={130} /></div>;

  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!summary) return null;

  const grandTotal = summary.people.reduce((sum, p) => sum + parseFloat(p.total), 0);

  return (
    <div className="page">
      <h1>{summary.title || t("summary.title")}</h1>

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

      <button className="btn btn-ghost" onClick={handleShareImage} disabled={imageBusy}>
        {imageBusy ? t("summary.imageBuilding") : t("summary.shareImageBtn")}
      </button>

      <button className="btn btn-ghost" onClick={() => navigate("/")}>
        {t("summary.splitAnother")}
      </button>

      <AnimatePresence>
        {toast && (
          <motion.div className="toast"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }} transition={{ duration: 0.2 }}
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
