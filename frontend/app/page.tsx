"use client";

import { useEffect, useState } from "react";
import { PanelLeft } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { ChatPanel } from "@/components/ChatPanel";
import { api } from "@/lib/api";

export default function Home() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [llmMode, setLlmMode] = useState<string>("");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [bootError, setBootError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [health, convs] = await Promise.all([
          api.health().catch(() => null),
          api.listConversations().catch(() => []),
        ]);
        if (!alive) return;
        if (health) setLlmMode(health.llm_mode);
        if (convs.length > 0) {
          setActiveId(convs[0].id);
        } else {
          const c = await api.createConversation();
          if (!alive) return;
          setActiveId(c.id);
          setRefreshKey((k) => k + 1);
        }
      } catch (e: any) {
        if (!alive) return;
        const msg = e?.name === "AbortError"
          ? "Request timed out — is the TradeXpert.ai API running? (`python run.py` in chatbot/quantflow/backend)"
          : (e?.message || "Could not reach the TradeXpert.ai API on http://127.0.0.1:8000");
        setBootError(msg);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const handleNew = async () => {
    const c = await api.createConversation();
    setActiveId(c.id);
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="qf-app-shell flex h-screen w-screen overflow-hidden bg-bg">
      {sidebarOpen && (
        <Sidebar
          activeId={activeId}
          onSelect={(id) => setActiveId(id)}
          onNew={handleNew}
          refreshKey={refreshKey}
          onCollapse={() => setSidebarOpen(false)}
        />
      )}
      <div className="qf-main relative flex min-w-0 flex-1 flex-col">
        {!sidebarOpen && (
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="fixed left-3 top-3 z-50 flex h-9 w-9 items-center justify-center rounded-md border border-line bg-bg-panel text-ink-muted shadow-lg ring-1 ring-black/20 transition-colors hover:bg-bg-elev hover:text-ink"
            title="Show conversations"
            aria-label="Show conversations sidebar"
          >
            <PanelLeft size={18} strokeWidth={1.75} aria-hidden />
          </button>
        )}
        {llmMode === "mock" && (
          <div
            className={
              "border-b border-amber-700/40 bg-amber-900/20 py-1.5 pr-5 text-[11px] text-amber-200 " +
              (!sidebarOpen ? "pl-14" : "pl-5")
            }
          >
            Running in <span className="font-mono">mock LLM</span> mode — set <span className="font-mono">ANTHROPIC_API_KEY</span> to enable Claude-powered parsing.
          </div>
        )}
        {bootError ? (
          <div className="qf-boot-error flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm">
            <p className="qf-boot-error-title">Cannot start TradeXpert.ai</p>
            <p className="qf-boot-error-body">{bootError}</p>
            <p className="qf-boot-error-hint">
              Start the API from <code>chatbot/quantflow/backend</code>: <code>python run.py</code>
            </p>
          </div>
        ) : loading || !activeId ? (
          <div className="qf-loading-main flex flex-1 items-center justify-center text-sm text-ink-dim">
            Loading…
          </div>
        ) : (
          <ChatPanel
            key={activeId}
            conversationId={activeId}
            onChange={() => setRefreshKey((k) => k + 1)}
            onTitleChange={() => setRefreshKey((k) => k + 1)}
            sidebarCollapsed={!sidebarOpen}
          />
        )}
      </div>
    </div>
  );
}
