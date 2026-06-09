import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";

const ModerationNavigation = () => {
	const { t } = useTranslation();

	const getLinkClassName = ({ isActive }) =>
		`moderation-navigation-link ${isActive ? "moderation-navigation-link-active" : ""}`;

	return (
		<nav className="moderation-navigation" aria-label={t("moderation.title")}>
			<NavLink to="/admin/kit-types" className={getLinkClassName}>
				{t("moderation.navigation.kitTypes")}
			</NavLink>
			<NavLink to="/admin/teams" className={getLinkClassName}>
				{t("moderation.navigation.teams")}
			</NavLink>
			<NavLink to="/admin/reports" className={getLinkClassName}>
				{t("moderation.navigation.reports")}
			</NavLink>
		</nav>
	);
};

export default ModerationNavigation;
