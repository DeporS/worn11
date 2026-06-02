export function getDateLocale(language = "en") {
	return language === "pl" ? "pl-PL" : "en-GB";
}

export function formatLocalizedDate(value, language, options = {}) {
	if (!value) return "";

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return "";
	}

	return new Intl.DateTimeFormat(getDateLocale(language), {
		day: "numeric",
		month: "short",
		year: "numeric",
		...options,
	}).format(date);
}
