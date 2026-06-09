import { useTranslation } from "react-i18next";

const AdminReportsPage = () => {
	const { t } = useTranslation();

	return (
		<section className="admin-kit-types-page moderation-section">
			<div className="admin-kit-types-header">
				<div>
					<h2 className="fw-bold mb-1">{t("moderation.reports.title")}</h2>
					<p className="text-muted mb-0">
						{t("moderation.reports.description")}
					</p>
				</div>
			</div>

			<div className="moderation-placeholder">
				<div className="moderation-placeholder-title">
					{t("moderation.comingSoon")}
				</div>
			</div>
		</section>
	);
};

export default AdminReportsPage;
