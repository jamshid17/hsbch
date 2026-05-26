import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ItemOut } from "../api";

interface EditableItem {
  id?: string;
  name: string;
  price: string;
  quantity: string;
  unit: string;
}

function emptyItem(): EditableItem {
  return { name: "", price: "", quantity: "1", unit: "pcs" };
}

export default function EditItemsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [items, setItems] = useState<EditableItem[]>([]);
  const [currency, setCurrency] = useState("");
  const [tax, setTax] = useState("0");
  const [tip, setTip] = useState("0");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [rawItems, session] = await Promise.all([
          api.listItems(sessionId!),
          fetch(`/api/sessions/${sessionId}`).then((r) => r.json()),
        ]);
        setItems(rawItems.map((i: ItemOut) => ({
          id: i.id,
          name: i.name,
          price: i.price,
          quantity: i.quantity,
          unit: i.unit,
        })));
        setCurrency(session.currency ?? "");
        setTax(session.tax ?? "0");
        setTip(session.tip ?? "0");
      } catch {
        setError("Failed to load items");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  function updateItem(idx: number, field: keyof EditableItem, value: string) {
    setItems((prev) => prev.map((item, i) => (i === idx ? { ...item, [field]: value } : item)));
  }

  function addItem() {
    setItems((prev) => [...prev, emptyItem()]);
  }

  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleNext() {
    setSaving(true);
    setError("");
    try {
      await api.updateItems(sessionId!, {
        items: items.map((i) => ({
          name: i.name,
          price: i.price,
          quantity: i.quantity,
          unit: i.unit,
        })),
        currency,
        tax,
        tip,
      });
      navigate(`/people/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div className="spinner">Loading items…</div>;

  return (
    <div className="page">
      <h1>Review Items</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>
        Fix any mistakes, then add tax and tip.
      </p>

      {items.map((item, idx) => (
        <div className="card" key={idx}>
          <div className="row">
            <div style={{ flex: 1 }}>
              <div className="label">Item name</div>
              <input
                type="text"
                value={item.name}
                onChange={(e) => updateItem(idx, "name", e.target.value)}
                placeholder="e.g. Burger"
              />
            </div>
            <button
              onClick={() => removeItem(idx)}
              style={{ background: "none", border: "none", color: "#e53935", fontSize: 20, cursor: "pointer", paddingTop: 18 }}
            >
              ✕
            </button>
          </div>
          <div className="row">
            <div style={{ flex: 1 }}>
              <div className="label">Price</div>
              <input
                type="number"
                value={item.price}
                onChange={(e) => updateItem(idx, "price", e.target.value)}
                placeholder="0.00"
                min="0"
                step="0.01"
              />
            </div>
            <div style={{ flex: 1 }}>
              <div className="label">Qty / Weight</div>
              <input
                type="number"
                value={item.quantity}
                onChange={(e) => updateItem(idx, "quantity", e.target.value)}
                placeholder="1"
                min="0"
                step="0.001"
              />
            </div>
            <div style={{ flex: 1 }}>
              <div className="label">Unit</div>
              <input
                type="text"
                value={item.unit}
                onChange={(e) => updateItem(idx, "unit", e.target.value)}
                placeholder="pcs"
              />
            </div>
          </div>
        </div>
      ))}

      <button className="btn btn-ghost" onClick={addItem}>
        + Add item
      </button>

      <div className="card">
        <div className="row">
          <div style={{ flex: 1 }}>
            <div className="label">Currency</div>
            <input
              type="text"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              placeholder="$"
            />
          </div>
          <div style={{ flex: 1 }}>
            <div className="label">Tax</div>
            <input
              type="number"
              value={tax}
              onChange={(e) => setTax(e.target.value)}
              placeholder="0.00"
              min="0"
              step="0.01"
            />
          </div>
          <div style={{ flex: 1 }}>
            <div className="label">Tip</div>
            <input
              type="number"
              value={tip}
              onChange={(e) => setTip(e.target.value)}
              placeholder="0.00"
              min="0"
              step="0.01"
            />
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saving || items.length === 0} onClick={handleNext}>
        {saving ? "Saving…" : "Next: Add People →"}
      </button>
    </div>
  );
}
