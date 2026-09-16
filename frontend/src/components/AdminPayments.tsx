import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { AdminPayment } from "../api";
import { fmtDateTime, fmtNum } from "../lib/format";

const METHOD_LABEL: Record<string, string> = {
  card: "Karta",
  manual: "Qo'lda",
  stars: "Stars",
};

/** Who the payment belongs to — the id is the only field guaranteed to be
 * there, since someone can be paid for before they ever open the app. */
function payer(p: AdminPayment) {
  const { first_name, username, telegram_user_id } = p.user;
  return first_name || (username ? `@${username}` : `ID ${telegram_user_id}`);
}

export default function AdminPayments() {
  const [limit, setLimit] = useState(20);
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "payments", limit],
    queryFn: () => api.adminPayments({ limit }),
  });

  if (isLoading && !data) {
    return <p className="muted-line">Yuklanmoqda…</p>;
  }
  if (!data) return null;

  if (data.total === 0) {
    return <p className="notice">Hali birorta to'lov yo'q.</p>;
  }

  return (
    <>
      <div className="stat-grid">
        <StatLine label="To'lovlar" value={fmtNum(data.total)} />
        <StatLine label="Jami tushum" value={`${fmtNum(data.revenue_total)} so'm`} />
      </div>

      {data.payments.map((p) => (
        <div className="user-row" key={p.id}>
          <div className="user-main">
            <div className="user-name">
              {fmtNum(p.amount)} {p.currency}
              <span className="badge badge-admin">
                {METHOD_LABEL[p.method] ?? p.method}
              </span>
              {p.refunded_at && <span className="badge badge-warn">qaytarilgan</span>}
            </div>
            <div className="user-meta">
              {payer(p)} · <span className="mono">{p.user.telegram_user_id}</span>
            </div>
            <div className="user-meta">
              {fmtDateTime(p.created_at)}
              {p.granted_by ? ` · admin ${p.granted_by}` : ""}
            </div>
            {p.note && <div className="user-meta">💬 {p.note}</div>}
          </div>
        </div>
      ))}

      {data.payments.length < data.total && (
        <button className="btn btn-ghost" onClick={() => setLimit((l) => l + 20)}>
          Yana yuklash
        </button>
      )}
    </>
  );
}

function StatLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
