import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ItemOut, PersonOut } from "../api";

export default function AssignPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [items, setItems] = useState<ItemOut[]>([]);
  const [people, setPeople] = useState<PersonOut[]>([]);
  // item_id → Set of person_ids
  const [assignments, setAssignments] = useState<Record<string, Set<string>>>({});
  const [activeItem, setActiveItem] = useState<ItemOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [i, p] = await Promise.all([
          api.listItems(sessionId!),
          api.listPeople(sessionId!),
        ]);
        setItems(i);
        setPeople(p);
        const init: Record<string, Set<string>> = {};
        i.forEach((item) => { init[item.id] = new Set(); });
        setAssignments(init);
      } catch {
        setError("Failed to load data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  function togglePerson(itemId: string, personId: string) {
    setAssignments((prev) => {
      const next = { ...prev };
      const set = new Set(next[itemId]);
      set.has(personId) ? set.delete(personId) : set.add(personId);
      next[itemId] = set;
      return next;
    });
  }

  function assignedCount(itemId: string) {
    return assignments[itemId]?.size ?? 0;
  }

  async function handleCalculate() {
    setSaving(true);
    setError("");
    try {
      const payload = Object.entries(assignments).map(([item_id, person_ids]) => ({
        item_id,
        person_ids: Array.from(person_ids),
      }));
      await api.updateAssignments(sessionId!, payload);
      navigate(`/summary/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="spinner">Loading…</div>;

  return (
    <div className="page">
      <h1>Who had what?</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>
        Tap an item to select who ate it.
      </p>

      {items.map((item) => (
        <div
          key={item.id}
          className="card"
          style={{ cursor: "pointer", flexDirection: "row", alignItems: "center" }}
          onClick={() => setActiveItem(item)}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600 }}>{item.name}</div>
            <div style={{ color: "var(--hint)", fontSize: 13 }}>
              {item.quantity} {item.unit} × ${item.price}
            </div>
          </div>
          <span className="badge">
            {assignedCount(item.id) === 0
              ? "unassigned"
              : `${assignedCount(item.id)} person${assignedCount(item.id) > 1 ? "s" : ""}`}
          </span>
        </div>
      ))}

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saving} onClick={handleCalculate}>
        {saving ? "Calculating…" : "Calculate →"}
      </button>

      {/* Bottom sheet */}
      {activeItem && (
        <div className="overlay" onClick={() => setActiveItem(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>{activeItem.name}</h3>
            <p style={{ color: "var(--hint)", fontSize: 13 }}>
              Select everyone who shared this item.
            </p>
            {people.map((person) => {
              const checked = assignments[activeItem.id]?.has(person.id) ?? false;
              return (
                <div
                  key={person.id}
                  className="check-row"
                  onClick={() => togglePerson(activeItem.id, person.id)}
                >
                  <div className={`checkmark${checked ? " checked" : ""}`}>
                    {checked && "✓"}
                  </div>
                  <span style={{ fontSize: 16 }}>{person.name}</span>
                </div>
              );
            })}
            <button className="btn" style={{ marginTop: 8 }} onClick={() => setActiveItem(null)}>
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
