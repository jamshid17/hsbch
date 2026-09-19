import { authHeaders } from "./telegram";
import type { TelegramAuthUser } from "./types/auth";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // For FormData (file upload) we must NOT set Content-Type — the browser sets
  // it together with the multipart boundary. Forcing application/json there
  // strips the boundary and the server sees no file.
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...authHeaders(),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    let message = text || res.statusText;
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") message = parsed.detail;
    } catch {
      // Not JSON — keep the raw text as the message.
    }
    throw new ApiError(message, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface SessionOut {
  id: string;
  code: string;
  telegram_chat_id: number;
  currency: string;
  tax: string;
  tip: string;
  status: string;
  title?: string;
  assignment_mode: string;
}

export interface ItemOut {
  id: string;
  name: string;
  price: string;
  quantity: string;
  unit: string;
}

export interface PersonOut {
  id: string;
  name: string;
  telegram_user_id: number | null;
}

export interface Pick {
  item_id: string;
  quantity: string;
}

export interface ParticipantOut {
  id: string;
  name: string;
  telegram_user_id: number | null;
  is_host: boolean;
  picks: Pick[];
}

export interface PersonSummary {
  person_id: string;
  name: string;
  items: { name: string; share: string }[];
  subtotal: string;
  extras: string;
  total: string;
}

export interface SummaryOut {
  title: string;
  currency: string;
  people: PersonSummary[];
}

export interface ScanResult {
  title: string;
  currency: string;
  tax: string;
  tip: string;
  items: { name: string; price: string; quantity: string; unit: string }[];
}

export interface MeOut {
  telegram_user_id: number;
  /** False = the paid tier is off and the app is fully free. Every paywall,
   * quota line and card block is keyed off this. */
  subscriptions_enabled: boolean;
  is_subscribed: boolean;
  subscription_until: string | null;
  scans_left: number;
  free_total_scans: number;
  subscription_days: number;
  is_admin: boolean;
  /** The owner account (first id in ADMIN_TELEGRAM_IDS). Ordinary admins only
   * get the overview tab of the panel. */
  is_super_admin: boolean;
  card: {
    number: string;
    holder: string;
    price_uzs: number;
    admin_contact: string;
  } | null;
}

export interface AdminStats {
  users_total: number;
  users_today: number;
  users_week: number;
  scans_total: number;
  scans_today: number;
  scans_week: number;
  subscribed: number;
  exhausted: number;
  sessions_total: number;
  revenue_month: number;
  payments_month: number;
  price_uzs: number;
  daily_scans: { date: string; scans: number }[];
  admins_total: number;
  subscriptions_enabled: boolean;
}

export interface AdminUser {
  telegram_user_id: number;
  first_name: string | null;
  username: string | null;
  free_scans_used: number;
  free_total_scans: number;
  scans_total: number;
  is_subscribed: boolean;
  subscription_until: string | null;
  last_seen_at: string | null;
  created_at: string | null;
  is_admin: boolean;
  /** The owner account (first id in ADMIN_TELEGRAM_IDS) — no other admin can
   * demote them. */
  is_super_admin: boolean;
}

/** Enough of a bot_users row to label a payment or a session. */
export interface AdminUserBrief {
  telegram_user_id: number;
  first_name: string | null;
  username: string | null;
}

export interface AdminPayment {
  id: string;
  amount: number;
  currency: string;
  method: string;
  granted_by: number | null;
  note: string | null;
  refunded_at: string | null;
  created_at: string | null;
  user: AdminUserBrief;
}

export interface AdminSession {
  id: string;
  code: string;
  status: string;
  title: string | null;
  currency: string;
  assignment_mode: string;
  items_count: number;
  people_count: number;
  created_at: string | null;
  host: AdminUserBrief;
}

export interface AdminTables {
  tables: { name: string; rows: number }[];
  db_size: string;
  pg_version: string;
}

export const api = {
  // Validates the Telegram initData (sent via the X-Telegram-Init-Data header
  // by authHeaders()) and returns the authenticated user.
  authTelegram: () =>
    request<TelegramAuthUser>("/auth/telegram", { method: "POST" }),

  getConfig: () =>
    request<{ bot_username: string | null }>("/config"),

  getMe: () => request<MeOut>("/me"),

  adminStats: () => request<AdminStats>("/admin/stats"),

  adminUsers: (params: { search?: string; filter?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params.search) q.set("search", params.search);
    if (params.filter && params.filter !== "all") q.set("filter", params.filter);
    q.set("limit", String(params.limit ?? 50));
    q.set("offset", String(params.offset ?? 0));
    return request<{ total: number; users: AdminUser[] }>(`/admin/users?${q}`);
  },

  adminPayments: (params: { limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams({
      limit: String(params.limit ?? 20),
      offset: String(params.offset ?? 0),
    });
    return request<{ total: number; revenue_total: number; payments: AdminPayment[] }>(
      `/admin/payments?${q}`,
    );
  },

  adminSessions: (params: { limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams({
      limit: String(params.limit ?? 20),
      offset: String(params.offset ?? 0),
    });
    return request<{ total: number; sessions: AdminSession[] }>(`/admin/sessions?${q}`);
  },

  adminTables: () => request<AdminTables>("/admin/tables"),

  adminUserPayments: (userId: number) =>
    request<AdminPayment[]>(`/admin/users/${userId}/payments`),

  adminGrant: (userId: number, days: number) =>
    request<{ subscription_until: string; days_added: number }>(
      `/admin/users/${userId}/grant`,
      { method: "POST", body: JSON.stringify({ days }) },
    ),

  adminRevoke: (userId: number) =>
    request<{ is_subscribed: boolean }>(`/admin/users/${userId}/revoke`, {
      method: "POST",
    }),

  adminSetAdmin: (userId: number, isAdmin: boolean) =>
    request<{ is_admin: boolean; is_super_admin: boolean }>(
      `/admin/users/${userId}/admin`,
      { method: "POST", body: JSON.stringify({ is_admin: isAdmin }) },
    ),

  createSession: () =>
    request<SessionOut>("/sessions", { method: "POST" }),

  getSession: (sessionId: string) =>
    request<SessionOut>(`/sessions/${sessionId}`),

  getSessionByCode: (code: string) =>
    request<SessionOut>(`/sessions/by-code/${code}`),

  joinSession: (sessionId: string) =>
    request<PersonOut>(`/sessions/${sessionId}/join`, { method: "POST" }),

  uploadReceipt: (sessionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ScanResult>(`/sessions/${sessionId}/receipt`, {
      method: "POST",
      body: form,
    });
  },

  updateItems: (
    sessionId: string,
    payload: { items: Omit<ItemOut, "id">[]; currency: string; tax: string; tip: string }
  ) =>
    request<ItemOut[]>(`/sessions/${sessionId}/items`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  listItems: (sessionId: string) =>
    request<ItemOut[]>(`/sessions/${sessionId}/items`),

  listParticipants: (sessionId: string) =>
    request<ParticipantOut[]>(`/sessions/${sessionId}/participants`),

  saveMyAssignments: (
    sessionId: string,
    picks: { item_id: string; quantity: string }[]
  ) =>
    request<Pick[]>(`/sessions/${sessionId}/my-assignments`, {
      method: "PUT",
      body: JSON.stringify({ picks }),
    }),

  finalizeSession: (sessionId: string) =>
    request<SessionOut>(`/sessions/${sessionId}/finalize`, { method: "POST" }),

  getSummary: (sessionId: string) =>
    request<SummaryOut>(`/sessions/${sessionId}/summary`),

  /** Hands the rendered split card to the bot, which posts it to the user's
   * own chat with a share button — a Mini App can't put a file in a chat
   * itself. Resolves with nothing; 409 means the bot may not write to them. */
  sendSummaryImage: (
    sessionId: string,
    image: Blob,
    caption: string,
    shareLabel: string
  ) => {
    const form = new FormData();
    form.append("file", image, "hisob.png");
    form.append("caption", caption);
    form.append("share_label", shareLabel);
    return request<void>(`/sessions/${sessionId}/summary/image`, {
      method: "POST",
      body: form,
    });
  },

  updateSession: (sessionId: string, data: { title?: string; assignment_mode?: string }) =>
    request<SessionOut>(`/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Host-assigns mode: host manages a named-only people list and assigns
  // every item to everyone themselves.
  listPeople: (sessionId: string) =>
    request<PersonOut[]>(`/sessions/${sessionId}/people`),

  addPerson: (sessionId: string, name: string) =>
    request<PersonOut>(`/sessions/${sessionId}/people`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  bulkSetPeople: (sessionId: string, people: { name: string }[]) =>
    request<PersonOut[]>(`/sessions/${sessionId}/people`, {
      method: "PUT",
      body: JSON.stringify({ people }),
    }),

  deletePerson: (sessionId: string, personId: string) =>
    request<void>(`/sessions/${sessionId}/people/${personId}`, { method: "DELETE" }),

  setHostAssignments: (
    sessionId: string,
    assignments: { item_id: string; person_id: string; quantity: string }[]
  ) =>
    request<SessionOut>(`/sessions/${sessionId}/host-assignments`, {
      method: "PUT",
      body: JSON.stringify({ assignments }),
    }),
};
