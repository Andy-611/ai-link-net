/* Theme store — manages dark/light mode with localStorage persistence. */

import { create } from "zustand";

type Theme = "dark" | "light";
const STORAGE_KEY = "fp_theme";

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (stored === "dark" || stored === "light") return stored;
  } catch { /* ignore */ }
  return "light";
}

function applyTheme(theme: Theme) {
  const html = document.documentElement;
  html.classList.remove("dark", "light");
  if (theme === "dark") html.classList.add("dark");
  html.style.colorScheme = theme;
  localStorage.setItem(STORAGE_KEY, theme);
}

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

export const useThemeStore = create<ThemeState>((set, get) => {
  const initial = getInitialTheme();
  applyTheme(initial);

  return {
    theme: initial,
    toggleTheme() {
      const next = get().theme === "dark" ? "light" : "dark";
      applyTheme(next);
      set({ theme: next });
    },
    setTheme(t) {
      applyTheme(t);
      set({ theme: t });
    },
  };
});
