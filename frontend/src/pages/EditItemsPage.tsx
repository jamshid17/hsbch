import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, ItemOut } from "../api";
import Skeleton from "../components/Skeleton";

interface EditableItem {
  id?: string;
  name: string;
  price: string;
  quantity: string;
  unit: string;
}

interface SessionBasic { currency: string; tax: string; tip: string; }

function emptyItem(): EditableItem {
  return { name: "", price: "", quantity: "1", unit: "pcs" };
}

export default function EditItemsPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [items, setItems] = useState<EditableItem[]>([]);
  const [currency, setCurrency] = useState("");
  const [tax, setTax] = useState("0");
  const [tip, setTip] = useState("0");
  const [initialized, setInitialized] = useState(false);
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery<{ rawItems: ItemOut[]; session: SessionBasic }>({
    queryKey: ["session-items", sessionId],
    queryFn: async () => {
      const [rawItems, session] = await Promise.all([
        api.listItems(sessionId!),
        fetch(`/api/sessions/${sessionId}`).then((r) => r.json()),
      ]);
      return { rawItems, session };
    },
  });

  useEffect(() => {
    if (!data || initialized) return;
    setItems(data.rawItems.map((i) => ({ id: i.id, name: i.name, price: i.price, quantity: i.quantity, unit: i.unit })));
    setCurrency(data.session.currency ?? "");
    setTax(data.session.tax ?? "0");
    setTip(data.session.tip ?? "0");
    setInitialized(true);
  }, [data, initialized]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateItems(sessionId!, {
        items: items.map((i) => ({ name: i.name, price: i.price, quantity: i.quantity, unit: i.unit })),
        currency, tax, tip,
      }),
    onSuccess: () => navigate(`/people/${sessionId}`),
    onError: (e: unknown) => setError(e instanceof Error ? e.message : t("edit.failedSave")),
  });

  function updateItem(idx: number, field: keyof EditableItem, value: string) {
    setItems((prev) => prev.map((item, i) => (i === idx ? { ...item, [field]: value } : item)));
  }
  function addItem() { setItems((prev) => [...prev, emptyItem()]); }
  function removeItem(idx: number) { setItems((prev) => prev.filter((_, i) => i !== idx)); }

  if (isLoading && !initialized) {
    return (
      <div className="page">
        <h1>{t("edit.title")}</h1>
        <Skeleton count={3} height={108} />
      </div>
    );
  }

  return (
    <div className="page">
      <h1>{t("edit.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("edit.subtitle")}</p>

      <AnimatePresence initial={false}>
        {items.map((item, idx) => (
          <motion.div key={idx} className="card"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0, padding: 0 }}
            transition={{ duration: 0.18 }}
          >
            <div className="row">
              <div style={{ flex: 1 }}>
                <div className="label">{t("edit.itemName")}</div>
                <input type="text" value={item.name} onChange={(e) => updateItem(idx, "name", e.target.value)} placeholder={t("edit.itemPlaceholder")} />
              </div>
              <button onClick={() => removeItem(idx)} style={{ background: "none", border: "none", color: "#e53935", fontSize: 20, cursor: "pointer", paddingTop: 18, flexShrink: 0 }}>✕</button>
            </div>
            <div className="row">
              <div style={{ flex: 1 }}>
                <div className="label">{t("edit.price")}</div>
                <input type="number" value={item.price} onChange={(e) => updateItem(idx, "price", e.target.value)} placeholder="0.00" min="0" step="0.01" />
              </div>
              <div style={{ flex: 1 }}>
                <div className="label">{t("edit.qty")}</div>
                <input type="number" value={item.quantity} onChange={(e) => updateItem(idx, "quantity", e.target.value)} placeholder="1" min="0" step="0.001" />
              </div>
              <div style={{ flex: 1 }}>
                <div className="label">{t("edit.unit")}</div>
                <input type="text" value={item.unit} onChange={(e) => updateItem(idx, "unit", e.target.value)} placeholder="pcs" />
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      <button className="btn btn-ghost" onClick={addItem}>{t("edit.addItem")}</button>

      <div className="card">
        <div className="row">
          <div style={{ flex: 1 }}>
            <div className="label">{t("edit.currency")}</div>
            <input type="text" value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="$" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="label">{t("edit.tax")}</div>
            <input type="number" value={tax} onChange={(e) => setTax(e.target.value)} placeholder="0.00" min="0" step="0.01" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="label">{t("edit.tip")}</div>
            <input type="number" value={tip} onChange={(e) => setTip(e.target.value)} placeholder="0.00" min="0" step="0.01" />
          </div>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saveMutation.isPending || items.length === 0} onClick={() => saveMutation.mutate()}>
        {saveMutation.isPending ? t("edit.saving") : t("edit.next")}
      </button>
    </div>
  );
}
