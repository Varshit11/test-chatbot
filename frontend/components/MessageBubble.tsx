"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import { User, Sparkles } from "lucide-react";
import type { Message } from "@/lib/types";
import { StrategyConfirmation } from "./StrategyConfirmation";
import { StrategyFinderPreview } from "./StrategyFinderPreview";
import {
  BacktestCard,
  StrategyFinderCard,
  AIFilterCard,
  ImprovementsCard,
} from "./ResultsCards";

export function MessageBubble({
  msg,
  onAction,
  busy,
}: {
  msg: Message;
  onAction: (id: string, payload?: Record<string, any>) => void;
  busy?: string | null;
}) {
  const isUser = msg.role === "user";
  return (
    <div
      className={clsx(
        "group flex animate-fade-up gap-3 px-2 py-3",
        isUser ? "" : ""
      )}
    >
      <div
        className={clsx(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
          isUser
            ? "bg-bg-elev text-ink-muted ring-1 ring-line"
            : "bg-gradient-to-br from-violet-500 via-fuchsia-500 to-purple-600 text-white shadow-[0_3px_10px_-3px_rgba(168,85,247,0.55)]"
        )}
        aria-hidden
      >
        {isUser ? <User size={13} /> : <Sparkles size={13} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 text-[11px] text-ink-dim">
          {isUser ? "You" : "TradeXpert.ai"}
        </div>

        <div className={clsx("max-w-3xl text-[14.5px] leading-relaxed text-ink", isUser && "")}>
          {msg.content && (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          )}

          {msg.msg_type === "strategy_confirmation" && msg.metadata?.parsed && (
            <div className="mt-3 max-w-3xl">
              <StrategyConfirmation
                parsed={msg.metadata.parsed}
                onAction={onAction}
                busy={busy}
              />
            </div>
          )}

          {msg.msg_type === "backtest_result" && msg.metadata && (
            <div className="mt-3 max-w-4xl">
              <BacktestCard meta={msg.metadata} onAction={onAction} busy={busy} />
            </div>
          )}

          {msg.msg_type === "sf_preview" && msg.metadata && (
            <div className="mt-3 max-w-4xl">
              <StrategyFinderPreview meta={msg.metadata as any} onAction={onAction} busy={busy} />
            </div>
          )}

          {msg.msg_type === "sf_result" && msg.metadata && (
            <div className="mt-3 max-w-4xl">
              <StrategyFinderCard meta={msg.metadata} onAction={onAction} busy={busy} />
            </div>
          )}

          {msg.msg_type === "ai_filter_result" && msg.metadata && (
            <div className="mt-3 max-w-4xl">
              <AIFilterCard meta={msg.metadata} onAction={onAction} busy={busy} />
            </div>
          )}

          {msg.msg_type === "improvements" && msg.metadata && (
            <div className="mt-3 max-w-3xl">
              <ImprovementsCard meta={msg.metadata} onAction={onAction} busy={busy} />
            </div>
          )}

          {msg.msg_type === "saved" && (
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-800/60 bg-emerald-900/20 px-2.5 py-1 text-xs text-emerald-200">
              ✓ Saved
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
