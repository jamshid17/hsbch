import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import Skeleton from "../components/Skeleton";
import { haptic } from "../telegram";

export default function PeoplePage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  // Arrived from the "split evenly" fork: names are the only thing still
  // missing, so this screen finishes the bill rather than handing off to a
  // per-item screen nobody is going to touch.
  const equalSplit = params.get("equal") === "1";
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
      await api.bulkSetPeople(sessionId!, filled.map((name) => ({ name })));
      await queryClient.invalidateQueries({ queryKey: ["people", sessionId] });
      if (equalSplit) {
        // No assignments at all, and everything left unclaimed handed to
        // everyone in equal parts — which, with nothing claimed, is the whole
        // bill split evenly. Same server-side path the host-live screen
        // offers when nobody picked anything.
        await api.setHostAssignments(sessionId!, [], true);
        haptic.success();
        navigate(`/summary/${sessionId}`);
        return;
      }
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
      <p style={{ color: "var(--hint)", fontSize: 14 }}>
        {equalSplit ? t("people.subtitleEqual") : t("people.subtitle")}
      </p>

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
        {saving
          ? t("people.saving")
          : equalSplit
            ? `⚖️ ${t("people.splitEqually")}`
            : t("people.next")}
      </button>
    </div>
  );
}
