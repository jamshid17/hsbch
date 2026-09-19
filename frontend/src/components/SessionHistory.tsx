import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api, SessionBrief } from "../api";
import { fmtDate } from "../lib/format";
import { haptic } from "../telegram";

function fmt(value: string): string {
  const num = parseFloat(value);
  return num.toLocaleString("ru-RU", {
    minimumFractionDigits: num % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  });
}

/**
 * Where an unfinished bill left off.
 *
 * A finished one is a result to read. An open one is a screen someone walked
 * away from, and which screen depends on who they were in it — sending
 * everyone to the summary would show a split that isn't decided yet.
 */
function routeFor(s: SessionBrief): string {
  if (s.status === "done") return `/summary/${s.id}`;
  if (!s.is_host) return `/pick/${s.id}`;
  return s.assignment_mode === "collaborative"
    ? `/host/${s.id}`
    : `/assign/${s.id}`;
}

/**
 * The bills this person has been part of.
 *
 * Until now leaving the summary lost a bill for good unless its four-digit
 * code was still in someone's head — which is exactly the thing nobody
 * writes down.
 */
export default function SessionHistory() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: sessions } = useQuery({
    queryKey: ["my-sessions"],
    queryFn: () => api.listMySessions(),
  });

  // Nothing to show on a first visit, and an empty heading is worse than no
  // heading at all.
  if (!sessions || sessions.length === 0) return null;

  function open(s: SessionBrief) {
    haptic.select();
    navigate(routeFor(s));
  }

  return (
    <>
      <h2 style={{ marginTop: 8 }}>{t("history.title")}</h2>

      {sessions.map((s) => (
        <div
          key={s.id}
          className="card tappable history-row"
          role="button"
          tabIndex={0}
          onClick={() => open(s)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              open(s);
            }
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="history-name">{s.title || t("history.untitled")}</div>
            <div className="history-meta">
              {t("history.people", { count: s.people_count })} ·{" "}
              {fmtDate(s.created_at)}
              {s.status !== "done" && ` · ${t("history.open")}`}
            </div>
          </div>
          <div className="history-total">
            {fmt(s.total)} {s.currency}
          </div>
        </div>
      ))}
    </>
  );
}
