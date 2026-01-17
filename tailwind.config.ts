import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0b1020",
        muted: "#5b6575",
        cream: "#eef2f5",
        peach: "#c9d7e1",
        amber: "#f0a25a",
        teal: "#1f6f6e",
        paper: "#f9fbfc",
      },
      fontFamily: {
        serif: ["var(--font-newsreader)", "Times New Roman", "serif"],
        sans: ["var(--font-spline)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        float: "0 28px 60px rgba(11, 16, 32, 0.16)",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-14px)" },
        },
        spinSlow: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        rise: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        spinSlow: "spinSlow 18s linear infinite",
        rise: "rise 0.8s ease-out both",
      },
      backgroundImage: {
        hero: "radial-gradient(circle at top, #f9fbfc 0%, #eef2f5 45%, #dde6ee 100%)",
      },
    },
  },
  plugins: [],
}

export default config
