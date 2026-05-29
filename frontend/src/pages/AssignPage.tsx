import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import { api, ItemOut, PersonOut } from "../api";
import Skeleton from "../components/Skeleton";
import { storage } from "../lib/storage";

export default function AssignPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [assignments, setAssignments] = useState<Record<string, Set<string>>>({});
  const [initialized, setInitialized] = useState(false);
  const [activeItem, setActiveItem] = useState<ItemOut | null>(null);
  const [error, setError] = useState("");

  const { data: items, isLoading: itemsLoading } = useQuery<ItemOut[]>({
    queryKey: ["items", sessionId],
    queryFn: () => api.listItems(sessionId!),
  });

  const { data: people, isLoading: peopleLoading } = useQuery<PersonOut[]>({
    queryKey: ["people", sessionId],
    queryFn: () => api.listPeople(sessionId!),
  });

  // Restore assignments from localStorage (matched by person name → current ID)
  useEffect(() => {
    if (!items || !people || initialized) return;

    const saved = storage.loadAssignments(sessionId!);
    const nameToId = Object.fromEntries(people.map((p) => [p.name, p.id]));

    const next: Record<string, Set<string>> = {};
    items.forEach((item) => {
      next[item.id] = new Set();
      saved?.[item.id]?.forEach((name) => {
        const id = nameToId[name];
        if (id) next[item.id].add(id);
      });
    });

    setAssignments(next);
    setInitialized(true);
  }, [items, people, initialized, sessionId]);

  // Persist assignments to localStorage on every change (store by person name)
  useEffect(() => {
    if (!people || !initialized) return;
    const idToName = Object.fromEntries(people.map((p) => [p.id, p.name]));
    const byName: Record<string, string[]> = {};
    Object.entries(assignments).forEach(([itemId, ids]) => {
      byName[itemId] = Array.from(ids)
        .map((id) => idToName[id])
        .filter(Boolean) as string[];
    });
    storage.saveAssignments(sessionId!, byName);
  }, [assignments, people, initialized, sessionId]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = Object.entries(assignments).map(([item_id, person_ids]) => ({
        item_id,
        person_ids: Array.from(person_ids),
      }));
      return api.updateAssignments(sessionId!, payload);
    },
    onSuccess: () => {
      storage.clearAssignments(sessionId!);
      navigate(`/summary/${sessionId}`);
    },
    onError: (e: unknown) =>
      setError(e instanceof Error ? e.message : "Failed to save"),
  });

  function togglePerson(itemId: string, personId: string) {
    setAssignments((prev) => {
      const set = new Set(prev[itemId]);
      set.has(personId) ? set.delete(personId) : set.add(personId);
      return { ...prev, [itemId]: set };
    });
  }

  function assignedCount(itemId: string) {
    return assignments[itemId]?.size ?? 0;
  }

  if (itemsLoading || peopleLoading) {
    return (
      <div className="page">
        <h1>Who had what?</h1>
        <Skeleton count={4} height={72} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1>Who had what?</h1>
        <button
          onClick={() => navigate(`/people/${sessionId}`)}
          style={{ background: "none", border: "none", color: "var(--link)", fontSize: 14, cursor: "pointer", padding: 0 }}
        >
          ← Edit people
        </button>
      </div>

      <p style={{ color: "var(--hint)", fontSize: 14 }}>
        Tap an item to select who ate it.
      </p>

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
                {item.quantity} {item.unit} × {item.price}
              </div>
            </div>
            <span className={clsx("badge", { "badge-warn": count === 0 })}>
              {count === 0 ? "unassigned" : `${count} person${count > 1 ? "s" : ""}`}
            </span>
          </motion.div>
        );
      })}

      {error && <p className="error">{error}</p>}

      <button
        className="btn"
        disabled={saveMutation.isPending}
        onClick={() => saveMutation.mutate()}
      >
        {saveMutation.isPending ? "Calculating…" : "Calculate →"}
      </button>

      {/* Animated bottom sheet */}
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
                Select everyone who shared this item.
              </p>
              {people?.map((person: PersonOut) => {
                const checked = assignments[activeItem.id]?.has(person.id) ?? false;
                return (
                  <motion.div
                    key={person.id}
                    className="check-row"
                    onClick={() => togglePerson(activeItem.id, person.id)}
                    whileTap={{ scale: 0.98 }}
                  >
                    <div className={clsx("checkmark", { checked })}>
                      {checked && "✓"}
                    </div>
                    <span style={{ fontSize: 16 }}>{person.name}</span>
                  </motion.div>
                );
              })}
              <button
                className="btn"
                style={{ marginTop: 8 }}
                onClick={() => setActiveItem(null)}
              >
                Done
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
