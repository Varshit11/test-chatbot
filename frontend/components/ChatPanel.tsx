"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Conversation, Message } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";
import { Composer } from "./Composer";
import { WelcomeHero } from "./WelcomeHero";
import { AIFilterBusyBanner } from "./AIFilterBusyBanner";

interface Props {
  conversationId: string;
  onTitleChange?: (id: string, title: string) => void;
  onChange?: () => void;
  /** When true, add left padding so the floating "show sidebar" control does not cover the title. */
  sidebarCollapsed?: boolean;
}

export function ChatPanel({ conversationId, onTitleChange, onChange, sidebarCollapsed }: Props) {
  const [conv, setConv] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState<string | null>(null);   // null | action-id | "send"
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Load
  useEffect(() => {
    let cancel = false;
    setMessages([]);
    setConv(null);
    api.getConversation(conversationId).then((c) => {
      if (cancel) return;
      setConv(c);
      setMessages(c.messages || []);
    });
    return () => {
      cancel = true;
    };
  }, [conversationId]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, busy]);

  const send = async (
    content: string,
    action?: string,
    payload?: Record<string, any>
  ) => {
    if (!content.trim() && !action) return;
    setBusy(action || "send");

    const optimistic: Message = {
      id: `tmp-${Date.now()}`,
      conversation_id: conversationId,
      role: "user",
      content: content || labelFor(action),
      msg_type: "text",
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, optimistic]);

    try {
      const out = await api.sendMessage(conversationId, { content, action, payload });
      setMessages((prev) => {
        const trimmed = prev.filter((p) => p.id !== optimistic.id);
        return [...trimmed, ...out];
      });
      onChange?.();
      // refresh conversation to pick up title change
      api.getConversation(conversationId).then((c) => {
        setConv(c);
        if (c.title && onTitleChange) onTitleChange(c.id, c.title);
      });
    } catch (e: any) {
      setMessages((prev) => [
        ...prev.filter((p) => p.id !== optimistic.id),
        {
          id: `err-${Date.now()}`,
          conversation_id: conversationId,
          role: "assistant",
          content: `**Error**: ${e?.message || e}`,
          msg_type: "text",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setBusy(null);
    }
  };

  const handleAction = (id: string, payload?: Record<string, any>) => {
    if (busy) return;
    send("", id, payload);
  };

  return (
    <div className="qf-chat-panel flex h-full min-w-0 flex-1 flex-col">
      {messages.length > 0 && (
        <header
          className={
            "flex items-center justify-between border-b border-white/5 bg-black/60 py-4 pr-5 backdrop-blur " +
            (sidebarCollapsed ? "pl-14 sm:pl-16" : "pl-6")
          }
        >
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold tracking-tight text-white">
              {conv?.title || "Conversation"}
            </div>
          </div>
        </header>
      )}

      <div ref={scrollRef} className="qf-chat-scroll flex-1 overflow-y-auto px-4 sm:px-8">
        <div className="mx-auto max-w-4xl py-3">
          {messages.length === 0 && !busy && (
            <WelcomeHero
              value={input}
              onChange={setInput}
              onSubmit={() => {
                const v = input;
                setInput("");
                send(v);
              }}
              disabled={!!busy}
              onPickPrompt={(text) => {
                setInput("");
                send(text);
              }}
            />
          )}
          {messages.length > 0 &&
            messages.map((m) => (
              <MessageBubble
                key={m.id}
                msg={m}
                onAction={handleAction}
                busy={busy}
              />
            ))}
          {busy === "run_filter" && (
            <div className="px-2 py-2">
              <AIFilterBusyBanner />
            </div>
          )}
          {busy && busy !== "run_filter" && (
            <div className="px-2 py-3 text-xs text-ink-dim">
              <span className="dot-pulse" />
              {busyLabel(busy)}…
            </div>
          )}
        </div>
      </div>

      {messages.length > 0 && (
        <Composer
          value={input}
          onChange={setInput}
          onSubmit={() => {
            const v = input;
            setInput("");
            send(v);
          }}
          disabled={!!busy}
        />
      )}
    </div>
  );
}

function labelFor(action?: string): string {
  switch (action) {
    case "confirm": return "Run the backtest";
    case "edit_params": return "Apply edits";
    case "run_finder": return "Preview Strategy Finder ranges";
    case "confirm_run_finder": return "Run optimization with these ranges";
    case "run_filter": return "Apply the AI filter";
    case "improve": return "Show pros, cons & improvements";
    case "save": return "Save the strategy";
    case "apply_best_params": return "Apply best parameters";
    default: return "";
  }
}

function busyLabel(busy: string): string {
  switch (busy) {
    case "send": return "thinking";
    case "confirm":
    case "edit_params":
    case "apply_best_params": return "running the backtest";
    case "run_finder": return "preparing parameter ranges";
    case "confirm_run_finder": return "searching the parameter space (this can take ~1 min)";
    case "run_filter": return "running the patented AI filter";
    case "improve": return "reviewing the strategy";
    case "save": return "saving";
    default: return "working";
  }
}
