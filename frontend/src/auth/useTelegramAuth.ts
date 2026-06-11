import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { tg, getInitData } from "../telegram";
import type { AuthContextValue, AuthState } from "../types/auth";

const INITIAL: AuthState = {
  isLoading: true,
  isAuthenticated: false,
  user: null,
  error: null,
};

/**
 * Authenticates the current Telegram Mini App session against the backend.
 *
 * - Signals readiness to Telegram (`WebApp.ready()`).
 * - Reads the signed `WebApp.initData` string.
 * - POSTs /api/auth/telegram; the raw initData travels in the
 *   `X-Telegram-Init-Data` header (added by `authHeaders()` in api.ts). Outside
 *   Telegram, the dev fallback header is used instead.
 * - Tracks { isLoading, isAuthenticated, user, error }.
 *
 * The request fires exactly once, even under React 18 StrictMode's double
 * effect invocation, via a ref guard.
 */
export function useTelegramAuth(): AuthContextValue {
  const [state, setState] = useState<AuthState>(INITIAL);
  const hasRun = useRef(false);

  const authenticate = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      // Idempotent; tells the Telegram client the app is ready to be shown.
      tg.ready();

      // Inside Telegram this is the signed initData string; in a plain browser
      // it is empty and the dev fallback (X-Telegram-User-Id) is used instead.
      const initData = getInitData();
      if (!initData && !import.meta.env.DEV) {
        throw new Error("Not running inside Telegram");
      }

      const user = await api.authTelegram();
      setState({ isLoading: false, isAuthenticated: true, user, error: null });
    } catch (err) {
      setState({
        isLoading: false,
        isAuthenticated: false,
        user: null,
        error: err instanceof Error ? err.message : "Authentication failed",
      });
    }
  }, []);

  useEffect(() => {
    // StrictMode invokes effects twice in development; the ref ensures the
    // network request runs only once.
    if (hasRun.current) return;
    hasRun.current = true;
    void authenticate();
  }, [authenticate]);

  const retry = useCallback(() => {
    void authenticate();
  }, [authenticate]);

  return { ...state, retry };
}
