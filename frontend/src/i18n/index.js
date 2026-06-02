import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import pl from "./locales/pl.json";

const LANGUAGE_STORAGE_KEY = "worn11-language";
const supportedLanguages = ["en", "pl"];

const getInitialLanguage = () => {
	if (typeof window === "undefined") {
		return "en";
	}

	const savedLanguage = localStorage.getItem(LANGUAGE_STORAGE_KEY);
	if (savedLanguage && supportedLanguages.includes(savedLanguage)) {
		return savedLanguage;
	}

	return "en";
};

i18n.use(initReactI18next).init({
	resources: {
		en: { translation: en },
		pl: { translation: pl },
	},
	lng: getInitialLanguage(),
	fallbackLng: "en",
	supportedLngs: supportedLanguages,
	returnNull: false,
	interpolation: {
		escapeValue: false,
	},
});

i18n.on("languageChanged", (language) => {
	if (typeof window !== "undefined") {
		localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
	}
});

export { LANGUAGE_STORAGE_KEY };
export default i18n;
