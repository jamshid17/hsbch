/** The authenticated Telegram user returned by POST /api/auth/telegram. */
export interface TelegramAuthUser {
  id: number;
  first_name: string;
  username: string | null;
}

/** State exposed by the auth hook / context. */
export interface AuthState {
  isLoading: boolean;
  isAuthenticated: boolean;
  user: TelegramAuthUser | null;
  error: string | null;
  /** True when opened outside Telegram (plain browser) — show the landing page. */
  notInTelegram: boolean;
  /** An admin has blocked this account. A dead end, not a failure to retry:
   * `error` carries the reason, when one was given. */
  isBlocked: boolean;
}

/** Auth context value: state plus a manual retry. */
export interface AuthContextValue extends AuthState {
  retry: () => void;
}
