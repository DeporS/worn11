import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import api, {
	approveAdminTeamSeasonKitType,
	getAdminKitTypeSuggestions,
	mergeAdminTeamSeasonKitType,
	rejectAdminTeamSeasonKitType,
} from "../services/api";
import { canAccessModeration } from "../utils/permissions";

import "../styles/admin.css";

const formatDate = (value, locale) => {
	if (!value) return "";
	try {
		return new Intl.DateTimeFormat(locale, {
			year: "numeric",
			month: "short",
			day: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		}).format(new Date(value));
	} catch (error) {
		return value;
	}
};

const AdminKitTypesPage = ({ user }) => {
	const { t, i18n } = useTranslation();
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [items, setItems] = useState([]);
	const [approvedKitTypes, setApprovedKitTypes] = useState([]);
	const [mergeTargets, setMergeTargets] = useState({});
	const [actionId, setActionId] = useState(null);

	const locale = i18n.language?.startsWith("pl") ? "pl-PL" : "en-US";

	const approvedOptions = useMemo(
		() =>
			approvedKitTypes.map((kitType) => ({
				value: String(kitType.id),
				label: kitType.name,
			})),
		[approvedKitTypes],
	);
	const hasModerationAccess = canAccessModeration(user);

	useEffect(() => {
		if (!hasModerationAccess) {
			setLoading(false);
			return undefined;
		}

		let cancelled = false;

		const loadPage = async () => {
			setLoading(true);
			setError("");
			try {
				const [suggestions, optionsResponse] = await Promise.all([
					getAdminKitTypeSuggestions(),
					api.get("/options/"),
				]);
				if (cancelled) return;
				setItems(Array.isArray(suggestions) ? suggestions : []);
				setApprovedKitTypes(optionsResponse.data?.kit_types || []);
				setMergeTargets({});
			} catch (loadError) {
				console.error("Failed to load admin kit type suggestions", loadError);
				if (!cancelled) {
					setError(t("admin.loadError"));
				}
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		};

		loadPage();

		return () => {
			cancelled = true;
		};
	}, [hasModerationAccess, t, user]);

	const removeItem = (itemId) => {
		setItems((current) => current.filter((item) => item.id !== itemId));
		setMergeTargets((current) => {
			const next = { ...current };
			delete next[itemId];
			return next;
		});
	};

	const handleApprove = async (item) => {
		setActionId(item.id);
		try {
			await approveAdminTeamSeasonKitType(item.id);
			removeItem(item.id);
		} catch (actionError) {
			console.error("Failed to approve admin suggestion", actionError);
			Swal.fire(t("common.error"), t("admin.actionError"), "error");
		} finally {
			setActionId(null);
		}
	};

	const handleReject = async (item) => {
		const result = await Swal.fire({
			title: t("admin.reject"),
			text: t("admin.rejectConfirm"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("admin.reject"),
			cancelButtonText: t("common.cancel"),
		});
		if (!result.isConfirmed) return;

		setActionId(item.id);
		try {
			await rejectAdminTeamSeasonKitType(item.id);
			removeItem(item.id);
		} catch (actionError) {
			console.error("Failed to reject admin suggestion", actionError);
			Swal.fire(t("common.error"), t("admin.actionError"), "error");
		} finally {
			setActionId(null);
		}
	};

	const handleMerge = async (item) => {
		const targetKitTypeId = mergeTargets[item.id];
		if (!targetKitTypeId) {
			Swal.fire(t("common.error"), t("admin.selectMergeTarget"), "error");
			return;
		}

		const result = await Swal.fire({
			title: t("admin.merge"),
			text: t("admin.mergeConfirm"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("admin.merge"),
			cancelButtonText: t("common.cancel"),
		});
		if (!result.isConfirmed) return;

		setActionId(item.id);
		try {
			await mergeAdminTeamSeasonKitType(item.id, Number(targetKitTypeId));
			removeItem(item.id);
		} catch (actionError) {
			console.error("Failed to merge admin suggestion", actionError);
			Swal.fire(t("common.error"), t("admin.actionError"), "error");
		} finally {
			setActionId(null);
		}
	};

	if (!hasModerationAccess) {
		return (
			<div className="container py-5 admin-kit-types-page">
				<div className="admin-kit-types-empty">{t("admin.notAuthorized")}</div>
			</div>
		);
	}

	return (
		<div className="container py-5 admin-kit-types-page">
			<div className="admin-kit-types-header">
				<div>
					<h1 className="fw-bold mb-1">{t("admin.title")}</h1>
					<p className="text-muted mb-0">{t("admin.kitTypesTitle")}</p>
				</div>
			</div>

			{loading ? (
				<div className="text-center py-5">
					<div className="spinner-border text-primary" role="status" />
					<div className="text-muted mt-3">{t("common.loading")}</div>
				</div>
			) : null}

			{!loading && error ? (
				<div className="alert alert-danger" role="alert">
					{error}
				</div>
			) : null}

			{!loading && !error && items.length === 0 ? (
				<div className="admin-kit-types-empty">{t("admin.noSuggestions")}</div>
			) : null}

			{!loading && !error && items.length > 0 ? (
				<div className="admin-kit-types-grid">
					{items.map((item) => {
						const isBusy = actionId === item.id;
						const mergeChoices = approvedOptions.filter(
							(option) => Number(option.value) !== item.kit_type_id,
						);

						return (
							<div key={item.id} className="card shadow-sm border-0 admin-kit-types-card">
								<div className="card-body">
									<div className="admin-kit-types-card-top">
										<div>
											<div className="admin-kit-types-badge">{item.kit_type_name}</div>
											<h2 className="h5 fw-bold mt-3 mb-1">
												{item.team_name}
											</h2>
											<div className="text-muted small">
												{t("admin.seasonLabel", { season: item.season })}
											</div>
										</div>
										<div className="text-end small text-muted">
											<div>{t("admin.uploads", { count: item.upload_count || 0 })}</div>
											<div>{item.kit_type_status}</div>
										</div>
									</div>

									<div className="admin-kit-types-preview">
										{item.preview_image ? (
											<img
												src={item.preview_image}
												alt={item.kit_type_name}
												className="admin-kit-types-image"
											/>
										) : (
											<div className="admin-kit-types-image-placeholder">
												{t("admin.noPreview")}
											</div>
										)}
									</div>

									<div className="admin-kit-types-meta">
										<div>
											<strong>{t("admin.createdByLabel")}</strong>{" "}
											{item.created_by_username || "—"}
										</div>
										<div>
											<strong>{t("admin.createdAtLabel")}</strong>{" "}
											{formatDate(item.created_at, locale)}
										</div>
										<div>
											<strong>{t("admin.sourceLabel")}</strong> {item.source}
										</div>
										{item.museum_url ? (
											<div>
												<a href={item.museum_url} className="small">
													{t("admin.viewMuseum")}
												</a>
											</div>
										) : null}
									</div>

									<div className="admin-kit-types-actions">
										<button
											type="button"
											className="btn btn-primary"
											disabled={isBusy}
											onClick={() => handleApprove(item)}
										>
											{t("admin.approve")}
										</button>
										<button
											type="button"
											className="btn btn-outline-danger"
											disabled={isBusy}
											onClick={() => handleReject(item)}
										>
											{t("admin.reject")}
										</button>
									</div>

									<div className="admin-kit-types-merge">
										<label className="form-label small text-muted mb-1">
											{t("admin.mergeInto")}
										</label>
										<div className="d-flex flex-column flex-md-row gap-2">
											<select
												className="form-select"
												value={mergeTargets[item.id] || ""}
												disabled={isBusy}
												onChange={(event) =>
													setMergeTargets((current) => ({
														...current,
														[item.id]: event.target.value,
													}))
												}
											>
												<option value="">{t("admin.selectMergeTarget")}</option>
												{mergeChoices.map((option) => (
													<option key={option.value} value={option.value}>
														{option.label}
													</option>
												))}
											</select>
											<button
												type="button"
												className="btn btn-outline-secondary"
												disabled={isBusy}
												onClick={() => handleMerge(item)}
											>
												{t("admin.merge")}
											</button>
										</div>
									</div>
								</div>
							</div>
						);
					})}
				</div>
			) : null}
		</div>
	);
};

export default AdminKitTypesPage;
