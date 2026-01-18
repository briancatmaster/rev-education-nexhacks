import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0a0f1f",
        muted: "#5a667a",
        cream: "#f4f1e9",
        peach: "#d5dde6",
        amber: "#f4b04a",
        teal: "#0f6b8f",
        paper: "#fbfaf7",
        cobalt: "#1b2a8a",
        lime: "#c7f36b",
      },
      fontFamily: {
        serif: ["var(--font-newsreader)", "Times New Roman", "serif"],
        sans: ["var(--font-spline)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        float: "0 30px 70px rgba(10, 15, 31, 0.2)",
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
        shimmer: {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "100% 50%" },
        },
      },
      animation: {
        float: "float 5s ease-in-out infinite",
        spinSlow: "spinSlow 18s linear infinite",
        rise: "rise 0.8s ease-out both",
        shimmer: "shimmer 10s ease infinite",
      },
      backgroundImage: {
        hero: "radial-gradient(circle at top, #f9fbff 0%, #eef2f5 45%, #d9e1ea 100%)",
        nebula:
          "linear-gradient(120deg, rgba(27,42,138,0.18), rgba(199,243,107,0.2), rgba(10,15,31,0.08))",
      },
    },
  },
  plugins: [],
}

export default config
