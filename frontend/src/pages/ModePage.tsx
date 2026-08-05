import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export default function ModePage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  const chooseMode = useMutation({
    mutationFn: (mode: "collaborative" | "host_assigns") =>
      api.updateSession(sessionId!, { assignment_mode: mode }).then(() => mode),
    onSuccess: (mode) => {
      navigate(mode === "collaborative" ? `/pick/${sessionId}` : `/people/${sessionId}`);
    },
    onError: (e: unknown) =>
      setError(e instanceof Error ? e.message : t("mode.failedSave")),
  });

  return (
    <div className="page">
      <h1>{t("mode.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("mode.subtitle")}</p>

      <div
        className="card"
        style={{ cursor: "pointer" }}
        onClick={() => chooseMode.mutate("collaborative")}
      >
        <div style={{ fontWeight: 600 }}>{t("mode.collaborative")}</div>
        <div style={{ color: "var(--hint)", fontSize: 13 }}>
          {t("mode.collaborativeDesc")}
        </div>
      </div>

      <div
        className="card"
        style={{ cursor: "pointer" }}
        onClick={() => chooseMode.mutate("host_assigns")}
      >
        <div style={{ fontWeight: 600 }}>{t("mode.hostAssigns")}</div>
        <div style={{ color: "var(--hint)", fontSize: 13 }}>
          {t("mode.hostAssignsDesc")}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {chooseMode.isPending && (
        <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("mode.saving")}</p>
      )}
    </div>
  );
}
