/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#000000",
          panel: "#0d0d10",
          elev: "#15151a",
        },
        line: "#23232a",
        ink: {
          DEFAULT: "#e7e7ea",
          muted: "#9aa0aa",
          dim: "#6b7180",
        },
        accent: {
          DEFAULT: "#8b5cf6",
          dim: "#7c3aed",
          glow: "#a855f7",
          alt: "#d946ef",
        },
        good: "#22c55e",
        bad: "#ef4444",
        warn: "#f59e0b",
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
        display: ["var(--font-display)", "Georgia", "Times New Roman", "serif"],
      },
      animation: {
        "pulse-soft": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-up": "fadeUp 240ms ease-out",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
