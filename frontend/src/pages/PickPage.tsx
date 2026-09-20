import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { api, ItemOut, ParticipantOut } from "../api";
import { getTelegramUser, haptic } from "../telegram";
import { claimCapacity, fmtQty, MAX_QTY } from "../lib/format";
import { useSessionSocket } from "../lib/useSessionSocket";
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

  const isHost = !!session && session.telegram_chat_id === myId;

  // Live updates: others' picks refetch instantly; when the host finalizes
  // (status=done), everyone jumps to the final summary.
  useSessionSocket(sessionId, (msg) => {
    if (msg.status === "done") navigate(`/summary/${sessionId}`, { replace: true });
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

  const othersByItem = useMemo(() => {
    const map: Record<string, string[]> = {};
    participants?.forEach((p) => {
      if (p.telegram_user_id === myId) return;
      p.picks.forEach((pk) => {
        if (Number(pk.quantity) <= 0) return;
        (map[pk.item_id] ||= []).push(p.name);
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

  /** The most of this item I can still claim: whatever the others have left
   * of a counted item, or no limit at all for a dish being shared. */
  function myCeiling(item: ItemOut): number {
    const capacity = claimCapacity(item.quantity);
    if (capacity === null) return MAX_QTY;
    return Math.min(MAX_QTY, capacity - (othersQty[item.id] || 0));
  }

  function toggle(item: ItemOut) {
    // Nothing left of it — the card is shown as taken, and this is the
    // keyboard path to the same refusal.
    if (!sel[item.id] && myCeiling(item) < 1) return;
    haptic.select();
    setSaved(false);
    setSel((prev) => {
      const next = { ...prev };
      if (next[item.id]) delete next[item.id];
      else next[item.id] = 1;
      return next;
    });
  }

  function step(item: ItemOut, delta: number, e: React.MouseEvent) {
    e.stopPropagation();
    setSaved(false);
    setSel((prev) => {
      const cur = prev[item.id] || 0;
      const nextQty = Math.min(myCeiling(item), Math.max(1, cur + delta));
      return { ...prev, [item.id]: nextQty };
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
    onSuccess: () => {
      // Host: go to the live overview to watch everyone and finalize.
      // Guest: stay here, just confirm the save.
      if (isHost) navigate(`/host/${sessionId}`);
      else setSaved(true);
    },
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
        const others = othersByItem[item.id] ?? [];
        const ceiling = myCeiling(item);
        // Everyone else has taken the lot and I have none of it.
        const taken = !selected && ceiling < 1;
        return (
          <motion.div
            key={item.id}
            className={clsx("card", "tappable", {
              "card-selected": selected,
              "check-row-locked": taken,
            })}
            style={{ flexDirection: "row", alignItems: "center", gap: 12 }}
            role="button"
            tabIndex={taken ? -1 : 0}
            aria-pressed={selected}
            aria-disabled={taken}
            onClick={() => toggle(item)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                toggle(item);
              }
            }}
            whileTap={{ scale: taken ? 1 : 0.98 }}
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
              {others.length > 0 && (
                <div className="item-others">
                  {t("pick.alsoTaken", { names: others.join(", ") })}
                </div>
              )}
              {taken && (
                <div className="item-others item-taken">{t("pick.allTaken")}</div>
              )}
            </div>
            {selected && multi && (
              <div className="qty-stepper" onClick={(e) => e.stopPropagation()}>
                <button onClick={(e) => step(item, -1, e)} disabled={qty <= 1}>−</button>
                <span>{qty}</span>
                <button onClick={(e) => step(item, 1, e)} disabled={qty >= ceiling}>+</button>
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
        className="btn-link"
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
