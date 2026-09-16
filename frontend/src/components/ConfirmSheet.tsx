import { useEffect } from "react";

interface Props {
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Bottom-sheet confirmation. Built in-app rather than with window.confirm or
 * Telegram's showConfirm: native dialogs block the WebView and the Telegram
 * one is unavailable in a plain browser, which is where dev testing happens. */
export default function ConfirmSheet({
  title,
  body,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <>
      <div className="overlay" onClick={busy ? undefined : onCancel} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sheet-handle" />
        <h3>{title}</h3>
        <p style={{ margin: 0, fontSize: 14, color: "var(--hint)", lineHeight: 1.45 }}>
          {body}
        </p>
        <button
          className={`btn ${danger ? "btn-danger" : ""}`}
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? "…" : confirmLabel}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          Bekor qilish
        </button>
      </div>
    </>
  );
}
