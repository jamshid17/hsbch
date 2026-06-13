import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import Skeleton from "../components/Skeleton";

export default function PeoplePage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [names, setNames] = useState<string[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const { data: existingPeople, isLoading } = useQuery({
    queryKey: ["people", sessionId],
    queryFn: () => api.listPeople(sessionId!),
  });

  useEffect(() => {
    if (initialized || !existingPeople) return;
    setNames(existingPeople.length > 0 ? existingPeople.map((p) => p.name) : ["", ""]);
    setInitialized(true);
  }, [existingPeople, initialized]);

  function updateName(idx: number, value: string) {
    setNames((prev) => prev.map((n, i) => (i === idx ? value : n)));
  }
  function addPerson() { setNames((prev) => [...prev, ""]); }
  function removePerson(idx: number) { setNames((prev) => prev.filter((_, i) => i !== idx)); }

  async function handleNext() {
    const filled = names.map((n) => n.trim()).filter(Boolean);
    if (filled.length < 1) { setError(t("people.minOne")); return; }
    setSaving(true);
    setError("");
    try {
      await api.updatePeople(sessionId!, filled.map((name) => ({ name })));
      await queryClient.invalidateQueries({ queryKey: ["people", sessionId] });
      navigate(`/assign/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("people.failedSave"));
    } finally {
      setSaving(false);
    }
  }

  if (isLoading && !initialized) {
    return (
      <div className="page">
        <h1>{t("people.title")}</h1>
        <Skeleton count={2} height={48} />
      </div>
    );
  }

  return (
    <div className="page">
      <h1>{t("people.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("people.subtitle")}</p>

      {names.map((name, idx) => (
        <div className="row" key={idx}>
          <input
            type="text"
            value={name}
            onChange={(e) => updateName(idx, e.target.value)}
            placeholder={t("people.placeholder", { n: idx + 1 })}
            style={{ flex: 1 }}
            autoFocus={idx === names.length - 1 && idx > 0}
          />
          {names.length > 1 && (
            <button className="btn-remove" onClick={() => removePerson(idx)}>✕</button>
          )}
        </div>
      ))}

      <button className="btn btn-ghost" onClick={addPerson}>{t("people.addPerson")}</button>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saving} onClick={handleNext}>
        {saving ? t("people.saving") : t("people.next")}
      </button>
    </div>
  );
}
