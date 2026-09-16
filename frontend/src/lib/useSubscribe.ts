import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { tg } from "../telegram";

export type SubscribeState = "idle" | "opening" | "paid" | "cancelled" | "failed";

/** The subscription is granted by the bot's successful_payment webhook, which
 * can land a moment after openInvoice() reports "paid" — so poll /me briefly
 * instead of trusting a single read right after the callback. */
async function waitForSubscription(tries = 5, delayMs = 700): Promise<boolean> {
  for (let i = 0; i < tries; i++) {
    try {
      const me = await api.getMe();
      if (me.is_subscribed) return true;
    } catch {
      // Ignore and retry — a transient failure here shouldn't look like a
      // failed payment.
    }
    await new Promise((r) => setTimeout(r, delayMs));
  }
  return false;
}

/** Opens the Telegram Stars invoice inside the Mini App and refreshes the
 * cached /me state once the payment goes through. */
export function useSubscribe(botUsername?: string | null) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SubscribeState>("idle");

  async function subscribe() {
    setState("opening");
    try {
      const { link } = await api.createInvoiceLink();

      // openInvoice needs Bot API 6.1+; older clients fall back to paying in
      // the bot chat via the /start subscribe deep link.
      if (!tg.isVersionAtLeast?.("6.1")) {
        tg.openTelegramLink(
          `https://t.me/${botUsername ?? "hsbchbot"}?start=subscribe`,
        );
        setState("idle");
        return;
      }

      tg.openInvoice(link, async (status) => {
        if (status !== "paid") {
          setState(status === "cancelled" ? "cancelled" : "failed");
          return;
        }
        const ok = await waitForSubscription();
        await queryClient.invalidateQueries({ queryKey: ["me"] });
        setState(ok ? "paid" : "failed");
      });
    } catch {
      setState("failed");
    }
  }

  return { subscribe, state, reset: () => setState("idle") };
}
