import type {
  Conversation,
  Message,
  SavedStrategy,
} from "./types";

/** Avoid IPv6 `localhost` → `::1` when the API only binds `127.0.0.1` (common hang / refused). */
function resolveApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "");
  if (env && env.length > 0) {
    return env;
  }
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  const { protocol, hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://127.0.0.1:8000";
  }
  return `${protocol}//${hostname}:8000`;
}

const BASE = resolveApiBase();

/** Default caps at 10 min; AI filter + SMC can exceed that on cold cache. */
const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;
const BOOT_TIMEOUT_MS = 20 * 1000;
const AI_FILTER_TIMEOUT_MS = 45 * 60 * 1000;

async function fetchJSON<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(BASE + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API ${res.status}: ${text}`);
    }
    return res.json();
  } catch (e: unknown) {
    const err = e as { name?: string; message?: string };
    if (err?.name === "AbortError") {
      throw new Error(
        "Request timed out or was cancelled. The AI filter can take many minutes on a long history — " +
          "keep this tab open and try again."
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () =>
    fetchJSON<{ status: string; llm_mode: string }>("/health", undefined, BOOT_TIMEOUT_MS),

  listConversations: () =>
    fetchJSON<Conversation[]>("/conversations", undefined, BOOT_TIMEOUT_MS),
  createConversation: (title?: string) =>
    fetchJSON<Conversation>(
      "/conversations",
      {
        method: "POST",
        body: JSON.stringify({ title }),
      },
      BOOT_TIMEOUT_MS
    ),
  getConversation: (id: string) =>
    fetchJSON<Conversation>(`/conversations/${id}`),
  deleteConversation: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/conversations/${id}`, { method: "DELETE" }),
  renameConversation: (id: string, title: string) =>
    fetchJSON<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  sendMessage: (
    id: string,
    body: { content: string; action?: string; payload?: Record<string, any> }
  ) =>
    fetchJSON<Message[]>(
      `/conversations/${id}/messages`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
      body?.action === "run_filter" ? AI_FILTER_TIMEOUT_MS : DEFAULT_TIMEOUT_MS
    ),

  listStrategies: () => fetchJSON<SavedStrategy[]>("/strategies"),
  getStrategy: (id: string) => fetchJSON<any>(`/strategies/${id}`),
  deleteStrategy: (id: string) =>
    fetchJSON<{ ok: boolean }>(`/strategies/${id}`, { method: "DELETE" }),

  listIndicators: () => fetchJSON<any[]>("/catalog/indicators"),
  listTemplates: () => fetchJSON<any[]>("/catalog/templates"),
  listInstruments: () => fetchJSON<any[]>("/catalog/instruments"),
};
