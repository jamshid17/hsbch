import { useEffect, useState } from "react";

interface Props {
  name: string;
  userId: number;
  busy?: boolean;
  error?: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

/**
 * Block someone, with a reason.
 *
 * The reason is optional but asked for every time, because the person who
 * later wonders why an account can't get in is rarely the one who blocked it
 * — and it is shown back to the user, so they know it wasn't a fault.
 */
export default function BlockSheet({
  name,
  userId,
  busy,
  error,
  onConfirm,
  onCancel,
}: Props) {
  const [reason, setReason] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);

  return (
    <>
      <div className="overlay" onClick={busy ? undefined : onCancel} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={name}>
        <div className="sheet-handle" />
        <h3>Foydalanuvchini bloklash</h3>
        <p style={{ margin: 0, fontSize: 14, color: "var(--hint)", lineHeight: 1.45 }}>
          {name} ({userId}) ilovaga ham, botga ham kira olmaydi. Hisoblari,
          tanlovlari va obunasi joyida qoladi — blokdan chiqarsangiz hammasi
          o'z holicha tiklanadi.
        </p>

        <div>
          <div className="label">Sabab (ixtiyoriy, foydalanuvchiga ko'rsatiladi)</div>
          <input
            type="text"
            value={reason}
            maxLength={200}
            placeholder="mas. spam"
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        {error && <p className="error">{error}</p>}

        <button
          className="btn btn-danger"
          disabled={busy}
          onClick={() => onConfirm(reason.trim())}
        >
          {busy ? "…" : "Ha, bloklash"}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          Bekor qilish
        </button>
      </div>
    </>
  );
}
