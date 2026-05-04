"use client";

import { useState } from "react";
import { ChevronRight, Code2, FileCode, ListChecks, Settings2 } from "lucide-react";
import clsx from "clsx";
import type { StrategyExplain } from "@/lib/types";

/**
 * Expandable "Show me what code actually ran" panel for a backtest result.
 * Surfaces:
 *   - The exact entry/exit rules (English).
 *   - The exact parameter values.
 *   - The list of indicators computed.
 *   - The actual `on_bar` Python source from the strategy class.
 *
 * Lets the user verify that the chatbot's interpretation of their natural
 * language matches what they meant.
 */
export function StrategyLogicPanel({
  explain,
}: {
  explain: StrategyExplain | undefined;
}) {
  const [open, setOpen] = useState(false);
  if (!explain) return null;
  const params = explain.params || {};
  const paramRows = Object.keys(params)
    .filter((k) => params[k] !== false && params[k] !== 0 && params[k] !== "")
    .sort();
  const fullSrc = explain.full_strategy_source?.trim();

  return (
    <div className="rounded-md border border-line bg-bg-elev">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[#1c1c22]"
      >
        <ChevronRight
          size={14}
          className={clsx("transition-transform", open && "rotate-90")}
        />
        <FileCode size={14} className="text-accent" />
        <span className="font-medium">Strategy logic that ran</span>
        <span className="text-[11px] text-ink-dim">
          ({explain.name} · {explain.indicators?.length || 0} indicators)
        </span>
      </button>

      {open && (
        <div className="border-t border-line px-3 py-3 text-sm">
          {explain.description && (
            <p className="mb-3 text-ink-muted">{explain.description}</p>
          )}

          <Section title="Entry rules" icon={<ListChecks size={12} />}>
            <ul className="ml-1 list-disc space-y-1 pl-4 text-ink-muted">
              {(explain.entry_rules || []).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </Section>

          <Section title="Exit rules" icon={<ListChecks size={12} />}>
            <ul className="ml-1 list-disc space-y-1 pl-4 text-ink-muted">
              {(explain.exit_rules || []).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </Section>

          <Section title="Parameter values" icon={<Settings2 size={12} />}>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
              {paramRows.length === 0 ? (
                <span className="text-ink-dim">defaults only</span>
              ) : (
                paramRows.map((k) => (
                  <div key={k} className="font-mono text-xs">
                    <span className="text-ink-dim">{k}</span>
                    <span className="text-ink"> = {String(params[k])}</span>
                  </div>
                ))
              )}
            </div>
          </Section>

          <Section title="Indicators computed" icon={<Settings2 size={12} />}>
            <div className="flex flex-wrap gap-1">
              {(explain.indicators || []).map((ind, i) => (
                <span
                  key={i}
                  className="rounded border border-line bg-bg-panel px-2 py-0.5 font-mono text-[11px] text-ink-muted"
                >
                  {ind}
                </span>
              ))}
            </div>
          </Section>

          {fullSrc ? (
            <Section title="Full strategy source (Python)" icon={<Code2 size={12} />}>
              <pre className="max-h-[min(520px,55vh)] overflow-auto rounded border border-line bg-[#0e0e12] p-3 font-mono text-[11px] text-ink-muted">
                {fullSrc}
              </pre>
            </Section>
          ) : explain.code_snippet ? (
            <Section title="Actual on_bar() Python source" icon={<Code2 size={12} />}>
              <pre className="overflow-x-auto rounded border border-line bg-[#0e0e12] p-3 font-mono text-[11px] text-ink-muted">
                {explain.code_snippet}
              </pre>
            </Section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-ink-dim">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}
