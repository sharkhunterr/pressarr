import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#E85D04",
          light: "#F48C06",
          dark: "#D00000",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
