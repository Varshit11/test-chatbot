"use client";

import { useEffect, useMemo, useState } from "react";
import {
  MessageSquarePlus,
  Search,
  Trash2,
  Check,
  X as XIcon,
} from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import { TradeXpertLogo } from "./TradeXpertLogo";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
  onCollapse?: () => void;
}

export function Sidebar({ activeId, onSelect, onNew, refreshKey, onCollapse }: Props) {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    let cancel = false;
    api
      .listConversations()
      .then((c) => {
        if (!cancel) setConvs(c);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [refreshKey]);

  const filteredConvs = useMemo(() => {
    if (!query.trim()) return convs;
    const q = query.toLowerCase();
    return convs.filter((c) => (c.title || "").toLowerCase().includes(q));
  }, [convs, query]);

  return (
    <aside className="qf-sidebar tx-sidebar flex h-full w-72 shrink-0 flex-col bg-black text-white">
      <div className="flex items-center justify-between px-5 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <TradeXpertLogo size={22} />
          <span className="text-[17px] font-semibold tracking-tight">TradeXpert</span>
        </div>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            className="flex h-7 w-7 items-center justify-center rounded-md text-white/60 transition-colors hover:bg-white/5 hover:text-white"
            title="Hide sidebar"
            aria-label="Hide sidebar"
          >
            <XIcon size={18} strokeWidth={1.75} />
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-0.5 px-3 pt-2">
        <NavItem
          icon={<MessageSquarePlus size={18} strokeWidth={1.75} />}
          label="New Chats"
          onClick={onNew}
        />
        <NavItem
          icon={<Search size={18} strokeWidth={1.75} />}
          label="Search"
          active={searchOpen}
          onClick={() => setSearchOpen((v) => !v)}
        />
      </nav>

      {searchOpen && (
        <div className="mx-3 mt-3">
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2 focus-within:border-violet-500/40">
            <Search size={14} className="text-white/40" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats…"
              className="w-full bg-transparent text-sm text-white outline-none placeholder:text-white/30"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                className="text-white/40 hover:text-white"
                aria-label="Clear search"
              >
                <XIcon size={13} />
              </button>
            )}
          </div>
        </div>
      )}

      <div className="mt-6 px-5 text-[11px] font-medium uppercase tracking-[0.16em] text-white/35">
        Your Recent Chats
      </div>

      <div className="mt-2 flex-1 overflow-y-auto px-2 pb-4">
        {filteredConvs.length === 0 ? (
          <EmptyHint label={query ? "No matches" : "No conversations yet"} />
        ) : (
          filteredConvs.map((c) => (
            <ConversationItem
              key={c.id}
              conv={c}
              active={c.id === activeId}
              onClick={() => onSelect(c.id)}
              onDelete={async () => {
                try {
                  await api.deleteConversation(c.id);
                  setConvs((cs) => cs.filter((x) => x.id !== c.id));
                  if (activeId === c.id) onNew();
                } catch (e: any) {
                  alert(`Could not delete: ${e?.message || e}`);
                }
              }}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-[15px] font-medium transition-all",
        active
          ? "bg-white/[0.06] text-white"
          : "text-white/85 hover:bg-white/[0.04] hover:text-white"
      )}
    >
      <span className="text-white/70">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function EmptyHint({ label }: { label: string }) {
  return (
    <div className="px-3 py-6 text-center text-xs text-white/40">{label}</div>
  );
}

function ConversationItem({
  conv,
  active,
  onClick,
  onDelete,
}: {
  conv: Conversation;
  active: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <div
      onClick={confirming ? undefined : onClick}
      className={clsx(
        "group mb-0.5 flex items-center gap-2 rounded-lg px-3 py-2 text-[14px]",
        confirming ? "border border-rose-500/40 bg-rose-900/20" : "cursor-pointer",
        !confirming &&
          (active
            ? "bg-white/[0.06] text-white"
            : "text-white/70 hover:bg-white/[0.04] hover:text-white")
      )}
    >
      <div className="min-w-0 flex-1 truncate">{conv.title}</div>

      {confirming ? (
        <div className="flex shrink-0 items-center gap-1">
          <button
            disabled={busy}
            onClick={async (e) => {
              e.stopPropagation();
              setBusy(true);
              try {
                await onDelete();
              } finally {
                setBusy(false);
                setConfirming(false);
              }
            }}
            className="rounded bg-rose-600/80 p-1 text-white hover:bg-rose-600 disabled:opacity-50"
            aria-label="Confirm delete"
            title="Confirm"
          >
            <Check size={12} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setConfirming(false);
            }}
            className="rounded bg-white/10 p-1 text-white/70 hover:text-white"
            aria-label="Cancel delete"
            title="Cancel"
          >
            <XIcon size={12} />
          </button>
        </div>
      ) : (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setConfirming(true);
          }}
          className="shrink-0 rounded p-1 text-white/30 opacity-0 transition-all hover:bg-rose-900/30 hover:text-rose-300 group-hover:opacity-100"
          aria-label="Delete"
          title="Delete"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  );
}

