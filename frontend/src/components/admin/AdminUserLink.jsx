import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

const AdminUserLink = ({
	username,
	displayName,
	className = "",
	fallback,
	title,
	ariaLabel,
}) => {
	const { t } = useTranslation();
	const resolvedUsername = (username || "").trim();
	if (!resolvedUsername) {
		return (
			<span className={className.trim()}>
				{fallback || t("moderation.reports.unknownUser")}
			</span>
		);
	}

	const resolvedLabel = displayName ?? resolvedUsername;
	const resolvedTitle = title || t("nav.viewProfile");
	const resolvedAriaLabel = ariaLabel || resolvedTitle;

	return (
		<Link
			to={`/profile/${resolvedUsername}`}
			className={`admin-user-link ${className}`.trim()}
			title={resolvedTitle}
			aria-label={resolvedAriaLabel}
			onClick={(event) => event.stopPropagation()}
		>
			{resolvedLabel}
		</Link>
	);
};

export default AdminUserLink;
