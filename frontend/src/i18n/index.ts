import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en";
import uz from "./locales/uz";
import ru from "./locales/ru";

import { preferredLanguage } from "../telegram";

const SUPPORTED = ["uz", "ru", "en"];
const DEFAULT_LANG = "uz";

const saved = localStorage.getItem("lang");
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
