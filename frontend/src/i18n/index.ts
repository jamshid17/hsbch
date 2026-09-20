import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en";
import uz from "./locales/uz";
import ru from "./locales/ru";


/**
 * The language to open in, when nothing has been chosen yet.
 *
 * Telegram knows which language the person reads, so asking again buys
 * nothing. Read off `window.Telegram` — set by the script tag in index.html
 * — rather than through the SDK module: this file is imported by the api
 * client, which is imported by everything, and dragging the whole Telegram
 * SDK down that path makes the most basic piece of the app, turning a failed
 * response into a sentence, depend on a browser being present.
 */
function preferredLanguage(supported: string[], fallback: string): string {
  const tg = (
    globalThis as {
      Telegram?: {
        WebApp?: { initDataUnsafe?: { user?: { language_code?: string } } };
      };
    }
  ).Telegram;
  const base = (tg?.WebApp?.initDataUnsafe?.user?.language_code ?? "")
    .toLowerCase()
    .split("-")[0];
  return supported.includes(base) ? base : fallback;
}

const SUPPORTED = ["uz", "ru", "en"];
const DEFAULT_LANG = "uz";

// A private window, or blocked site data, makes this throw rather than
// return null — and a language preference is never worth an exception.
let saved: string | null = null;
try {
  saved = localStorage.getItem("lang");
} catch {
  /* no stored preference */
}
const lng =
  saved && SUPPORTED.includes(saved)
    ? saved
    : preferredLanguage(SUPPORTED, DEFAULT_LANG);

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    uz: { translation: uz },
    ru: { translation: ru },
  },
  lng,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
