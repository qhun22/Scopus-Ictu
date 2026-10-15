import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "light",
  toggleTheme: () => {},
});

// CSS vars injected at runtime — no Tailwind dark: rebuild needed
const DARK_STYLE_ID = "scopus-dark-theme";
const DARK_CSS = `
  :root.dark {
    color-scheme: dark;
  }
  .dark body,
  .dark #root {
    background-color: #0f172a;
    color: #e2e8f0;
  }
  /* AppLayout bg */
  .dark .min-h-screen {
    background-color: #0f172a !important;
    color: #e2e8f0 !important;
  }
  /* Header */
  .dark header {
    background-color: rgba(15,23,42,0.97) !important;
    border-bottom-color: rgba(51,65,85,0.8) !important;
  }
  .dark header h2 {
    color: #f1f5f9 !important;
  }
  .dark header button {
    border-color: #334155;
    background-color: #1e293b;
    color: #94a3b8;
  }
  .dark header button:hover {
    background-color: #334155;
    color: #f1f5f9;
  }
  /* Language switcher active button keeps brand blue */
  .dark header button[aria-label*="đang chọn"],
  .dark header button[aria-label*="selected"] {
    background-color: #3A5FC3 !important;
    color: #fff !important;
  }
  /* User dropdown trigger */
  .dark header .bg-slate-50\\/70 {
    background-color: #1e293b !important;
    border-color: #334155 !important;
    color: #cbd5e1 !important;
  }
  .dark header .text-slate-800 { color: #f1f5f9 !important; }
  .dark header .text-slate-500 { color: #94a3b8 !important; }
  /* Sidebar */
  .dark aside {
    background-color: #0f172a !important;
    border-right-color: rgba(51,65,85,0.8) !important;
  }
  /* Sidebar brand border */
  .dark aside > div:first-child {
    border-bottom-color: rgba(51,65,85,0.8) !important;
  }
  /* Sidebar nav text */
  .dark aside a {
    color: #94a3b8 !important;
  }
  .dark aside a:hover {
    background-color: #1e293b !important;
    color: #f1f5f9 !important;
  }
  /* Sidebar active item */
  .dark aside a[aria-current="page"],
  .dark aside a.active {
    background-color: rgba(58,95,195,0.2) !important;
    color: #93b4f0 !important;
  }
  /* Sidebar group heading */
  .dark aside p.text-\\[10px\\] {
    color: #475569 !important;
  }
  /* Sidebar group divider */
  .dark aside .border-t {
    border-top-color: #1e293b !important;
  }
  /* Sidebar version badge */
  .dark aside .text-slate-400 { color: #475569 !important; }
  /* Main content area */
  .dark main {
    background-color: #0f172a !important;
  }
  /* Cards / white surfaces */
  .dark .bg-white {
    background-color: #1e293b !important;
    border-color: #334155 !important;
  }
  .dark .bg-slate-50,
  .dark .bg-slate-50\\/70,
  .dark .bg-\\[\\#f4f6fb\\] {
    background-color: #1e293b !important;
  }
  .dark .border-slate-200,
  .dark .border-slate-200\\/80 {
    border-color: #334155 !important;
  }
  /* Text colors */
  .dark .text-slate-800 { color: #f1f5f9 !important; }
  .dark .text-slate-700 { color: #cbd5e1 !important; }
  .dark .text-slate-600 { color: #94a3b8 !important; }
  .dark .text-slate-500 { color: #64748b !important; }
  .dark .text-slate-400 { color: #475569 !important; }
  /* Page overlay loading */
  .dark [data-testid="first-visit-loading"] {
    background-color: rgba(15,23,42,0.85) !important;
  }
  .dark [data-testid="first-visit-loading"] p {
    color: #94a3b8 !important;
  }
`;

function injectDarkCSS() {
  if (!document.getElementById(DARK_STYLE_ID)) {
    const style = document.createElement("style");
    style.id = DARK_STYLE_ID;
    style.textContent = DARK_CSS;
    document.head.appendChild(style);
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem("scopus-theme") as Theme | null;
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    injectDarkCSS();
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    localStorage.setItem("scopus-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((prev) => (prev === "light" ? "dark" : "light"));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
