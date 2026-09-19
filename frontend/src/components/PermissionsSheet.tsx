import { useEffect, useState } from "react";
import clsx from "clsx";
import { PERMISSIONS, type PermissionKey } from "../lib/permissions";

interface Props {
  name: string;
  /** What the admin holds now. */
  current: string[];
  /** What the person editing holds — nobody can grant past their own. */
  mine: string[];
  busy?: boolean;
  error?: string;
  onSave: (permissions: string[]) => void;
  onCancel: () => void;
}

/**
 * Tick what an admin may do.
 *
 * Grants the editor doesn't hold themselves are shown but not tickable: the
 * backend refuses them anyway, and a checkbox that fails on save teaches
 * nothing. Seeing the whole list is what makes the missing ones legible as
 * "not yours to give" rather than "doesn't exist".
 */
export default function PermissionsSheet({
  name,
  current,
  mine,
  busy,
  error,
  onSave,
  onCancel,
}: Props) {
  const [picked, setPicked] = useState<Set<string>>(new Set(current));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);

  function toggle(key: PermissionKey, locked: boolean) {
    if (locked) return;
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <>
      <div className="overlay" onClick={busy ? undefined : onCancel} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={name}>
        <div className="sheet-handle" />
        <h3>{name} — huquqlar</h3>
        <p style={{ margin: 0, fontSize: 13, color: "var(--hint)", lineHeight: 1.45 }}>
          Admin har doim umumiy statistika va foydalanuvchilar ro'yxatini
          ko'radi. Quyidagilar — shundan tashqari nima qila olishi.
        </p>

        {PERMISSIONS.map((p) => {
          const checked = picked.has(p.key);
          // Can't hand on what you don't hold — unless it's already theirs,
          // in which case taking it away is still fair game.
          const locked = !mine.includes(p.key) && !current.includes(p.key);
          return (
            <div
              key={p.key}
              className={clsx("check-row", { "check-row-locked": locked })}
              role="button"
              tabIndex={locked ? -1 : 0}
              aria-pressed={checked}
              aria-disabled={locked}
              onClick={() => toggle(p.key, locked)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggle(p.key, locked);
                }
              }}
            >
              <div className={clsx("checkmark", { checked })}>{checked && "✓"}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{p.label}</div>
                <div className="stat-hint">
                  {locked ? "Sizda bu huquq yo'q" : p.hint}
                </div>
              </div>
            </div>
          );
        })}

        {error && <p className="error">{error}</p>}

        <button
          className="btn"
          disabled={busy}
          onClick={() => onSave([...picked])}
        >
          {busy ? "…" : "Saqlash"}
        </button>
        <button className="btn btn-ghost" disabled={busy} onClick={onCancel}>
          Bekor qilish
        </button>
      </div>
    </>
  );
}
