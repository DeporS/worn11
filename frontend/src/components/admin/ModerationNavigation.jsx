import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { canAccessCatalog } from "../../utils/permissions";

const ModerationNavigation = ({ user, queueCounts }) => {
	const { t } = useTranslation();
	const showCatalog = canAccessCatalog(user);
	const kitTypeCount = queueCounts?.kit_type_suggestions_pending || 0;
	const teamCount = queueCounts?.team_verification_pending || 0;
	const reportCount = queueCounts?.kit_report_groups_pending || 0;

	const renderCount = (count) => (count > 0 ? ` (${count})` : "");

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
				{renderCount(kitTypeCount)}
			</NavLink>
			<NavLink to="/admin/teams" className={getLinkClassName("moderation")}>
				{t("moderation.nav.teamVerification")}
				{renderCount(teamCount)}
			</NavLink>
			<NavLink to="/admin/reports" className={getLinkClassName("moderation")}>
				{t("moderation.nav.kitReports")}
				{renderCount(reportCount)}
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
