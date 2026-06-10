import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { canAccessCatalog } from "../../utils/permissions";

const AdminCatalogLayout = ({ user }) => {
	const { t } = useTranslation();
	const location = useLocation();

	if (!canAccessCatalog(user)) {
		return (
			<div className="catalog-section">
				<div className="moderation-placeholder moderation-placeholder--denied">
					<div className="moderation-placeholder-title">
						{t("admin.catalog.staffOnly")}
					</div>
				</div>
			</div>
		);
	}

	if (location.pathname === "/admin/catalog") {
		return <Navigate to="/admin/catalog/countries" replace />;
	}

	return (
		<Outlet />
	);
};

export default AdminCatalogLayout;
