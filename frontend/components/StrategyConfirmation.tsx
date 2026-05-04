"use client";

import { useState } from "react";
import clsx from "clsx";
import { Edit3, Play, ChevronDown, Code2 } from "lucide-react";
import type { ParsedStrategy } from "@/lib/types";

export function StrategyConfirmation({
  parsed,
  onAction,
  busy,
}: {
  parsed: ParsedStrategy;
  onAction: (id: string, payload?: Record<string, any>) => void;
  busy?: string | null;
}) {
  const [editing, setEditing] = useState(false);
  const [params, setParams] = useState<Record<string, any>>({ ...parsed.parameters });
  const [instrument, setInstrument] = useState(parsed.instrument);
  const [timeframe, setTimeframe] = useState(parsed.timeframe);
  const [sourceOpen, setSourceOpen] = useState(false);

  const dr = (parsed as any).date_range;
  const rangeLabel =
    dr && dr.type === "relative" && dr.value
      ? `Past ${dr.value} ${dr.unit}${dr.value > 1 && !String(dr.unit).endsWith("s") ? "s" : ""}`
      : "Full history";

  // Title prefers the human label; never falls back to internal template names.
  const humanizeTemplate = (t?: string) =>
    (t || "Strategy")
      .replace(/^custom_/, "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (m) => m.toUpperCase());
  const stratTitle =
    (parsed.strategy_label && parsed.strategy_label.trim()) ||
    humanizeTemplate(parsed.template);
  const genSrc = parsed.generated_python?.trim();
  const isGenerated = parsed.implementation_mode === "generated_class" && !!genSrc;

  return (
    <div className="rounded-lg border border-line bg-bg-elev p-4">
      <div className="mb-3 grid grid-cols-3 gap-3 text-xs">
        <Info label="Strategy" value={stratTitle} />
        <Info label="Instrument" value={`${instrument} · ${timeframe}`} />
        <Info label="Date range" value={rangeLabel} />
      </div>

      {(parsed as any).chart?.type === "renko" && (
        <div className="mb-3 rounded-md border border-violet-900/40 bg-violet-950/25 px-3 py-2 text-[11px] text-violet-100">
          <span className="font-semibold">Chart:</span> Renko ({String((parsed as any).chart.mode || "wicks")}
          {(parsed as any).chart.brick_size != null
            ? `, brick ${(parsed as any).chart.brick_size}`
            : ", automatic brick size"}
          ).
        </div>
      )}

      <SectionTitle>Entry rules</SectionTitle>
      <ul className="mb-3 ml-4 list-disc text-sm text-ink-muted marker:text-ink-dim">
        {(parsed.entry_rules || []).map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <SectionTitle>Exit rules</SectionTitle>
      <ul className="mb-3 ml-4 list-disc text-sm text-ink-muted marker:text-ink-dim">
        {(parsed.exit_rules || []).map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>

      <SectionTitle>Indicators</SectionTitle>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {(parsed.indicators_used || []).map((i) => (
          <span
            key={i}
            className="rounded-md border border-line bg-bg-panel px-2 py-0.5 font-mono text-[11px] text-ink-muted"
          >
            {i}
          </span>
        ))}
      </div>

      {isGenerated && genSrc && (
        <>
          <button
            type="button"
            onClick={() => setSourceOpen((v) => !v)}
            className="mb-1 flex w-full items-center gap-2 text-left text-[10px] uppercase tracking-wide text-ink-dim hover:text-ink-muted"
          >
            <ChevronDown
              size={14}
              className={clsx("text-ink-muted transition-transform", sourceOpen && "rotate-180")}
            />
            <Code2 size={12} className="text-accent" />
            View strategy code
          </button>
          {sourceOpen && (
            <pre className="mb-4 max-h-[min(420px,50vh)] overflow-auto rounded border border-line bg-[#0e0e12] p-3 font-mono text-[11px] leading-relaxed text-ink-muted">
              {genSrc}
            </pre>
          )}
        </>
      )}

      <SectionTitle>Parameters</SectionTitle>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {Object.entries(params).map(([k, v]) => (
          <div
            key={k}
            className="rounded-md border border-line bg-bg-panel px-3 py-2"
          >
            <div className="text-[10px] uppercase tracking-wide text-ink-dim">
              {k}
            </div>
            {editing && (typeof v === "number" || typeof v === "boolean") ? (
              typeof v === "boolean" ? (
                <button
                  onClick={() =>
                    setParams((p) => ({ ...p, [k]: !p[k] }))
                  }
                  className={clsx(
                    "mt-1 rounded px-2 py-0.5 text-xs",
                    params[k] ? "bg-good/30 text-good" : "bg-zinc-700 text-zinc-300"
                  )}
                >
                  {String(params[k])}
                </button>
              ) : (
                <input
                  type="number"
                  value={params[k] ?? ""}
                  onChange={(e) =>
                    setParams((p) => ({
                      ...p,
                      [k]: Number.isInteger(v) ? parseInt(e.target.value || "0", 10) : parseFloat(e.target.value || "0"),
                    }))
                  }
                  className="mt-1 w-full bg-transparent font-mono text-sm text-ink outline-none"
                />
              )
            ) : (
              <div className="font-mono text-sm text-ink">{String(v)}</div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          disabled={!!busy}
          onClick={() => {
            if (editing) {
              setEditing(false);
              onAction("edit_params", { parameters: params, instrument, timeframe });
            } else {
              onAction("confirm");
            }
          }}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-accent-dim disabled:opacity-50"
        >
          {busy === "confirm" || busy === "edit_params" ? (
            <span className="inline-flex items-center">
              <span className="mr-1.5 h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
              Running backtest…
            </span>
          ) : editing ? (
            <>
              <Play size={13} /> Apply &amp; Run Backtest
            </>
          ) : (
            <>
              <Play size={13} /> Run Backtest
            </>
          )}
        </button>
        <button
          disabled={!!busy}
          onClick={() => setEditing((e) => !e)}
          className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg-panel px-3 py-1.5 text-sm text-ink-muted hover:bg-[#1c1c22] hover:text-ink disabled:opacity-50"
        >
          <Edit3 size={13} /> {editing ? "Cancel" : "Edit Parameters"}
        </button>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-ink-dim">
        {label}
      </div>
      <div className="text-sm text-ink">{value}</div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-dim">
      {children}
    </div>
  );
}
