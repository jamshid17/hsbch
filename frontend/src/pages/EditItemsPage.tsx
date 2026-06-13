import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { api, ItemOut } from "../api";
import Skeleton from "../components/Skeleton";
import { clampQty, fmtQty, MAX_QTY } from "../lib/format";

interface EditableItem {
  id?: string;
  name: string;
  price: string;
  quantity: string;
  unit: string;
}

interface SessionBasic { currency: string; tax: string; tip: string; title?: string; }

function emptyItem(): EditableItem {
  return { name: "", price: "", quantity: "1", unit: "pcs" };
}

/** Tax/tip input that can be entered as a fixed amount or as a % of subtotal. */
function AmountPercentField({
  label,
  amountLabel,
  mode,
  onMode,
  amount,
  onAmount,
  pct,
  onPct,
  computed,
  currency,
}: {
  label: string;
  amountLabel: string;
  mode: "amount" | "pct";
  onMode: (m: "amount" | "pct") => void;
  amount: string;
  onAmount: (v: string) => void;
  pct: string;
  onPct: (v: string) => void;
  computed: number;
  currency: string;
}) {
  return (
    <div>
      <div
        className="row"
        style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}
      >
        <div className="label" style={{ margin: 0 }}>{label}</div>
        <div className="seg">
          <button
            type="button"
            className={mode === "amount" ? "seg-btn active" : "seg-btn"}
            onClick={() => onMode("amount")}
          >
            {amountLabel}
          </button>
          <button
            type="button"
            className={mode === "pct" ? "seg-btn active" : "seg-btn"}
            onClick={() => onMode("pct")}
          >
            %
          </button>
        </div>
      </div>

      {mode === "amount" ? (
        <input
          type="number"
          inputMode="decimal"
          value={amount}
          onChange={(e) => onAmount(e.target.value)}
          placeholder="0.00"
          min="0"
          step="0.01"
        />
      ) : (
        <>
          <input
            type="number"
            inputMode="decimal"
            value={pct}
            onChange={(e) => onPct(e.target.value)}
            placeholder="12"
            min="0"
            step="0.1"
          />
          <div style={{ color: "var(--hint)", fontSize: 13, marginTop: 6 }}>
            = {currency}
            {computed.toFixed(2)}
          </div>
        </>
      )}
    </div>
  );
}

export default function EditItemsPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [items, setItems] = useState<EditableItem[]>([]);
  const [currency, setCurrency] = useState("");
  const [tax, setTax] = useState("0");
  const [tip, setTip] = useState("0");
  const [taxMode, setTaxMode] = useState<"amount" | "pct">("amount");
  const [tipMode, setTipMode] = useState<"amount" | "pct">("amount");
  const [taxPct, setTaxPct] = useState("");
  const [tipPct, setTipPct] = useState("");
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
    setItems(data.rawItems.map((i) => ({ id: i.id, name: i.name, price: i.price, quantity: clampQty(fmtQty(i.quantity)), unit: i.unit })));
    setCurrency(data.session.currency ?? "");
    setTax(data.session.tax ?? "0");
    setTip(data.session.tip ?? "0");
    setTitle(data.session.title ?? "");
    setInitialized(true);
  }, [data, initialized]);

  const subtotal = items.reduce(
    (sum, i) => sum + (parseFloat(i.price) || 0) * (parseFloat(i.quantity) || 0),
    0
  );
  const effectiveTax =
    taxMode === "pct" ? (subtotal * (parseFloat(taxPct) || 0)) / 100 : parseFloat(tax) || 0;
  const effectiveTip =
    tipMode === "pct" ? (subtotal * (parseFloat(tipPct) || 0)) / 100 : parseFloat(tip) || 0;

  const saveMutation = useMutation({
    mutationFn: () => {
      // Sanitize: coerce blank price/qty to valid numbers (avoids the backend
      // decimal-parsing error) and drop empty junk rows (e.g. from scanning a
      // non-receipt photo).
      const cleanItems = items
        .map((i) => ({
          name: i.name.trim(),
          price: i.price.trim() === "" ? "0" : i.price,
          quantity: i.quantity.trim() === "" ? "1" : i.quantity,
          unit: i.unit.trim() || "pcs",
        }))
        .filter((i) => i.name !== "" || parseFloat(i.price) > 0);

      if (cleanItems.length === 0) {
        return Promise.reject(new Error(t("edit.needItem")));
      }

      return api.updateItems(sessionId!, {
        items: cleanItems,
        currency,
        tax: effectiveTax.toFixed(2),
        tip: effectiveTip.toFixed(2),
      });
    },
    onSuccess: () => navigate(`/host/${sessionId}`),
    onError: (e: unknown) => setError(e instanceof Error ? e.message : t("edit.failedSave")),
  });

  function updateItem(idx: number, field: keyof EditableItem, value: string) {
    const v = field === "quantity" ? clampQty(value) : value;
    setItems((prev) => prev.map((item, i) => (i === idx ? { ...item, [field]: v } : item)));
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

      <div className="card" style={{ gap: 4 }}>
        <div className="label">{t("edit.sessionTitle")}</div>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => { if (sessionId) api.updateSession(sessionId, { title }); }}
          placeholder={t("edit.titlePlaceholder")}
          style={{ fontWeight: 600, fontSize: 16 }}
        />
      </div>

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
              <button className="btn-remove" onClick={() => removeItem(idx)}>✕</button>
            </div>
            <div className="item-fields">
              <div>
                <div className="label">{t("edit.price")}</div>
                <input type="number" value={item.price} onChange={(e) => updateItem(idx, "price", e.target.value)} placeholder="0.00" min="0" step="0.01" />
              </div>
              <div>
                <div className="label">{t("edit.qty")}</div>
                <input type="number" value={item.quantity} onChange={(e) => updateItem(idx, "quantity", e.target.value)} placeholder="1" min="0" max={MAX_QTY} step="0.001" />
              </div>
              <div>
                <div className="label">{t("edit.unit")}</div>
                <input type="text" value={item.unit} onChange={(e) => updateItem(idx, "unit", e.target.value)} placeholder="pcs" />
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>

      <button className="btn btn-ghost" onClick={addItem}>{t("edit.addItem")}</button>

      <div className="card">
        <div>
          <div className="label">{t("edit.currency")}</div>
          <input type="text" value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="$" />
        </div>

        <AmountPercentField
          label={t("edit.tax")}
          amountLabel={t("edit.modeAmount")}
          mode={taxMode}
          onMode={setTaxMode}
          amount={tax}
          onAmount={setTax}
          pct={taxPct}
          onPct={setTaxPct}
          computed={effectiveTax}
          currency={currency}
        />

        <AmountPercentField
          label={t("edit.tip")}
          amountLabel={t("edit.modeAmount")}
          mode={tipMode}
          onMode={setTipMode}
          amount={tip}
          onAmount={setTip}
          pct={tipPct}
          onPct={setTipPct}
          computed={effectiveTip}
          currency={currency}
        />
      </div>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saveMutation.isPending || items.length === 0} onClick={() => saveMutation.mutate()}>
        {saveMutation.isPending ? t("edit.saving") : t("edit.next")}
      </button>
    </div>
  );
}
