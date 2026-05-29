import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import Skeleton from "../components/Skeleton";

export default function PeoplePage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [names, setNames] = useState<string[]>([]);
  const [initialized, setInitialized] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const { data: existingPeople, isLoading } = useQuery({
    queryKey: ["people", sessionId],
    queryFn: () => api.listPeople(sessionId!),
  });

  // Initialize from API — runs once when data arrives
  useEffect(() => {
    if (initialized || !existingPeople) return;
    setNames(existingPeople.length > 0 ? existingPeople.map((p) => p.name) : ["", ""]);
    setInitialized(true);
  }, [existingPeople, initialized]);

  function updateName(idx: number, value: string) {
    setNames((prev) => prev.map((n, i) => (i === idx ? value : n)));
  }

  function addPerson() {
    setNames((prev) => [...prev, ""]);
  }

  function removePerson(idx: number) {
    setNames((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleNext() {
    const filled = names.map((n) => n.trim()).filter(Boolean);
    if (filled.length < 1) {
      setError("Add at least one person");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.updatePeople(sessionId!, filled.map((name) => ({ name })));
      navigate(`/assign/${sessionId}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (isLoading && !initialized) {
    return (
      <div className="page">
        <h1>Who's at the table?</h1>
        <Skeleton count={2} height={48} />
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Who's at the table?</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>
        Enter everyone's name.
      </p>

      {names.map((name, idx) => (
        <div className="row" key={idx}>
          <input
            type="text"
            value={name}
            onChange={(e) => updateName(idx, e.target.value)}
            placeholder={`Person ${idx + 1}`}
            style={{ flex: 1 }}
            autoFocus={idx === names.length - 1 && idx > 0}
          />
          {names.length > 1 && (
            <button
              onClick={() => removePerson(idx)}
              style={{ background: "none", border: "none", color: "#e53935", fontSize: 20, cursor: "pointer" }}
            >
              ✕
            </button>
          )}
        </div>
      ))}

      <button className="btn btn-ghost" onClick={addPerson}>
        + Add person
      </button>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={saving} onClick={handleNext}>
        {saving ? "Saving…" : "Next: Assign Items →"}
      </button>
    </div>
  );
}
