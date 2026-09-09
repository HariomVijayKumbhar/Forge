import { AgentStep } from "./types";
import { getAccessToken } from "./api";

export interface SSEListener {
  onStep: (step: AgentStep) => void;
  onError: (error: any) => void;
  onComplete: () => void;
}

export function subscribeToAgentStream(
  runId: string,
  listeners: SSEListener
): () => void {
  let isClosed = false;
  let lastEventId: number | null = null;
  let abortController: AbortController | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: NodeJS.Timeout | null = null;

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  function connect() {
    if (isClosed) return;

    const streamUrl = `${API_BASE}/agent/stream/${runId}`;
    abortController = new AbortController();

    void fetch(streamUrl, {
      headers: {
        Accept: "text/event-stream",
        ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
        ...(lastEventId !== null ? { "Last-Event-ID": String(lastEventId) } : {}),
      },
      credentials: "include",
      signal: abortController.signal,
    }).then(async (response) => {
      if (!response.ok || !response.body) {
        throw new Error(`SSE request failed with status ${response.status}.`);
      }

      reconnectAttempts = 0;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!isClosed) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const dataLine = event.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;
          const idLine = event.split("\n").find((line) => line.startsWith("id: "));
          if (idLine) lastEventId = parseInt(idLine.slice(4), 10);
          const data: AgentStep = JSON.parse(dataLine.slice(6));
          if (data.id) lastEventId = data.id;
          listeners.onStep(data);
          if (["finish", "error", "stopped", "stuck"].includes(data.action_type)) {
            cleanup();
            listeners.onComplete();
            return;
          }
        }
      }
      if (!isClosed) throw new Error("SSE connection closed.");
    }).catch((error: unknown) => {
      if (isClosed || (error instanceof DOMException && error.name === "AbortError")) return;
      console.warn("SSE connection error, attempting reconnect...", error);
      scheduleReconnect();
    });
  }

  function scheduleReconnect() {
    if (reconnectAttempts < 5) {
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
      reconnectAttempts++;
      reconnectTimer = setTimeout(connect, delay);
    } else {
      listeners.onError(new Error("Lost connection to agent event stream."));
    }
  }

  function cleanup() {
    isClosed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    abortController?.abort();
    abortController = null;
  }

  connect();
  return cleanup;
}
