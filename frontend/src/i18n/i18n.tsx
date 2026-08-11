import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Language = {
  code: string;
  label: string;
  native: string;
  flag: string;
  dir: "ltr" | "rtl";
  locale: string;
};

type CatalogResponse = {
  locale: string;
  metadata: { dir: "ltr" | "rtl"; locale: string };
  messages: Record<string, string>;
};

type I18nContextValue = {
  language: string;
  languages: Language[];
  t: (key: string, values?: Record<string, string | number>) => string;
  setLanguage: (language: string) => Promise<void>;
};

const LANGUAGE_KEY = "prunin_language";

const I18nContext = createContext<I18nContextValue | null>(null);

function interpolate(value: string, values: Record<string, string | number> = {}): string {
  return Object.entries(values).reduce(
    (result, [key, replacement]) => result.replaceAll(`{${key}}`, String(replacement)),
    value
  );
}

async function loadLanguages(): Promise<Language[]> {
  const response = await fetch("/api/i18n/languages", { cache: "no-store" });
  const payload = await response.json();
  return payload.languages || [];
}

async function loadCatalog(language: string): Promise<CatalogResponse> {
  const response = await fetch(`/api/i18n/catalog/${encodeURIComponent(language)}`, { cache: "no-store" });
  return response.json();
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setCurrentLanguage] = useState(localStorage.getItem(LANGUAGE_KEY) || "es");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [messages, setMessages] = useState<Record<string, string>>({});

  const setLanguage = useCallback(async (nextLanguage: string) => {
    const catalog = await loadCatalog(nextLanguage);
    setCurrentLanguage(catalog.locale);
    setMessages(catalog.messages || {});
    localStorage.setItem(LANGUAGE_KEY, catalog.locale);
    document.documentElement.lang = catalog.locale;
    document.documentElement.dir = catalog.metadata?.dir || "ltr";
  }, []);

  useEffect(() => {
    loadLanguages()
      .then(setLanguages)
      .then(() => setLanguage(language))
      .catch(() => setLanguage("es"));
  }, [language, setLanguage]);

  const value = useMemo<I18nContextValue>(() => ({
    language,
    languages,
    t: (key, values) => interpolate(messages[key] || key, values),
    setLanguage
  }), [language, languages, messages, setLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}
