import WebApp from "@twa-dev/sdk";

export const tg = WebApp;

export interface TgUser {
  id: number;
  name: string;
}

function devParam(key: string): string | null {
  // Persist dev identity so it survives client-side navigation (the URL query
  // is dropped after redirects). Inside Telegram this path is never used.
  const fromUrl = new URLSearchParams(window.location.search).get(key);
  if (fromUrl) {
    localStorage.setItem(key, fromUrl);
    return fromUrl;
  }
  return localStorage.getItem(key);
}

/**
 * The authenticated user. Inside Telegram this comes from initDataUnsafe.
 * In the browser (dev) it falls back to ?devUser=<id>&devName=<name>
 * (or the same keys in localStorage) so two users can be simulated.
 */
export function getTelegramUser(): TgUser {
  const user = WebApp.initDataUnsafe?.user;
  if (user?.id) {
    return { id: user.id, name: user.first_name || user.username || `User ${user.id}` };
  }
  const devId = devParam("devUser");
  if (devId) {
    return { id: Number(devId), name: devParam("devName") || `User ${devId}` };
  }
  return { id: 0, name: "Guest" };
}

/** Raw signed initData string (empty in the browser). */
export function getInitData(): string {
  return WebApp.initData || "";
}

/**
 * Auth headers sent on every API request. Prefers the signed initData;
 * falls back to unsigned dev headers when running outside Telegram.
 */
export function authHeaders(): Record<string, string> {
  const initData = getInitData();
  if (initData) return { "X-Telegram-Init-Data": initData };
  const u = getTelegramUser();
  return {
    "X-Telegram-User-Id": String(u.id),
    "X-Telegram-User-Name": u.name,
  };
}

/**
 * The language to open in, when nothing has been chosen yet.
 *
 * Telegram knows which language the person reads, so asking them again is a
 * step that buys nothing. `language_code` is a base tag ("ru") or a full one
 * ("pt-BR"); anything unsupported falls back to Uzbek.
 */
export function preferredLanguage(supported: string[], fallback: string): string {
  const code = WebApp.initDataUnsafe?.user?.language_code ?? "";
  const base = code.toLowerCase().split("-")[0];
  return supported.includes(base) ? base : fallback;
}

/**
 * What a deep link points at: ?join=<token> or Telegram's startapp param.
 *
 * Either a session id or a join code. Links posted into a chat carry the id,
 * because a code goes back in the pool after a month and would eventually
 * point at someone else's bill; a code still arrives from links shared
 * before that, and from anyone typing one in. Not upper-cased any more — it
 * may be a uuid.
 */
export function getJoinToken(): string | null {
  const fromQuery = new URLSearchParams(window.location.search).get("join");
  const fromStart = WebApp.initDataUnsafe?.start_param;
  return (fromQuery || fromStart || "").trim() || null;
}

/**
 * Telegram's haptics, safe to call anywhere.
 *
 * The API only exists inside a recent Telegram client — in a browser (which
 * is where dev testing happens) and in older clients the calls are missing or
 * throw, and a buzz is never worth an exception.
 */
function buzz(run: (h: NonNullable<typeof tg.HapticFeedback>) => void) {
  try {
    const h = tg.HapticFeedback;
    if (h) run(h);
  } catch {
    /* no haptics here */
  }
}

export const haptic = {
  /** A choice was made: an item picked, a screen entered. */
  select: () => buzz((h) => h.selectionChanged()),
  /** Something finished the way the user wanted. */
  success: () => buzz((h) => h.notificationOccurred("success")),
  /** Something went wrong. */
  error: () => buzz((h) => h.notificationOccurred("error")),
};

export function setMainButton(text: string, onClick: () => void) {
  tg.MainButton.setText(text);
  tg.MainButton.onClick(onClick);
  tg.MainButton.show();
}

export function hideMainButton() {
  tg.MainButton.offClick(() => {});
  tg.MainButton.hide();
}

export function showBackButton(onClick: () => void) {
  tg.BackButton.onClick(onClick);
  tg.BackButton.show();
}

export function hideBackButton() {
  tg.BackButton.offClick(() => {});
  tg.BackButton.hide();
}
