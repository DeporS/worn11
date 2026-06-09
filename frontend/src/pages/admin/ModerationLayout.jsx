import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { canAccessModeration } from "../../utils/permissions";
import ModerationNavigation from "../../components/admin/ModerationNavigation";

const ModerationLayout = ({ user }) => {
	const { t } = useTranslation();

	if (!canAccessModeration(user)) {
		return (
			<div className="container py-5 moderation-layout">
				<div className="moderation-placeholder moderation-placeholder--denied">
					<div className="moderation-placeholder-title">
						{t("moderation.notAuthorized")}
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="container py-5 moderation-layout">
			<header className="moderation-header">
				<div>
					<h1 className="fw-bold mb-1">{t("moderation.title")}</h1>
				</div>
				<ModerationNavigation />
			</header>

			<div className="moderation-content">
				<Outlet />
			</div>
		</div>
	);
};

export default ModerationLayout;
