import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import LanguageTransitionOverlay from "../components/common/LanguageTransitionOverlay";
import { en } from "./locales/en";
import { vi } from "./locales/vi";
import { Locale, TranslationSchema } from "./types";

const LOCALE_STORAGE_KEY = "locale";
const TRANSITION_DURATION_MS = 3000;

interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  switchLanguage: (locale: Locale) => void;
  isLanguageSwitching: boolean;
  pendingLocale: Locale | null;
  t: TranslationSchema;
  getRoleLabel: (role?: string, withCode?: boolean) => string;
}

const translations: Record<Locale, TranslationSchema> = {
  vi,
  en,
};

const I18nContext = createContext<I18nContextType | null>(null);

function getInitialLocale(): Locale {
  try {
    const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved === "en" || saved === "vi") {
      return saved;
    }
  } catch {
    // ignore storage errors
  }
  return "vi"; // Default locale
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);
  const [isLanguageSwitching, setIsLanguageSwitching] = useState<boolean>(false);
  const [pendingLocale, setPendingLocale] = useState<Locale | null>(null);
  const timeoutRef = useRef<number | null>(null);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Update document lang attribute when locale changes
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const switchLanguage = (newLocale: Locale) => {
    if (newLocale === locale || isLanguageSwitching) {
      return;
    }

    setIsLanguageSwitching(true);
    setPendingLocale(newLocale);

    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = window.setTimeout(() => {
      setLocaleState(newLocale);
      try {
        localStorage.setItem(LOCALE_STORAGE_KEY, newLocale);
      } catch {
        // ignore storage errors
      }
      setIsLanguageSwitching(false);
      setPendingLocale(null);
      timeoutRef.current = null;
    }, TRANSITION_DURATION_MS);
  };

  // Immediate or transitioned setter
  const setLocale = (newLocale: Locale) => {
    switchLanguage(newLocale);
  };

  const currentTranslations = translations[locale] || translations.vi;

  const getRoleLabel = (role?: string, withCode = false): string => {
    const r = role?.toUpperCase() || "";
    if (r === "ADMIN") {
      return withCode
        ? currentTranslations.roles.ADMIN_WITH_CODE
        : currentTranslations.roles.ADMIN;
    }
    if (r === "REVIEWER") {
      return withCode
        ? currentTranslations.roles.REVIEWER_WITH_CODE
        : currentTranslations.roles.REVIEWER;
    }
    if (r === "LECTURER") {
      return withCode
        ? currentTranslations.roles.LECTURER_WITH_CODE
        : currentTranslations.roles.LECTURER;
    }
    if (r === "ALL") {
      return currentTranslations.roles.ALL;
    }
    return role || "";
  };

  return (
    <I18nContext.Provider
      value={{
        locale,
        setLocale,
        switchLanguage,
        isLanguageSwitching,
        pendingLocale,
        t: currentTranslations,
        getRoleLabel,
      }}
    >
      {children}
      {/* Global 3-second transition overlay */}
      <LanguageTransitionOverlay
        isVisible={isLanguageSwitching}
        pendingLocale={pendingLocale}
      />
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextType {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return context;
}
