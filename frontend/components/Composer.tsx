"use client";

import { useEffect, useRef } from "react";
import { ArrowUp } from "lucide-react";
import clsx from "clsx";

export function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  variant = "footer",
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  placeholder?: string;
  /** `hero`: larger, centered chip like a clean chat starting point */
  variant?: "footer" | "hero";
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = Math.min(ref.current.scrollHeight, 200) + "px";
    }
  }, [value]);

  const isHero = variant === "hero";

  return (
    <div
      className={clsx(
        "backdrop-blur",
        isHero
          ? "border-0 px-4 py-2"
          : "border-t border-line/60 bg-bg-panel/80 px-4 py-3"
      )}
    >
      <div className={clsx("mx-auto", isHero ? "max-w-2xl" : "max-w-4xl")}>
        <div
          className={clsx(
            "flex items-end gap-2 border bg-bg-elev/80 p-2.5 ring-1 ring-transparent transition-all focus-within:ring-violet-500/40",
            isHero
              ? "rounded-2xl border-violet-500/25 shadow-[0_8px_40px_-12px_rgba(139,92,246,0.35)] focus-within:border-violet-500/40"
              : "rounded-xl border-line"
          )}
        >
          <textarea
            ref={ref}
            rows={isHero ? 2 : 1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!disabled && value.trim()) onSubmit();
              }
            }}
            disabled={disabled}
            placeholder={
              placeholder ||
              (isHero
                ? "Describe entry & exit in plain English…"
                : "Describe a strategy, e.g. 'EMA 9/21 cross on XAUUSD 5m with ADX > 20 filter'")
            }
            className={clsx(
              "flex-1 resize-none bg-transparent px-2 py-1.5 leading-relaxed text-ink outline-none placeholder:text-ink-dim disabled:opacity-60",
              isHero ? "min-h-[56px] text-[15px]" : "text-[14px]"
            )}
          />
          <button
            type="button"
            onClick={onSubmit}
            disabled={disabled || !value.trim()}
            aria-label="Send"
            className={clsx(
              "tx-send-btn flex shrink-0 items-center justify-center rounded-xl text-white disabled:cursor-not-allowed",
              isHero ? "h-10 w-10" : "h-8 w-8"
            )}
          >
            <ArrowUp size={isHero ? 18 : 15} strokeWidth={2.25} />
          </button>
        </div>
      </div>
    </div>
  );
}
