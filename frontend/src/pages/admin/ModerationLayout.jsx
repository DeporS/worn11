import { useCallback, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { canAccessModeration } from "../../utils/permissions";
import ModerationNavigation from "../../components/admin/ModerationNavigation";
import { getAdminModerationSummary } from "../../services/api";

const ModerationLayout = ({ user }) => {
	const { t } = useTranslation();
	const [queueCounts, setQueueCounts] = useState(null);
	const canAccess = canAccessModeration(user);

	const refreshModerationSummary = useCallback(async () => {
		try {
			const summary = await getAdminModerationSummary();
			setQueueCounts(summary || null);
		} catch (error) {
			setQueueCounts(null);
		}
	}, []);

	useEffect(() => {
		if (canAccess) {
			refreshModerationSummary();
		}
	}, [canAccess, refreshModerationSummary]);

	if (!canAccess) {
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
				<ModerationNavigation user={user} queueCounts={queueCounts} />
			</header>

			<div className="moderation-content">
				<Outlet context={{ refreshModerationSummary }} />
			</div>
		</div>
	);
};

export default ModerationLayout;
