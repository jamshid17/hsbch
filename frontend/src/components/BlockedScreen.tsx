import { useTranslation } from "react-i18next";
import { tg } from "../telegram";

/** Where a blocked account ends up. Nothing here can be retried — the only
 * way forward is a person, so the screen names who and opens the chat. */
export default function BlockedScreen({
  message,
  admin,
}: {
  message: string;
  admin?: string;
}) {
  const { t } = useTranslation();
  const handle = (admin || "hsbchadmin").replace(/^@/, "");

  return (
    <>
      <div style={{ fontSize: 40 }}>🚫</div>
      <p style={{ margin: 0, fontSize: 15, lineHeight: 1.5 }}>{message}</p>
      <p style={{ margin: 0, fontSize: 14, color: "var(--hint)" }}>
        {t("blocked.contactHint")}
      </p>
      <button
        className="btn"
        style={{ maxWidth: 280 }}
        onClick={() => tg.openTelegramLink(`https://t.me/${handle}`)}
      >
        {t("blocked.contact", { admin: handle })}
      </button>
    </>
  );
}
