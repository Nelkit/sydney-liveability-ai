import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Legacy (keep for backward compat)
        slateBg: "#f4f6fb",
        slateSurface: "#f0f2f8",
        slateBorder: "#e2e5ef",
        slateText: "#0f1629",
        slateMuted: "#7a85a3",
        brandBlue: "#2563eb",

        // Design system
        bg: {
          DEFAULT: "oklch(0.992 0.002 250)",
          elev: "oklch(0.975 0.004 250)",
        },
        fg: {
          DEFAULT: "oklch(0.18 0.01 250)",
          muted: "oklch(0.55 0.012 250)",
        },
        border: {
          DEFAULT: "oklch(0.92 0.005 250)",
        },
        accent: {
          DEFAULT: "oklch(0.55 0.18 285)",
          soft: "oklch(0.95 0.04 285)",
        },
        accentB: {
          DEFAULT: "oklch(0.62 0.16 75)",
        },
        cat: {
          crime: "oklch(0.55 0.18 25)",
          gis: "oklch(0.55 0.16 235)",
          sentiment: "oklch(0.55 0.16 75)",
          comparator: "oklch(0.55 0.18 285)",
        },
        sent: {
          pos: "oklch(0.55 0.16 145)",
          neu: "oklch(0.65 0.02 250)",
          neg: "oklch(0.55 0.18 25)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,.06),0 4px 16px rgba(0,0,0,.06)",
        cardLg: "0 8px 32px rgba(0,0,0,.12)",
        float: "0 1px 2px rgba(0,0,0,0.04)",
        floatLg: "0 2px 8px rgba(0,0,0,0.05)",
      },
      borderRadius: {
        xl2: "16px",
      },
    },
  },
  plugins: [],
};

export default config;
