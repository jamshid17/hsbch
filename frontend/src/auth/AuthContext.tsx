import { createContext, useContext, type ReactNode } from "react";
import { useTelegramAuth } from "./useTelegramAuth";
import LandingPage from "../pages/LandingPage";
import type { AuthContextValue } from "../types/auth";

const AuthContext = createContext<AuthContextValue | null>(null);

/** Centered full-screen message used for the loading / error gates. */
function GateScreen({ children }: { children: ReactNode }) {
  return (
    <div
      className="page"
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        gap: 16,
      }}
    >
      {children}
    </div>
  );
}

/**
 * Authenticates at the root level and only renders protected content once the
 * Telegram user is verified. While loading it shows a spinner; on failure it
 * shows the error with a retry button.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useTelegramAuth();

  // Opened in a normal browser → marketing landing page with a link to the bot.
  if (auth.notInTelegram) {
    return <LandingPage />;
  }

  if (auth.isLoading) {
    return (
      <GateScreen>
        <div className="auth-spinner" aria-label="Loading" />
        <p style={{ color: "var(--hint)" }}>Authenticating…</p>
      </GateScreen>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <GateScreen>
        <div style={{ fontSize: 40 }}>🔒</div>
        <p className="error">{auth.error ?? "Authentication failed"}</p>
        <button className="btn" style={{ maxWidth: 240 }} onClick={auth.retry}>
          Retry
        </button>
      </GateScreen>
    );
  }

  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

/** Access the authenticated user / auth state anywhere below <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthProvider>");
  }
  return ctx;
}
