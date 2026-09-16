import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import ConfirmSheet from "./ConfirmSheet";

/** Promote someone straight from their Telegram id.
 *
 * The user list can only offer people who have already opened the Mini App,
 * which is exactly the wrong constraint when onboarding a new admin — you
 * usually have their id and nothing else. This takes the id, creates the row
 * if there isn't one, and their name fills in the first time they open the
 * app. */
export default function AddAdminForm() {
  const queryClient = useQueryClient();
  const [value, setValue] = useState("");
  const [confirming, setConfirming] = useState<number | null>(null);

  const promote = useMutation({
    mutationFn: (id: number) => api.adminSetAdmin(id, true),
    onSuccess: () => {
      setConfirming(null);
      setValue("");
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
  });

  // Telegram ids are plain positive integers; anything else is a typo, most
  // often a pasted @username.
  const id = /^\d+$/.test(value.trim()) ? Number(value.trim()) : null;

  return (
    <div className="add-admin">
      <div className="label">ID bo'yicha admin qo'shish</div>
      <p style={{ margin: 0, fontSize: 13, color: "var(--hint)", lineHeight: 1.45 }}>
        Telegram ID ni kiriting. Bu odam ilovani hali ochmagan bo'lsa ham
        bo'ladi — ismi birinchi kirganda o'zi paydo bo'ladi.
      </p>
      <div className="add-admin-row">
        <input
          type="text"
          inputMode="numeric"
          placeholder="masalan 978440562"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <button
          className="btn-mini btn-mini-primary"
          disabled={id === null}
          onClick={() => id !== null && setConfirming(id)}
        >
          Qo'shish
        </button>
      </div>

      {value.trim() !== "" && id === null && (
        <p className="error">Faqat raqamlardan iborat Telegram ID kiriting.</p>
      )}
      {promote.isError && (
        <p className="error">{(promote.error as Error).message}</p>
      )}

      {confirming !== null && (
        <ConfirmSheet
          title="Admin qilish"
          body={`${confirming} ID li foydalanuvchi admin panelga to'liq kirish huquqini oladi: barcha foydalanuvchilar, statistika va boshqa adminlarni boshqarish. ID to'g'ri ekanini tekshirdingizmi?`}
          confirmLabel="Ha, admin qilish"
          busy={promote.isPending}
          onConfirm={() => promote.mutate(confirming)}
          onCancel={() => setConfirming(null)}
        />
      )}
    </div>
  );
}
