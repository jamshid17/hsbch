import { authHeaders } from "./telegram";
import type { TelegramAuthUser } from "./types/auth";

const BASE = "/api";

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
    throw new Error(text || res.statusText);
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

export const api = {
  // Validates the Telegram initData (sent via the X-Telegram-Init-Data header
  // by authHeaders()) and returns the authenticated user.
  authTelegram: () =>
    request<TelegramAuthUser>("/auth/telegram", { method: "POST" }),

  getConfig: () =>
    request<{ bot_username: string | null }>("/config"),

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
