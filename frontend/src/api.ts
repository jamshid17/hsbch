const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
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
  currency: string;
  tax: string;
  tip: string;
  status: string;
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
  currency: string;
  people: PersonSummary[];
}

export interface ScanResult {
  currency: string;
  tax: string;
  tip: string;
  items: { name: string; price: string; quantity: string; unit: string }[];
}

export const api = {
  createSession: (telegram_user_id: number, telegram_chat_id: number) =>
    request<SessionOut>("/sessions", {
      method: "POST",
      body: JSON.stringify({ telegram_user_id, telegram_chat_id }),
    }),

  uploadReceipt: (sessionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ScanResult>(`/sessions/${sessionId}/receipt`, {
      method: "POST",
      headers: {},
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

  addPerson: (sessionId: string, name: string) =>
    request<PersonOut>(`/sessions/${sessionId}/people`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  updatePeople: (sessionId: string, people: { name: string }[]) =>
    request<PersonOut[]>(`/sessions/${sessionId}/people`, {
      method: "PUT",
      body: JSON.stringify({ people }),
    }),

  listPeople: (sessionId: string) =>
    request<PersonOut[]>(`/sessions/${sessionId}/people`),

  updateAssignments: (
    sessionId: string,
    assignments: { item_id: string; person_ids: string[] }[]
  ) =>
    request<void>(`/sessions/${sessionId}/assignments`, {
      method: "PUT",
      body: JSON.stringify({ assignments }),
    }),

  getSummary: (sessionId: string) =>
    request<SummaryOut>(`/sessions/${sessionId}/summary`),
};
