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

/** Join code from a deep link: ?join=CODE or Telegram startapp start_param. */
export function getJoinCode(): string | null {
  const fromQuery = new URLSearchParams(window.location.search).get("join");
  const fromStart = WebApp.initDataUnsafe?.start_param;
  return (fromQuery || fromStart || "").toUpperCase() || null;
}

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
