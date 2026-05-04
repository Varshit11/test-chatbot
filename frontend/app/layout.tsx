import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TradeXpert.ai — Strategy Studio",
  description:
    "Build, backtest, optimize and AI-filter trading strategies in plain English.",
};

/**
 * Tailwind is served from `/quantflow-tw.css` (built from `app/tw-source.css`)
 * so utilities load even when the Next.js CSS chunk pipeline misbehaves in dev.
 * Run `npm run build:tw` after changing Tailwind config or class names in source.
 */
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" style={{ backgroundColor: "#000" }}>
      <head>
        <link rel="stylesheet" href="/quantflow-tw.css" />
      </head>
      <body
        style={{ backgroundColor: "#000", color: "#f4f4f6", margin: 0 }}
        className="font-sans"
      >
        {children}
      </body>
    </html>
  );
}
