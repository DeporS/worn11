import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { canAccessCatalog } from "../../utils/permissions";

const ModerationNavigation = ({ user }) => {
	const { t } = useTranslation();
	const showCatalog = canAccessCatalog(user);

	const getLinkClassName = (variant) => ({ isActive }) =>
		[
			"moderation-navigation-link",
			`moderation-navigation-link--${variant}`,
			isActive ? "moderation-navigation-link-active" : "",
		]
			.filter(Boolean)
			.join(" ");

	return (
		<nav className="moderation-navigation" aria-label={t("moderation.title")}>
			<NavLink to="/admin/kit-types" className={getLinkClassName("moderation")}>
				{t("moderation.nav.kitTypes")}
			</NavLink>
			<NavLink to="/admin/teams" className={getLinkClassName("moderation")}>
				{t("moderation.nav.teamVerification")}
			</NavLink>
			<NavLink to="/admin/reports" className={getLinkClassName("moderation")}>
				{t("moderation.nav.kitReports")}
			</NavLink>
			{showCatalog ? (
				<>
					<span className="moderation-navigation-spacer" aria-hidden="true" />
					<NavLink
						to="/admin/catalog/countries"
						className={getLinkClassName("catalog")}
					>
						{t("moderation.nav.countries")}
					</NavLink>
					<NavLink
						to="/admin/catalog/leagues"
						className={getLinkClassName("catalog")}
					>
						{t("moderation.nav.leagues")}
					</NavLink>
					<NavLink
						to="/admin/catalog/teams"
						className={getLinkClassName("catalog")}
					>
						{t("moderation.nav.officialTeams")}
					</NavLink>
				</>
			) : null}
		</nav>
	);
};

export default ModerationNavigation;
