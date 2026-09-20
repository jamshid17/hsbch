import { useEffect } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  icon?: string;
  title: string;
  body: string;
  /** Extra guidance under the message — what to do differently next time. */
  hint?: string;
  /** Label for the one thing there is to do. Defaults to "got it". */
  actionLabel?: string;
  onClose: () => void;
}

/**
 * Something the reader needs to take in before carrying on.
 *
 * Not a confirmation — there is nothing to weigh up and no second choice,
 * only a fact and the way forward. A line of red text under the photo is
 * easy to miss and reads like a fault; this reads like an answer.
 */
export default function AlertSheet({
  icon = "⚠️",
  title,
  body,
  hint,
  actionLabel,
  onClose,
}: Props) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="sheet" role="alertdialog" aria-modal="true" aria-label={title}>
        <div className="sheet-handle" />
        <div style={{ fontSize: 40, textAlign: "center" }} aria-hidden="true">
          {icon}
        </div>
        <h3 style={{ textAlign: "center" }}>{title}</h3>
        <p
          style={{
            margin: 0,
            fontSize: 15,
            lineHeight: 1.5,
            textAlign: "center",
          }}
        >
          {body}
        </p>
        {hint && (
          <p className="notice" style={{ marginTop: 4 }}>
            {hint}
          </p>
        )}
        <button className="btn" onClick={onClose}>
          {actionLabel ?? t("common.gotIt")}
        </button>
      </div>
    </>
  );
}
