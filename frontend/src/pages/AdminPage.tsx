import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AdminUser } from "../api";
import DailyScansChart from "../components/DailyScansChart";
import ConfirmSheet from "../components/ConfirmSheet";
import AddAdminForm from "../components/AddAdminForm";
import AdminPayments from "../components/AdminPayments";
import AdminSessions from "../components/AdminSessions";
import AdminTables from "../components/AdminTables";
import BlockSheet from "../components/BlockSheet";
import PermissionsSheet from "../components/PermissionsSheet";
import { can, permissionLabel } from "../lib/permissions";
import { fmtDate, fmtDateTime, fmtNum, relDate } from "../lib/format";

const FILTERS = [
  { key: "all", label: "Hammasi" },
  { key: "active", label: "Faol (7 kun)" },
  { key: "admins", label: "Adminlar" },
  // Meaningless while the paid tier is off — filtered out in the UI below.
  { key: "subscribed", label: "Obunachi", paidOnly: true },
  { key: "exhausted", label: "Limiti tugagan", paidOnly: true },
] as const;

// Each tab past the overview needs its own grant. The backend answers 404 on
// those endpoints without it, so hiding the tab shows the same truth rather
// than a lock the person can press.
const TABS = [
  { key: "overview", label: "📊 Umumiy" },
  { key: "payments", label: "💳 To'lovlar", needs: "payments" },
  { key: "sessions", label: "🧾 Sessiyalar", needs: "sessions" },
  { key: "tables", label: "🗄 Baza", needs: "tables" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

type PendingAction =
  | "grant"
  | "extend"
  | "revoke"
  | "promote"
  | "demote"
  | "block"
  | "unblock"
  | "permissions";

function UserRow({
  user,
  paid,
  meId,
  myPermissions,
}: {
  user: AdminUser;
  paid: boolean;
  meId?: number;
  /** What the admin looking at this row holds. */
  myPermissions: string[];
}) {
  const queryClient = useQueryClient();
  // Every write goes through a confirmation sheet — these rows sit close
  // together on a phone and all three actions change what someone paid for.
  const [pending, setPending] = useState<PendingAction | null>(null);
  // Payment history is collapsed by default and only fetched once opened —
  // a list of 50 users shouldn't fire 50 requests nobody asked for.
  const [showPayments, setShowPayments] = useState(false);

  const holds = (key: Parameters<typeof can>[1]) =>
    myPermissions.includes(key);

  const payments = useQuery({
    queryKey: ["admin", "user-payments", user.telegram_user_id],
    queryFn: () => api.adminUserPayments(user.telegram_user_id),
    enabled: showPayments && holds("payments"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
  };

  const grant = useMutation({
    mutationFn: () => api.adminGrant(user.telegram_user_id, 30),
    onSuccess: () => {
      setPending(null);
      invalidate();
    },
  });
  const revoke = useMutation({
    mutationFn: () => api.adminRevoke(user.telegram_user_id),
    onSuccess: () => {
      setPending(null);
      invalidate();
    },
  });
  const setAdmin = useMutation({
    mutationFn: (isAdmin: boolean) =>
      api.adminSetAdmin(user.telegram_user_id, isAdmin),
    onSuccess: () => {
      setPending(null);
      invalidate();
      // The current user's own panel access can change here, so /me is stale.
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
  const setPermissions = useMutation({
    mutationFn: (permissions: string[]) =>
      api.adminSetPermissions(user.telegram_user_id, permissions),
    onSuccess: () => {
      setPending(null);
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
  const block = useMutation({
    mutationFn: (reason: string) =>
      api.adminBlock(user.telegram_user_id, reason),
    onSuccess: () => {
      setPending(null);
      invalidate();
    },
  });
  const unblock = useMutation({
    mutationFn: () => api.adminUnblock(user.telegram_user_id),
    onSuccess: () => {
      setPending(null);
      invalidate();
    },
  });

  // Managing admins is its own grant. On top of it: the owner account has no
  // in-app toggle at all, and nobody can demote themselves out of the screen
  // they're standing on.
  const isSelf = user.telegram_user_id === meId;
  const canToggleAdmin =
    holds("manage_admins") && !user.is_super_admin && !(user.is_admin && isSelf);
  // Same two exceptions, and one more: an admin is only blockable by someone
  // who could have demoted them — the backend refuses otherwise.
  const canBlock =
    holds("block_users") &&
    !user.is_super_admin &&
    !isSelf &&
    (!user.is_admin || holds("manage_admins"));

  const name =
    user.first_name || (user.username ? `@${user.username}` : "Noma'lum");
  const until = user.subscription_until
    ? fmtDate(user.subscription_until)
    : null;

  return (
    <div className="user-row">
      <div className="user-main">
        <div className="user-name">
          {name}
          {user.is_admin && (
            <span
              className={`badge ${
                user.is_super_admin ? "badge-super" : "badge-admin"
              }`}
            >
              {user.is_super_admin ? "asosiy admin" : "admin"}
            </span>
          )}
          {user.is_blocked && <span className="badge badge-danger">bloklangan</span>}
          {paid && user.is_subscribed && (
            <span className="badge badge-ok">obuna</span>
          )}
          {paid &&
            !user.is_subscribed &&
            user.free_scans_used >= user.free_total_scans && (
              <span className="badge badge-warn">limit tugagan</span>
            )}
        </div>
        <div className="user-meta">
          {user.username ? `@${user.username} · ` : ""}
          <span className="mono">{user.telegram_user_id}</span>
        </div>
        <div className="user-meta">
          {user.scans_total} skan ·{" "}
          {paid
            ? `bepul ${user.free_scans_used}/${user.free_total_scans} · `
            : ""}
          {relDate(user.last_seen_at)}
          {paid && user.is_subscribed && until ? ` · ${until} gacha` : ""}
        </div>

        {user.is_blocked && (
          <div className="user-meta">
            🚫 Bloklangan{user.blocked_at ? ` · ${fmtDate(user.blocked_at)}` : ""}
            {user.block_reason ? ` · ${user.block_reason}` : ""}
          </div>
        )}

        {/* What an admin may do, spelled out — otherwise the only way to
            know is to open the editor one row at a time. */}
        {user.is_admin && !user.is_super_admin && (
          <div className="user-meta">
            🔑{" "}
            {user.permissions.length
              ? user.permissions.map(permissionLabel).join(", ")
              : "faqat umumiy ko'rish"}
          </div>
        )}

        {holds("payments") && (
          <button
            className="link-toggle"
            onClick={() => setShowPayments((v) => !v)}
            aria-expanded={showPayments}
          >
            To'lovlar tarixi {showPayments ? "▴" : "▾"}
          </button>
        )}

        {showPayments && (
          <div className="user-payments">
            {payments.isLoading && (
              <span className="user-meta">Yuklanmoqda…</span>
            )}
            {payments.data?.length === 0 && (
              <span className="user-meta">To'lov qilinmagan.</span>
            )}
            {payments.data?.map((p) => (
              <div className="user-meta" key={p.id}>
                {fmtNum(p.amount)} {p.currency} · {p.method} ·{" "}
                {fmtDateTime(p.created_at)}
                {p.note ? ` · ${p.note}` : ""}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="user-actions">
        {paid &&
          holds("subscriptions") &&
          (user.is_subscribed ? (
            <>
              <button className="btn-mini" onClick={() => setPending("extend")}>
                +30 kun
              </button>
              <button
                className="btn-mini btn-mini-danger"
                onClick={() => setPending("revoke")}
              >
                To'xtatish
              </button>
            </>
          ) : (
            <button
              className="btn-mini btn-mini-primary"
              onClick={() => setPending("grant")}
            >
              ✅ Obunani yoqish
            </button>
          ))}

        {canToggleAdmin &&
          (user.is_admin ? (
            <button
              className="btn-mini btn-mini-danger"
              onClick={() => setPending("demote")}
            >
              Adminlikdan olish
            </button>
          ) : (
            <button className="btn-mini" onClick={() => setPending("promote")}>
              🛠 Admin qilish
            </button>
          ))}

        {holds("manage_admins") && user.is_admin && !user.is_super_admin && (
          <button className="btn-mini" onClick={() => setPending("permissions")}>
            🔑 Huquqlar
          </button>
        )}

        {canBlock &&
          (user.is_blocked ? (
            <button
              className="btn-mini btn-mini-primary"
              onClick={() => setPending("unblock")}
            >
              Blokdan chiqarish
            </button>
          ) : (
            <button
              className="btn-mini btn-mini-danger"
              onClick={() => setPending("block")}
            >
              🚫 Bloklash
            </button>
          ))}
      </div>

      {pending === "grant" && (
        <ConfirmSheet
          title="Obunani yoqish"
          body={`${name} (${user.telegram_user_id}) uchun 30 kunlik obuna yoqiladi va to'lov yozib qo'yiladi. To'lov haqiqatan kelganini tekshirdingizmi?`}
          confirmLabel="Ha, yoqish"
          busy={grant.isPending}
          onConfirm={() => grant.mutate()}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "extend" && (
        <ConfirmSheet
          title="Obunani uzaytirish"
          body={`${name} uchun yana 30 kun qo'shiladi${
            until ? ` — ${until} dan keyin davom etadi` : ""
          }. Yangi to'lov yozib qo'yiladi.`}
          confirmLabel="Ha, +30 kun"
          busy={grant.isPending}
          onConfirm={() => grant.mutate()}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "promote" && (
        <ConfirmSheet
          title="Admin qilish"
          body={`${name} (${user.telegram_user_id}) admin panelning "Umumiy" tabini ochadi: statistika va foydalanuvchilar ro'yxati — ko'rish uchun. Obuna berish, bloklash, to'lovlar va boshqalar uchun keyin "🔑 Huquqlar" dan alohida ruxsat berasiz.`}
          confirmLabel="Ha, admin qilish"
          busy={setAdmin.isPending}
          onConfirm={() => setAdmin.mutate(true)}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "demote" && (
        <ConfirmSheet
          title="Adminlikdan olish"
          body={`${name} ning admin huquqlari darhol olib tashlanadi va u admin panelni boshqa ocholmaydi. Berilgan huquqlar ham tozalanadi — keyin qayta admin qilsangiz, ularni yana berishingiz kerak.`}
          confirmLabel="Ha, olib tashlash"
          danger
          busy={setAdmin.isPending}
          onConfirm={() => setAdmin.mutate(false)}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "permissions" && (
        <PermissionsSheet
          name={name}
          current={user.permissions}
          mine={myPermissions}
          busy={setPermissions.isPending}
          error={
            setPermissions.isError
              ? (setPermissions.error as Error).message
              : undefined
          }
          onSave={(perms) => setPermissions.mutate(perms)}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "block" && (
        <BlockSheet
          name={name}
          userId={user.telegram_user_id}
          busy={block.isPending}
          error={block.isError ? (block.error as Error).message : undefined}
          onConfirm={(reason) => block.mutate(reason)}
          onCancel={() => setPending(null)}
        />
      )}

      {pending === "unblock" && (
        <ConfirmSheet
          title="Blokdan chiqarish"
          body={`${name} yana ilovadan va botdan foydalana oladi. Hammasi bloklashdan oldingi holida.`}
          confirmLabel="Ha, chiqarish"
          busy={unblock.isPending}
          onConfirm={() => unblock.mutate()}
          onCancel={() => setPending(null)}
        />
      )}

      {setAdmin.isError && (
        <p className="error">{(setAdmin.error as Error).message}</p>
      )}

      {unblock.isError && (
        <p className="error">{(unblock.error as Error).message}</p>
      )}

      {pending === "revoke" && (
        <ConfirmSheet
          title="Obunani to'xtatish"
          body={`${name} ning obunasi darhol to'xtatiladi va u yana bepul limitga qaytadi. Keyin faqat qayta yoqish orqali tiklanadi.`}
          confirmLabel="Ha, to'xtatish"
          danger
          busy={revoke.isPending}
          onConfirm={() => revoke.mutate()}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}

export default function AdminPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>("overview");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");
  const [limit, setLimit] = useState(20);

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  // Subscription stats, filters and row actions all hang off this one flag.
  const paid = !!me?.subscriptions_enabled;
  // Everything an admin may do beyond reading the overview. The owner holds
  // all of them; an admin holds whatever they were granted.
  const myPermissions = me?.permissions ?? [];
  const tabs = TABS.filter(
    (t) => !("needs" in t) || myPermissions.includes(t.needs),
  );
  const activeTab = tabs.some((t) => t.key === tab) ? tab : "overview";
  const filters = FILTERS.filter(
    (f) => paid || !("paidOnly" in f && f.paidOnly),
  );
  const activeFilter = filters.some((f) => f.key === filter) ? filter : "all";

  const { data: stats } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => api.adminStats(),
    enabled: me?.is_admin === true && activeTab === "overview",
    refetchInterval: 30000,
  });

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin", "users", search, activeFilter, limit],
    queryFn: () => api.adminUsers({ search, filter: activeFilter, limit }),
    enabled: me?.is_admin === true && activeTab === "overview",
  });

  // Non-admins never see this screen, even by typing the URL.
  if (me && !me.is_admin) {
    navigate("/", { replace: true });
    return null;
  }

  return (
    <div className="page">
      <h1>🛠 Admin</h1>

      {tabs.length > 1 && (
        <div className="admin-tabs">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`admin-tab ${
                activeTab === t.key ? "admin-tab-active" : ""
              }`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {activeTab === "payments" && <AdminPayments />}
      {activeTab === "sessions" && <AdminSessions />}
      {activeTab === "tables" && <AdminTables />}

      {activeTab === "overview" && (
        <>
          {!paid && (
            <p className="notice">
              Obuna tizimi hozircha o'chirilgan — ilova hamma uchun to'liq
              bepul. Skan limiti hisoblanmayapti va to'lov ekrani
              ko'rsatilmayapti.
            </p>
          )}

          <div className="stat-grid">
            <StatTile
              label="Foydalanuvchilar"
              value={fmtNum(stats?.users_total ?? 0)}
              hint={
                stats
                  ? `bugun +${stats.users_today} · 7 kun +${stats.users_week}`
                  : undefined
              }
            />
            <StatTile
              label="Skan · bugun"
              value={fmtNum(stats?.scans_today ?? 0)}
              hint={stats ? `7 kun: ${stats.scans_week}` : undefined}
            />
            <StatTile
              label="Skan · jami"
              value={fmtNum(stats?.scans_total ?? 0)}
              hint={stats ? `${stats.sessions_total} sessiya` : undefined}
            />
            <StatTile
              label="Adminlar"
              value={fmtNum(stats?.admins_total ?? 0)}
              hint="panelga kirish huquqi"
            />
            {paid && (
              <>
                <StatTile
                  label="Obunachilar"
                  value={fmtNum(stats?.subscribed ?? 0)}
                  hint={
                    stats ? `${stats.exhausted} ta limiti tugagan` : undefined
                  }
                />
                <StatTile
                  label="Bu oy tushum"
                  value={`${fmtNum(stats?.revenue_month ?? 0)} so'm`}
                  hint={stats ? `${stats.payments_month} ta to'lov` : undefined}
                />
                <StatTile
                  label="Obuna narxi"
                  value={`${fmtNum(stats?.price_uzs ?? 0)} so'm`}
                  hint="30 kun"
                />
              </>
            )}
          </div>

          {stats && <DailyScansChart data={stats.daily_scans} />}

          {can(me, "manage_admins") && (
            <>
              <h2 className="section-title">Adminlar</h2>
              <AddAdminForm />
            </>
          )}

          <h2 className="section-title">Foydalanuvchilar</h2>

          <input
            type="text"
            placeholder="Ism, @username yoki ID bo'yicha qidirish"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="chip-row">
            {filters.map((f) => (
              <button
                key={f.key}
                className={`chip ${activeFilter === f.key ? "chip-active" : ""}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>

          {isLoading && (
            <p style={{ color: "var(--hint)", fontSize: 14 }}>Yuklanmoqda…</p>
          )}

          {users && (
            <>
              <p style={{ color: "var(--hint)", fontSize: 13, margin: 0 }}>
                {users.total} ta topildi
              </p>
              {users.users.map((u) => (
                <UserRow
                  key={u.telegram_user_id}
                  user={u}
                  paid={paid}
                  meId={me?.telegram_user_id}
                  myPermissions={myPermissions}
                />
              ))}
              {users.users.length < users.total && (
                <button
                  className="btn btn-ghost"
                  onClick={() => setLimit((l) => l + 20)}
                >
                  Yana yuklash
                </button>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
