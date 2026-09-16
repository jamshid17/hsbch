import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { fmtNum } from "../lib/format";

/** What each table actually holds, in the language of the app rather than
 * the schema — the point of this screen is to be readable without knowing
 * the model layer. */
const LABELS: Record<string, string> = {
  bot_users: "Foydalanuvchilar",
  sessions: "Sessiyalar",
  items: "Mahsulotlar",
  people: "Ishtirokchilar",
  assignments: "Tanlovlar",
  payments: "To'lovlar",
  receipt_scans: "Chek skanlari",
};

export default function AdminTables() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "tables"],
    queryFn: () => api.adminTables(),
  });

  if (isLoading && !data) {
    return <p className="muted-line">Yuklanmoqda…</p>;
  }
  if (!data) return null;

  return (
    <>
      <div className="card db-table">
        {data.tables.map((t) => (
          <div className="db-row" key={t.name}>
            <div className="db-row-main">
              <div className="db-row-label">{LABELS[t.name] ?? t.name}</div>
              <div className="db-row-name mono">{t.name}</div>
            </div>
            <div className="db-row-count mono">{fmtNum(t.rows)}</div>
          </div>
        ))}
      </div>

      <div className="stat-grid">
        <div className="stat-tile">
          <div className="stat-label">Baza hajmi</div>
          <div className="stat-value">{data.db_size}</div>
        </div>
        <div className="stat-tile">
          <div className="stat-label">PostgreSQL</div>
          <div className="stat-value">{data.pg_version}</div>
        </div>
      </div>
    </>
  );
}
