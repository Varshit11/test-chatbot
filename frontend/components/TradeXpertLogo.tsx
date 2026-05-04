"use client";

/** Stylised "X" brand mark with a subtle white-to-violet gradient. */
export function TradeXpertLogo({
  size = 28,
  className,
}: {
  size?: number;
  className?: string;
}) {
  // Per-instance gradient ID so multiple logos on the page don't collide.
  const gid = `tx-x-grad-${Math.round(size)}`;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id={gid} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="55%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#c4b5fd" />
        </linearGradient>
      </defs>
      <polygon points="3.5,4 12,4 28.5,28 20,28" fill={`url(#${gid})`} />
      <polygon points="20,4 28.5,4 12,28 3.5,28" fill={`url(#${gid})`} />
    </svg>
  );
}
