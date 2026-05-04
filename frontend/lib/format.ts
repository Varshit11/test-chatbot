export function fmtNum(n: number | undefined | null, digits = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: digits });
  return Number(n).toFixed(digits);
}

export function fmtPct(n: number | undefined | null, digits = 2): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return sign + Number(n).toFixed(digits) + "%";
}

export function fmtDate(d: string | undefined | null): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return d;
  }
}

export function colorForPct(n: number | undefined | null): string {
  if (n === undefined || n === null) return "text-ink-muted";
  if (n > 0) return "text-good";
  if (n < 0) return "text-bad";
  return "text-ink";
}
