import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, SummaryOut } from "../api";
import { tg } from "../telegram";

export default function SummaryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<SummaryOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getSummary(sessionId!)
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [sessionId]);

  function handleShare() {
    if (!summary) return;
    const lines = summary.people.map(
      (p) => `${p.name}: ${summary.currency}${p.total}`
    );
    const text = `Bill split:\n${lines.join("\n")}`;
    tg.switchInlineQuery?.(text);
  }

  if (loading) return <div className="spinner">Calculating…</div>;
  if (error) return <div className="page"><p className="error">{error}</p></div>;
  if (!summary) return null;

  return (
    <div className="page">
      <h1>Who owes what</h1>

      {summary.people.map((person) => (
        <div className="card" key={person.person_id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span style={{ fontWeight: 700, fontSize: 17 }}>{person.name}</span>
            <span style={{ fontWeight: 700, fontSize: 17 }}>
              {summary.currency}{person.total}
            </span>
          </div>

          <div style={{ borderTop: "1px solid var(--secondary-bg)", paddingTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
            {person.items.map((item, idx) => (
              <div className="row" key={idx} style={{ justifyContent: "space-between" }}>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>{item.name}</span>
                <span style={{ color: "var(--hint)", fontSize: 14 }}>
                  {summary.currency}{item.share}
                </span>
              </div>
            ))}
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span style={{ color: "var(--hint)", fontSize: 13 }}>Tax + tip share</span>
              <span style={{ color: "var(--hint)", fontSize: 13 }}>
                {summary.currency}{person.extras}
              </span>
            </div>
          </div>
        </div>
      ))}

      <button className="btn btn-ghost" onClick={handleShare}>
        Share results
      </button>

      <button
        className="btn"
        style={{ background: "var(--secondary-bg)", color: "var(--text)" }}
        onClick={() => navigate("/")}
      >
        Split another bill
      </button>
    </div>
  );
}
