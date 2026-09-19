import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, SessionOut } from "../api";
import { haptic } from "../telegram";

const CODE_LEN = 4;

/** A deep link carries a session id; a person at the table types four digits. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function JoinPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const token = (params.get("code") || "").trim();
  // Only a typed code belongs in the input; a session id from a deep link is
  // resolved below without ever being shown.
  const [code, setCode] = useState(
    UUID.test(token) ? "" : token.replace(/\D/g, "").slice(0, CODE_LEN)
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const autoTried = useRef(false);

  /** A finished bill is a result to read, not one to join and pick from. */
  async function open(session: SessionOut) {
    if (session.status === "done") {
      navigate(`/summary/${session.id}`, { replace: true });
      return;
    }
    await api.joinSession(session.id);
    haptic.success();
    navigate(`/pick/${session.id}`, { replace: true });
  }

  async function resolve(raw: string) {
    const value = raw.trim();
    setLoading(true);
    setError("");
    try {
      await open(
        UUID.test(value)
          ? await api.getSession(value)
          : await api.getSessionByCode(value.replace(/\D/g, ""))
      );
    } catch {
      haptic.error();
      setError(t("join.notFound"));
      setLoading(false);
    }
  }

  function joinByCode() {
    if (code.length === CODE_LEN) resolve(code);
  }

  // Arriving via a deep link: resolve it without making them press anything.
  useEffect(() => {
    if (!token || autoTried.current) return;
    autoTried.current = true;
    if (UUID.test(token) || token.replace(/\D/g, "").length === CODE_LEN) {
      resolve(token);
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
        aria-label={t("join.title")}
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
        onClick={joinByCode}
      >
        {loading ? t("join.joining") : t("join.joinBtn")}
      </button>
    </div>
  );
}
