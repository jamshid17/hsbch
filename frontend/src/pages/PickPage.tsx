import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { api, ItemOut, ParticipantOut } from "../api";
import { getTelegramUser } from "../telegram";
import { fmtQty, MAX_QTY } from "../lib/format";
import Skeleton from "../components/Skeleton";

function fmt(n: number): string {
  const dec = n % 1 !== 0;
  return n.toLocaleString("ru-RU", {
    minimumFractionDigits: dec ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

export default function PickPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const myId = getTelegramUser().id;

  // itemId -> claimed quantity (absent = not selected)
  const [sel, setSel] = useState<Record<string, number>>({});
  const [initialized, setInitialized] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId!),
  });

  const { data: items, isLoading } = useQuery<ItemOut[]>({
    queryKey: ["items", sessionId],
    queryFn: () => api.listItems(sessionId!),
  });

  const { data: participants } = useQuery<ParticipantOut[]>({
    queryKey: ["participants", sessionId],
    queryFn: () => api.listParticipants(sessionId!),
  });

  // Seed my current selection from the server once.
  useEffect(() => {
    if (!participants || initialized) return;
    const me = participants.find((p) => p.telegram_user_id === myId);
    const next: Record<string, number> = {};
    me?.picks.forEach((pk) => {
      next[pk.item_id] = Number(pk.quantity);
    });
    setSel(next);
    setInitialized(true);
  }, [participants, initialized, myId]);

  // How much everyone *else* has claimed of each item (for the live share preview).
  const othersQty = useMemo(() => {
    const map: Record<string, number> = {};
    participants?.forEach((p) => {
      if (p.telegram_user_id === myId) return;
      p.picks.forEach((pk) => {
        map[pk.item_id] = (map[pk.item_id] || 0) + Number(pk.quantity);
      });
    });
    return map;
  }, [participants, myId]);

  const cur = session?.currency || "";

  const subtotal = useMemo(() => {
    if (!items) return 0;
    let sum = 0;
    for (const item of items) {
      const mine = sel[item.id];
      if (!mine || mine <= 0) continue;
      const lineTotal = parseFloat(item.price) * parseFloat(item.quantity);
      const totalClaimed = (othersQty[item.id] || 0) + mine;
      sum += lineTotal * (mine / totalClaimed);
    }
    return sum;
  }, [items, sel, othersQty]);

  function toggle(itemId: string) {
    setSaved(false);
    setSel((prev) => {
      const next = { ...prev };
      if (next[itemId]) delete next[itemId];
      else next[itemId] = 1;
      return next;
    });
  }

  function step(itemId: string, delta: number, e: React.MouseEvent) {
    e.stopPropagation();
    setSaved(false);
    setSel((prev) => {
      const cur = prev[itemId] || 0;
      const nextQty = Math.min(MAX_QTY, Math.max(1, cur + delta));
      return { ...prev, [itemId]: nextQty };
    });
  }

  const saveMutation = useMutation({
    mutationFn: () =>
      api.saveMyAssignments(
        sessionId!,
        Object.entries(sel).map(([item_id, qty]) => ({
          item_id,
          quantity: String(qty),
        }))
      ),
    onSuccess: () => setSaved(true),
    onError: (e: unknown) =>
      setError(e instanceof Error ? e.message : t("pick.failedSave")),
  });

  if (isLoading) {
    return (
      <div className="page">
        <h1>{t("pick.title")}</h1>
        <Skeleton count={4} height={64} />
      </div>
    );
  }

  return (
    <div className="page">
      <h1>{t("pick.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("pick.subtitle")}</p>

      {items && items.length === 0 && (
        <p style={{ color: "var(--hint)" }}>{t("pick.empty")}</p>
      )}

      {items?.map((item) => {
        const selected = !!sel[item.id];
        const qty = sel[item.id] || 0;
        const multi = parseFloat(item.quantity) > 1;
        return (
          <motion.div
            key={item.id}
            className={clsx("card", { "card-selected": selected })}
            style={{ cursor: "pointer", flexDirection: "row", alignItems: "center", gap: 12 }}
            onClick={() => toggle(item.id)}
            whileTap={{ scale: 0.98 }}
          >
            <div className={clsx("checkmark", { checked: selected })}>
              {selected && "✓"}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{item.name}</div>
              <div style={{ color: "var(--hint)", fontSize: 13 }}>
                {fmtQty(item.quantity)} {item.unit} × {cur}
                {fmt(parseFloat(item.price))}
              </div>
            </div>
            {selected && multi && (
              <div className="qty-stepper" onClick={(e) => e.stopPropagation()}>
                <button onClick={(e) => step(item.id, -1, e)} disabled={qty <= 1}>−</button>
                <span>{qty}</span>
                <button onClick={(e) => step(item.id, 1, e)} disabled={qty >= MAX_QTY}>+</button>
              </div>
            )}
          </motion.div>
        );
      })}

      <div className="grand-total" style={{ marginTop: 16 }}>
        <span>{t("pick.yourTotal")}</span>
        <span>
          {fmt(subtotal)} {cur}
        </span>
      </div>

      {error && <p className="error">{error}</p>}

      <button
        className="btn"
        disabled={saveMutation.isPending}
        onClick={() => saveMutation.mutate()}
      >
        {saveMutation.isPending
          ? t("pick.saving")
          : saved
            ? t("pick.saved")
            : t("pick.save")}
      </button>

      <button
        className="btn btn-ghost"
        onClick={() => navigate(`/summary/${sessionId}`)}
      >
        {t("pick.viewSummary")}
      </button>

      <AnimatePresence>
        {saved && (
          <motion.div
            className="toast"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
          >
            {t("pick.saved")}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
