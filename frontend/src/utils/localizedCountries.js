export function localizeCountryName(countryName, t) {
	if (!countryName) return "";

	return t(`countries.${countryName}`, {
		defaultValue: countryName,
	});
}
