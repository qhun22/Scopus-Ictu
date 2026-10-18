/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Single source of design tokens. Values come from Figma "Thành phần giao diện" (yctOa75eATXHnTQmesJy5A, nodes 5:2, 5:34, 9:9, 9:25, 9:41).
      // Owner policy (P12-B0): ALL RADIUS = 5px. Figma nodes 5:2/9:9/9:72/9:25/9:41 flagged FIGMA_UPDATE_REQUIRED to match.
      colors: {
        brand: { DEFAULT: "#3A5FC3", hover: "#2F4EA6", subtle: "#EBEFF9" },
        ink: { DEFAULT: "#1E293B", body: "#334155", muted: "#64748B", faint: "#94A3B8" },
        line: { DEFAULT: "#E2E8F0", strong: "#CBD5E1" },
        danger: { DEFAULT: "#E11D48", hover: "#BE123C" },
      },
      borderRadius: {
        control: "5px",
        action: "5px",
        card: "5px",
      },
      height: {
        control: "36px",
        badge: "23px",
      },
      minWidth: {
        action: "120px",
      },
    },
  },
  plugins: [],
};
