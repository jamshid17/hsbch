import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";

const CODE_LEN = 4;

export default function JoinPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [code, setCode] = useState(
    (params.get("code") || "").replace(/\D/g, "").slice(0, CODE_LEN)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const autoTried = useRef(false);

  async function join(rawCode: string) {
    const c = rawCode.replace(/\D/g, "");
    if (c.length !== CODE_LEN) return;
    setLoading(true);
    setError("");
    try {
      const session = await api.getSessionByCode(c);
      // A finished bill: just show the result, don't (re)join to pick items.
      if (session.status === "done") {
        navigate(`/summary/${session.id}`, { replace: true });
        return;
      }
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
        inputMode="numeric"
        pattern="[0-9]*"
        value={code}
        onChange={(e) =>
          setCode(e.target.value.replace(/\D/g, "").slice(0, CODE_LEN))
        }
        placeholder={t("join.placeholder")}
        maxLength={CODE_LEN}
        style={{
          fontSize: 32,
          letterSpacing: 12,
          textAlign: "center",
          fontWeight: 700,
        }}
      />

      {error && <p className="error">{error}</p>}

      <button
        className="btn"
        disabled={loading || code.length !== CODE_LEN}
        onClick={() => join(code)}
      >
        {loading ? t("join.joining") : t("join.joinBtn")}
      </button>
    </div>
  );
}
