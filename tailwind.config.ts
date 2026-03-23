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
        // AMARA OS Dark Command Palette
        void: "#050508",
        abyss: "#080b12",
        surface: "#0d1117",
        panel: "#111827",
        border: "#1f2937",
        // Accent System
        signal: "#00d4ff",       // primary cyan signal
        amber: "#f59e0b",        // deal / alert amber
        green: "#10b981",        // confirmed / active
        red: "#ef4444",          // reject / danger
        violet: "#7c3aed",       // AI / intelligence
        gold: "#fbbf24",         // high-value
        // Text hierarchy
        "text-primary": "#f1f5f9",
        "text-secondary": "#94a3b8",
        "text-muted": "#475569",
        "text-ghost": "#1e293b",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "monospace"],
        display: ["'Inter'", "sans-serif"],
      },
      backgroundImage: {
        "void-gradient": "linear-gradient(135deg, #050508 0%, #080b12 50%, #0d1117 100%)",
        "panel-gradient": "linear-gradient(135deg, rgba(13,17,23,0.95) 0%, rgba(17,24,39,0.95) 100%)",
        "signal-glow": "radial-gradient(ellipse at center, rgba(0,212,255,0.1) 0%, transparent 70%)",
        "deal-glow": "radial-gradient(ellipse at center, rgba(16,185,129,0.08) 0%, transparent 70%)",
        "grid-pattern": "linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)",
      },
      boxShadow: {
        "signal": "0 0 20px rgba(0,212,255,0.15), 0 0 40px rgba(0,212,255,0.05)",
        "deal": "0 0 20px rgba(16,185,129,0.15), 0 0 40px rgba(16,185,129,0.05)",
        "amber": "0 0 20px rgba(245,158,11,0.15)",
        "panel": "0 4px 24px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)",
        "glass": "0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "scan": "scan 4s linear infinite",
        "flicker": "flicker 8s linear infinite",
        "glow-pulse": "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)", opacity: "0" },
          "10%": { opacity: "0.5" },
          "90%": { opacity: "0.5" },
          "100%": { transform: "translateY(100vh)", opacity: "0" },
        },
        flicker: {
          "0%, 97%, 100%": { opacity: "1" },
          "97.5%": { opacity: "0.8" },
          "98%": { opacity: "0.95" },
          "98.5%": { opacity: "0.7" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(0,212,255,0.1)" },
          "50%": { boxShadow: "0 0 40px rgba(0,212,255,0.3), 0 0 80px rgba(0,212,255,0.1)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
