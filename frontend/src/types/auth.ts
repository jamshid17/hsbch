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
}

/** Auth context value: state plus a manual retry. */
export interface AuthContextValue extends AuthState {
  retry: () => void;
}
