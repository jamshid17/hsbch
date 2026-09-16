import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AdminUser } from "../api";
import DailyScansChart from "../components/DailyScansChart";

const FILTERS = [
  { key: "all", label: "Hammasi" },
  { key: "active", label: "Faol (7 kun)" },
  { key: "subscribed", label: "Obunachi" },
  { key: "exhausted", label: "Limiti tugagan" },
] as const;

function fmt(n: number) {
  return n.toLocaleString("ru-RU");
}

/** dd.mm.yyyy — the app has three UI languages, so month names are avoided. */
function fmtDate(iso: string) {
  const d = new Date(iso);
  return [d.getDate(), d.getMonth() + 1, d.getFullYear()]
    .map((v, i) => (i < 2 ? String(v).padStart(2, "0") : v))
    .join(".");
}

function relDate(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (days === 0) return "bugun";
  if (days === 1) return "kecha";
  if (days < 30) return `${days} kun oldin`;
  return fmtDate(iso);
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

function UserRow({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  const grant = useMutation({
    mutationFn: () => api.adminGrant(user.telegram_user_id, 30),
    onSuccess: invalidate,
  });
  const revoke = useMutation({
    mutationFn: () => api.adminRevoke(user.telegram_user_id),
    onSuccess: () => {
      setConfirming(false);
      invalidate();
    },
  });

  const name = user.first_name || (user.username ? `@${user.username}` : "Noma'lum");
  const until = user.subscription_until ? fmtDate(user.subscription_until) : null;

  return (
    <div className="user-row">
      <div className="user-main">
        <div className="user-name">
          {name}
          {user.is_subscribed && <span className="badge badge-ok">obuna</span>}
          {!user.is_subscribed && user.free_scans_used >= user.free_total_scans && (
            <span className="badge badge-warn">limit tugagan</span>
          )}
        </div>
        <div className="user-meta">
          {user.username ? `@${user.username} · ` : ""}
          <span className="mono">{user.telegram_user_id}</span>
        </div>
        <div className="user-meta">
          {user.scans_total} skan · bepul {user.free_scans_used}/{user.free_total_scans} ·{" "}
          {relDate(user.last_seen_at)}
          {user.is_subscribed && until ? ` · ${until} gacha` : ""}
        </div>
      </div>

      <div className="user-actions">
        {user.is_subscribed ? (
          confirming ? (
            <>
              <button
                className="btn-mini btn-mini-danger"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate()}
              >
                {revoke.isPending ? "…" : "Aniqmi?"}
              </button>
              <button className="btn-mini" onClick={() => setConfirming(false)}>
                Yo'q
              </button>
            </>
          ) : (
            <>
              <button
                className="btn-mini"
                disabled={grant.isPending}
                onClick={() => grant.mutate()}
              >
                {grant.isPending ? "…" : "+30 kun"}
              </button>
              <button className="btn-mini" onClick={() => setConfirming(true)}>
                Bekor
              </button>
            </>
          )
        ) : (
          <button
            className="btn-mini btn-mini-primary"
            disabled={grant.isPending}
            onClick={() => grant.mutate()}
          >
            {grant.isPending ? "…" : "✅ Obunani yoqish"}
          </button>
        )}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const [limit, setLimit] = useState(20);

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: () => api.getMe() });

  const { data: stats } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api.adminStats(),
    enabled: me?.is_admin === true,
    refetchInterval: 30000,
  });

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin", "users", search, filter, limit],
    queryFn: () => api.adminUsers({ search, filter, limit }),
    enabled: me?.is_admin === true,
  });

  // Non-admins never see this screen, even by typing the URL.
  if (me && !me.is_admin) {
    navigate("/", { replace: true });
    return null;
  }

  return (
    <div className="page">
      <h1>🛠 Admin</h1>

      <div className="stat-grid">
        <StatTile
          label="Foydalanuvchilar"
          value={fmt(stats?.users_total ?? 0)}
          hint={stats ? `bugun +${stats.users_today} · 7 kun +${stats.users_week}` : undefined}
        />
        <StatTile
          label="Obunachilar"
          value={fmt(stats?.subscribed ?? 0)}
          hint={stats ? `${stats.exhausted} ta limiti tugagan` : undefined}
        />
        <StatTile
          label="Skan · bugun"
          value={fmt(stats?.scans_today ?? 0)}
          hint={stats ? `7 kun: ${stats.scans_week}` : undefined}
        />
        <StatTile
          label="Skan · jami"
          value={fmt(stats?.scans_total ?? 0)}
          hint={stats ? `${stats.sessions_total} sessiya` : undefined}
        />
        <StatTile
          label="Bu oy tushum"
          value={`${fmt(stats?.revenue_month ?? 0)} so'm`}
          hint={stats ? `${stats.payments_month} ta to'lov` : undefined}
        />
        <StatTile
          label="Obuna narxi"
          value={`${fmt(stats?.price_uzs ?? 0)} so'm`}
          hint="30 kun"
        />
      </div>

      {stats && <DailyScansChart data={stats.daily_scans} />}

      <h2 className="section-title">Foydalanuvchilar</h2>

      <input
        type="text"
        placeholder="Ism, @username yoki ID bo'yicha qidirish"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="chip-row">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`chip ${filter === f.key ? "chip-active" : ""}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <p style={{ color: "var(--hint)", fontSize: 14 }}>Yuklanmoqda…</p>}

      {users && (
        <>
          <p style={{ color: "var(--hint)", fontSize: 13, margin: 0 }}>
            {users.total} ta topildi
          </p>
          {users.users.map((u) => (
            <UserRow key={u.telegram_user_id} user={u} />
          ))}
          {users.users.length < users.total && (
            <button className="btn btn-ghost" onClick={() => setLimit((l) => l + 20)}>
              Yana yuklash
            </button>
          )}
        </>
      )}
    </div>
  );
}
