/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#F8F9FA",
        surface: "#FFFFFF",
        primary: {
          DEFAULT: "#192B52",
          50: "#EEF2F9",
          100: "#D9E2F2",
          200: "#B4C6E5",
          300: "#8FA9D7",
          400: "#6A8DC9",
          500: "#3E6BB8",
          600: "#2B529B",
          700: "#203E77",
          800: "#192B52",
          900: "#0F1C36",
          950: "#080F1E",
        },
        navy: {
          DEFAULT: "#192B52",
          light: "#263D70",
          dark: "#0F1C36",
        },
        gold: {
          DEFAULT: "#C59B27",
          light: "#E5BC48",
          dark: "#9E7B1A",
        },
        border: "#E2E8F0",
        muted: "#64748B",
        accent: "#F1F5F9",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)",
        card: "0 4px 6px -1px rgba(25, 43, 82, 0.05), 0 2px 4px -2px rgba(25, 43, 82, 0.05)",
        dropdown: "0 10px 15px -3px rgba(25, 43, 82, 0.08), 0 4px 6px -4px rgba(25, 43, 82, 0.04)",
      },
    },
  },
  plugins: [],
};
