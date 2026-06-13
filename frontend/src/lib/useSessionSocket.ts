import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

export interface SessionUpdate {
  type: string;
  status?: string;
}

/**
 * Subscribe to live updates for a session over WebSocket. On any update it
 * invalidates the live react-query caches (which refetch), and calls onUpdate
 * with the parsed message. Reconnects automatically if the socket drops.
 */
export function useSessionSocket(
  sessionId: string | undefined,
  onUpdate?: (msg: SessionUpdate) => void
) {
  const qc = useQueryClient();
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  useEffect(() => {
    if (!sessionId) return;

    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/sessions/${sessionId}`;

    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      ws = new WebSocket(url);
      ws.onmessage = (e) => {
        qc.invalidateQueries({ queryKey: ["participants", sessionId] });
        qc.invalidateQueries({ queryKey: ["live-summary", sessionId] });
        qc.invalidateQueries({ queryKey: ["summary", sessionId] });
        try {
          onUpdateRef.current?.(JSON.parse(e.data));
        } catch {
          /* ignore non-JSON */
        }
      };
      ws.onclose = () => {
        if (!closed) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws?.close();
    }

    connect();

    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [sessionId, qc]);
}
