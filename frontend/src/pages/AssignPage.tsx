import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { api, ItemOut, PersonOut } from "../api";
import Skeleton from "../components/Skeleton";
import { fmtQty, MAX_QTY } from "../lib/format";
import { storage } from "../lib/storage";

// itemId -> personId -> claimed quantity (absent/0 = not assigned)
type Selection = Record<string, Record<string, number>>;

function fmt(n: number): string {
  const dec = n % 1 !== 0;
  return n.toLocaleString("ru-RU", {
    minimumFractionDigits: dec ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

export default function AssignPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [sel, setSel] = useState<Selection>({});
  const [initialized, setInitialized] = useState(false);
  const [activeItem, setActiveItem] = useState<ItemOut | null>(null);
  const [error, setError] = useState("");

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId!),
  });

  const { data: items, isLoading: itemsLoading } = useQuery<ItemOut[]>({
    queryKey: ["items", sessionId],
    queryFn: () => api.listItems(sessionId!),
  });

  const { data: people, isLoading: peopleLoading } = useQuery<PersonOut[]>({
    queryKey: ["people", sessionId],
    queryFn: () => api.listPeople(sessionId!),
  });

  // Seed from the locally saved draft (keyed by person name, so it survives
  // person UUIDs changing after a trip back to the people-list screen).
  useEffect(() => {
    if (!items || !people || initialized) return;
    const draft = storage.loadAssignments(sessionId!);
    const nameToId = Object.fromEntries(people.map((p) => [p.name, p.id]));
    const next: Selection = {};
    items.forEach((item) => {
      next[item.id] = {};
      const byName = draft?.[item.id];
      if (!byName) return;
      Object.entries(byName).forEach(([name, qty]) => {
        const id = nameToId[name];
        if (id && qty > 0) next[item.id][id] = qty;
      });
    });
    setSel(next);
    setInitialized(true);
  }, [items, people, initialized, sessionId]);

  useEffect(() => {
    if (!people || !initialized) return;
    const idToName = Object.fromEntries(people.map((p) => [p.id, p.name]));
    const byName: Record<string, Record<string, number>> = {};
    Object.entries(sel).forEach(([itemId, byPerson]) => {
      byName[itemId] = {};
      Object.entries(byPerson).forEach(([personId, qty]) => {
        const name = idToName[personId];
        if (name) byName[itemId][name] = qty;
      });
    });
    storage.saveAssignments(sessionId!, byName);
  }, [sel, people, initialized, sessionId]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const assignments = Object.entries(sel).flatMap(([item_id, byPerson]) =>
        Object.entries(byPerson)
          .filter(([, qty]) => qty > 0)
          .map(([person_id, qty]) => ({ item_id, person_id, quantity: String(qty) }))
      );
      return api.setHostAssignments(sessionId!, assignments);
    },
    onSuccess: () => {
      storage.clearAssignments(sessionId!);
      navigate(`/summary/${sessionId}`);
    },
    onError: (e: unknown) =>
      setError(e instanceof Error ? e.message : t("assign.failedSave")),
  });

  function togglePerson(itemId: string, personId: string) {
    setSel((prev) => {
      const byPerson = { ...(prev[itemId] || {}) };
      if (byPerson[personId]) delete byPerson[personId];
      else byPerson[personId] = 1;
      return { ...prev, [itemId]: byPerson };
    });
  }

  function step(itemId: string, personId: string, delta: number, e: React.MouseEvent) {
    e.stopPropagation();
    setSel((prev) => {
      const byPerson = { ...(prev[itemId] || {}) };
      const cur = byPerson[personId] || 0;
      byPerson[personId] = Math.min(MAX_QTY, Math.max(1, cur + delta));
      return { ...prev, [itemId]: byPerson };
    });
  }

  function assignedCount(itemId: string) {
    return Object.keys(sel[itemId] || {}).length;
  }

  const cur = session?.currency || "";

  if (itemsLoading || peopleLoading) {
    return (
      <div className="page">
        <h1>{t("assign.title")}</h1>
        <Skeleton count={4} height={72} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1>{t("assign.title")}</h1>
        <button
          onClick={() => navigate(`/people/${sessionId}`)}
          style={{
            background: "none",
            border: "none",
            color: "var(--link)",
            fontSize: 14,
            cursor: "pointer",
            padding: 0,
          }}
        >
          {t("assign.editPeople")}
        </button>
      </div>

      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("assign.subtitle")}</p>

      {items?.map((item) => {
        const count = assignedCount(item.id);
        return (
          <motion.div
            key={item.id}
            className="card"
            style={{ cursor: "pointer", flexDirection: "row", alignItems: "center" }}
            onClick={() => setActiveItem(item)}
            whileTap={{ scale: 0.98 }}
          >
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600 }}>{item.name}</div>
              <div style={{ color: "var(--hint)", fontSize: 13 }}>
                {fmtQty(item.quantity)} {item.unit} × {cur}
                {fmt(parseFloat(item.price))}
              </div>
            </div>
            <span className={clsx("badge", { "badge-warn": count === 0 })}>
              {count === 0 ? t("assign.unassigned") : t("assign.person", { count })}
            </span>
          </motion.div>
        );
      })}

      {error && <p className="error">{error}</p>}

      <button
        className="btn"
        disabled={saveMutation.isPending || !people || people.length === 0}
        onClick={() => saveMutation.mutate()}
      >
        {saveMutation.isPending ? t("assign.calculating") : t("assign.calculate")}
      </button>

      <AnimatePresence>
        {activeItem && (
          <>
            <motion.div
              className="overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setActiveItem(null)}
            />
            <motion.div
              className="sheet"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
            >
              <div className="sheet-handle" />
              <h3>{activeItem.name}</h3>
              <p style={{ color: "var(--hint)", fontSize: 13, marginTop: -4 }}>
                {t("assign.sheetSubtitle")}
              </p>
              {people?.map((person) => {
                const qty = sel[activeItem.id]?.[person.id] || 0;
                const checked = qty > 0;
                const multi = parseFloat(activeItem.quantity) > 1;
                return (
                  <div
                    key={person.id}
                    className="check-row"
                    onClick={() => togglePerson(activeItem.id, person.id)}
                  >
                    <div className={clsx("checkmark", { checked })}>{checked && "✓"}</div>
                    <span style={{ fontSize: 16, flex: 1 }}>{person.name}</span>
                    {checked && multi && (
                      <div className="qty-stepper" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={(e) => step(activeItem.id, person.id, -1, e)}
                          disabled={qty <= 1}
                        >
                          −
                        </button>
                        <span>{qty}</span>
                        <button
                          onClick={(e) => step(activeItem.id, person.id, 1, e)}
                          disabled={qty >= MAX_QTY}
                        >
                          +
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
              <button className="btn" style={{ marginTop: 8 }} onClick={() => setActiveItem(null)}>
                {t("assign.done")}
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
