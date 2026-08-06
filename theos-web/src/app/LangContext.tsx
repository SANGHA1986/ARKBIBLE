"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface LangContextType {
  lang: "KO" | "EN";
  setLang: (lang: "KO" | "EN") => void;
}

const LangContext = createContext<LangContextType>({
  lang: "KO",
  setLang: () => {},
});

const STORAGE_KEY = "ark_lang";

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<"KO" | "EN">("KO");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "KO" || saved === "EN") setLangState(saved);
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang = lang === "EN" ? "en" : "ko";
  }, [lang]);

  const setLang = (next: "KO" | "EN") => {
    setLangState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  };

  // Wait for localStorage so KO/EN never flash-mix (wrong-lang API fetch)
  if (!ready) {
    return null;
  }

  return (
    <LangContext.Provider value={{ lang, setLang }}>
      {children}
    </LangContext.Provider>
  );
}

export const useLang = () => useContext(LangContext);
