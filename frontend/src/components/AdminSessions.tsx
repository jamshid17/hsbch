import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { AdminSession } from "../api";
import { fmtDateTime, fmtNum } from "../lib/format";

const STATUS: Record<string, { label: string; cls: string }> = {
  editing: { label: "tahrirlash", cls: "badge-warn" },
  assigning: { label: "tanlash", cls: "badge-admin" },
  done: { label: "yakunlangan", cls: "badge-ok" },
};

function host(s: AdminSession) {
  const { first_name, username, telegram_user_id } = s.host;
  return first_name || (username ? `@${username}` : `ID ${telegram_user_id}`);
}

export default function AdminSessions() {
  const [limit, setLimit] = useState(20);
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "sessions", limit],
    queryFn: () => api.adminSessions({ limit }),
  });

  if (isLoading && !data) {
    return <p className="muted-line">Yuklanmoqda…</p>;
  }
  if (!data) return null;

  if (data.total === 0) {
    return <p className="notice">Hali birorta sessiya yo'q.</p>;
  }

  return (
    <>
      <p className="muted-line">{fmtNum(data.total)} ta sessiya</p>

      {data.sessions.map((s) => {
        const status = STATUS[s.status] ?? { label: s.status, cls: "badge-admin" };
        return (
          <div className="user-row" key={s.id}>
            <div className="user-main">
              <div className="user-name">
                <span className="mono">{s.code}</span>
                <span className={`badge ${status.cls}`}>{status.label}</span>
                <span className="badge badge-admin">
                  {s.assignment_mode === "collaborative" ? "birgalikda" : "host taqsimlaydi"}
                </span>
              </div>
              {s.title && <div className="user-meta">{s.title}</div>}
              <div className="user-meta">
                {s.items_count} mahsulot · {s.people_count} kishi
                {s.currency ? ` · ${s.currency}` : ""}
              </div>
              <div className="user-meta">
                {host(s)} · {fmtDateTime(s.created_at)}
              </div>
            </div>
          </div>
        );
      })}

      {data.sessions.length < data.total && (
        <button className="btn btn-ghost" onClick={() => setLimit((l) => l + 20)}>
          Yana yuklash
        </button>
      )}
    </>
  );
}
