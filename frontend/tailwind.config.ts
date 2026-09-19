import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: "#06080d",
          secondary: "#090d16",
          elevated: "#0f1422",
        },
        glass: {
          surface: "rgba(11, 16, 28, 0.62)",
          panel: "rgba(13, 19, 33, 0.70)",
          elevated: "rgba(18, 25, 44, 0.85)",
          nav: "rgba(10, 15, 26, 0.75)",
          border: "rgba(255, 255, 255, 0.07)",
          "border-focus": "rgba(255, 255, 255, 0.16)",
          highlight: "rgba(255, 255, 255, 0.10)",
          hover: "rgba(22, 31, 54, 0.65)",
        },
        threat: {
          low: "#10B981",       // Emerald
          medium: "#F59E0B",    // Amber
          high: "#F97316",      // Orange
          critical: "#EF4444",  // Crimson
        },
        cyber: {
          cyan: "#06B6D4",
          teal: "#14B8A6",
          blue: "#3B82F6",
          indigo: "#6366F1",
          emerald: "#10B981",
        }
      },
      backdropBlur: {
        xs: "2px",
        glass: "18px",
        xl: "24px",
      },
      boxShadow: {
        "glass-nav": "0 20px 40px -15px rgba(0, 0, 0, 0.7), inset 0 1px 1px 0 rgba(255, 255, 255, 0.14)",
        "glass-panel": "0 16px 36px -8px rgba(0, 0, 0, 0.55), inset 0 1px 0 0 rgba(255, 255, 255, 0.09)",
        "glass-card": "0 8px 24px -4px rgba(0, 0, 0, 0.45), inset 0 1px 0 0 rgba(255, 255, 255, 0.08)",
        "glass-elevated": "0 20px 48px -10px rgba(0, 0, 0, 0.75), inset 0 1px 1px 0 rgba(255, 255, 255, 0.18)",
        "glass-glow": "0 0 24px -2px rgba(6, 182, 212, 0.15)",
        "status-glow": "0 0 12px 1px rgba(16, 185, 129, 0.35)",
        "threat-glow": "0 0 28px -4px rgba(239, 68, 68, 0.25)",
      },
      keyframes: {
        fadeSlide: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.65', transform: 'scale(0.95)' },
        },
      },
      animation: {
        'fade-slide': 'fadeSlide 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-glow': 'pulseGlow 2.5s ease-in-out infinite',
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
