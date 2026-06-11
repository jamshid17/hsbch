import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export default function JoinPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [code, setCode] = useState((params.get("code") || "").toUpperCase());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const autoTried = useRef(false);

  async function join(rawCode: string) {
    const c = rawCode.trim().toUpperCase();
    if (c.length < 4) return;
    setLoading(true);
    setError("");
    try {
      const session = await api.getSessionByCode(c);
      await api.joinSession(session.id);
      navigate(`/pick/${session.id}`, { replace: true });
    } catch {
      setError(t("join.notFound"));
      setLoading(false);
    }
  }

  // Auto-join when arriving via a deep link with ?code=.
  useEffect(() => {
    const c = params.get("code");
    if (c && !autoTried.current) {
      autoTried.current = true;
      join(c);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page">
      <h1>{t("join.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("join.subtitle")}</p>

      <input
        type="text"
        value={code}
        onChange={(e) => setCode(e.target.value.toUpperCase())}
        placeholder={t("join.placeholder")}
        maxLength={8}
        autoCapitalize="characters"
        style={{
          fontSize: 28,
          letterSpacing: 6,
          textAlign: "center",
          fontWeight: 700,
          textTransform: "uppercase",
        }}
      />

      {error && <p className="error">{error}</p>}

      <button
        className="btn"
        disabled={loading || code.trim().length < 4}
        onClick={() => join(code)}
      >
        {loading ? t("join.joining") : t("join.joinBtn")}
      </button>
    </div>
  );
}
