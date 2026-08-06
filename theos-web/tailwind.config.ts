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
        ark: {
          brown: "#B36B00",
          gold: "#D4A017",
          navy: "#0D1B2A",
          grey: "#687280",
          bg: "#FAF8F5",
          white: "#FFFFFF",
        },
      },
      fontFamily: {
        serif: ['"Noto Serif KR"', '"Playfair Display"', "Georgia", "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
      keyframes: {
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        marquee: "marquee 40s linear infinite",
      },
      boxShadow: {
        soft: "0 8px 30px rgba(13, 27, 42, 0.06)",
        card: "0 4px 20px rgba(13, 27, 42, 0.08)",
      },
    },
  },
  plugins: [],
};
export default config;
