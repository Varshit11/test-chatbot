"use client";

import { Search, Sparkles, Lightbulb, Save, Play, Edit3, Check } from "lucide-react";
import clsx from "clsx";

const ICONS: Record<string, any> = {
  search: Search,
  sparkles: Sparkles,
  lightbulb: Lightbulb,
  save: Save,
  play: Play,
  edit: Edit3,
  check: Check,
};

interface ActionButton {
  id: string;
  label: string;
  icon?: string;
}

export function ActionButtons({
  actions,
  onAction,
  busy,
}: {
  actions?: ActionButton[];
  onAction: (id: string) => void;
  busy?: string | null;
}) {
  if (!actions || actions.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {actions.map((a) => {
        const Icon = ICONS[a.icon || ""] || Sparkles;
        const isBusy = busy === a.id;
        const isPrimary = a.id === "confirm" || a.id === "apply_best_params";
        return (
          <button
            key={a.id}
            onClick={() => onAction(a.id)}
            disabled={!!busy}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
              isPrimary
                ? "bg-accent text-white shadow-sm hover:bg-accent-dim"
                : "border border-line bg-bg-elev text-ink-muted hover:bg-[#1c1c22] hover:text-ink"
            )}
          >
            {isBusy ? (
              <span className="inline-flex items-center">
                <span className="mr-1.5 h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                {a.id === "run_filter" ? "AI filter…" : "Working…"}
              </span>
            ) : (
              <>
                <Icon size={13} />
                {a.label}
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
