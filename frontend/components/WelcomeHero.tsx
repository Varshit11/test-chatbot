"use client";

import { useEffect, useRef } from "react";
import { Plus, ArrowUp } from "lucide-react";
import { TradeXpertLogo } from "./TradeXpertLogo";

const QUICK_CHIPS: { label: string; prompt: string }[] = [
  {
    label: "EMA crossover + RSI filter",
    prompt:
      "EMA 9 / 21 crossover on XAUUSD 5m with an RSI(14) filter — only take longs when RSI > 50 and shorts when RSI < 50",
  },
  {
    label: "Bollinger Band mean reversion",
    prompt:
      "Bollinger Bands 20 / 2 mean reversion on XAUUSD 15m — buy when price tags lower band, sell when it tags upper band, ATR stop",
  },
  {
    label: "MACD momentum with volume",
    prompt:
      "MACD 12 26 9 momentum strategy on XAUUSD 15m, only enter when volume is above its 20-bar average",
  },
];

export function WelcomeHero({
  value,
  onChange,
  onSubmit,
  disabled,
  onPickPrompt,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  onPickPrompt: (text: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 160) + "px";
    }
  }, [value]);

  return (
    <div className="flex min-h-[78vh] flex-col items-center justify-center px-6 py-12">
      <div className="mb-5 flex items-center gap-4">
        <TradeXpertLogo size={52} />
        <h1 className="bg-gradient-to-r from-white via-white to-violet-300 bg-clip-text text-[44px] font-semibold leading-none tracking-tight text-transparent sm:text-[52px]">
          TradeXpert.ai
        </h1>
      </div>

      <p className="mb-10 max-w-xl text-center text-[15px] leading-relaxed text-white/55">
        Turn ideas into tested strategies. Describe entries and exits in plain
        English, run real backtests, then sharpen edge with{" "}
        <span className="font-medium text-white/85">Strategy Finder</span> and the{" "}
        <span className="font-medium text-white/85">AI Filter</span>.
      </p>

      <div className="w-full max-w-3xl">
        <div className="rounded-2xl border border-white/[0.08] bg-[#1a1a22] px-4 py-3 shadow-[0_18px_60px_-20px_rgba(0,0,0,0.6)] transition-colors focus-within:border-violet-500/40">
          <textarea
            ref={ref}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!disabled && value.trim()) onSubmit();
              }
            }}
            disabled={disabled}
            placeholder="Describe your trading strategy…"
            className="block w-full resize-none bg-transparent py-1.5 text-[15px] leading-relaxed text-white outline-none placeholder:text-white/40 disabled:opacity-60"
          />
          <div className="mt-2 flex items-center justify-between">
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-white/[0.06] text-white/70 transition-colors hover:bg-white/[0.10] hover:text-white"
              aria-label="Attach"
              title="Attach"
            >
              <Plus size={15} strokeWidth={1.75} />
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={disabled || !value.trim()}
              aria-label="Send"
              className="tx-send-btn flex h-8 w-8 items-center justify-center rounded-full text-white disabled:cursor-not-allowed"
            >
              <ArrowUp size={16} strokeWidth={2.25} />
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
          {QUICK_CHIPS.map((c) => (
            <button
              key={c.label}
              type="button"
              onClick={() => onPickPrompt(c.prompt)}
              className="rounded-full bg-gradient-to-r from-violet-900/45 via-violet-800/40 to-fuchsia-900/45 px-5 py-2.5 text-[13px] font-medium text-white/90 ring-1 ring-violet-500/25 transition-all hover:-translate-y-0.5 hover:from-violet-800/55 hover:to-fuchsia-800/55 hover:text-white hover:ring-violet-400/40"
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
