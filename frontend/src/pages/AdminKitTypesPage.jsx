import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import api, {
	approveAdminTeamSeasonKitType,
	getAdminKitTypeModerationActions,
	getAdminKitTypeSuggestions,
	mergeAdminTeamSeasonKitType,
	rejectAdminTeamSeasonKitType,
	undoAdminKitTypeModerationAction,
} from "../services/api";

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

const getModerationActionSummary = (action, t) => {
	if (action.action_type === "approve") {
		return t("moderation.approvedSummary", {
			type: action.source_kit_type_name,
			team: action.team_name,
			season: action.season,
		});
	}
	if (action.action_type === "reject") {
		return t("moderation.rejectedSummary", {
			type: action.source_kit_type_name,
			team: action.team_name,
			season: action.season,
		});
	}
	if (action.action_type === "merge") {
		return t("moderation.mergedSummary", {
			source: action.source_kit_type_name,
			target: action.target_kit_type_name,
		});
	}
	return action.summary || action.action_type;
};

const getUndoBlockText = (action, t) => {
	if (action.undone_at) {
		return t("moderation.undone");
	}
	if (action.action_type === "merge") {
		return t("moderation.mergeManualUndo");
	}
	return action.undo_block_reason || t("moderation.notReversible");
};

const AdminKitTypesPage = ({ user }) => {
	const { t, i18n } = useTranslation();
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [items, setItems] = useState([]);
	const [recentActions, setRecentActions] = useState([]);
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

	useEffect(() => {
		let cancelled = false;

		const loadPage = async () => {
			setLoading(true);
			setError("");
			try {
				const [suggestions, optionsResponse, actions] =
					await Promise.all([
						getAdminKitTypeSuggestions(),
						api.get("/options/"),
						getAdminKitTypeModerationActions(20),
					]);
				if (cancelled) return;
				setItems(Array.isArray(suggestions) ? suggestions : []);
				setApprovedKitTypes(optionsResponse.data?.kit_types || []);
				setRecentActions(Array.isArray(actions) ? actions : []);
				setMergeTargets({});
			} catch (loadError) {
				console.error(
					"Failed to load admin kit type suggestions",
					loadError,
				);
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
	}, [t]);

	const refreshModerationData = async () => {
		const [suggestions, actions] = await Promise.all([
			getAdminKitTypeSuggestions(),
			getAdminKitTypeModerationActions(20),
		]);
		setItems(Array.isArray(suggestions) ? suggestions : []);
		setRecentActions(Array.isArray(actions) ? actions : []);
	};

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
			await refreshModerationData();
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
			await refreshModerationData();
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
			await refreshModerationData();
		} catch (actionError) {
			console.error("Failed to merge admin suggestion", actionError);
			Swal.fire(t("common.error"), t("admin.actionError"), "error");
		} finally {
			setActionId(null);
		}
	};

	const handleUndoAction = async (action) => {
		const result = await Swal.fire({
			title: t("moderation.undoConfirmTitle"),
			text: t("moderation.undoConfirmText"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("moderation.undo"),
			cancelButtonText: t("common.cancel"),
		});
		if (!result.isConfirmed) return;

		setActionId(`undo-${action.id}`);
		try {
			await undoAdminKitTypeModerationAction(action.id);
			await refreshModerationData();
			Swal.fire(
				t("common.success"),
				t("moderation.undoSuccess"),
				"success",
			);
		} catch (actionError) {
			console.error("Failed to undo moderation action", actionError);
			if (actionError?.response?.status === 409) {
				Swal.fire(
					t("common.error"),
					t("moderation.undoConflict"),
					"error",
				);
			} else {
				Swal.fire(
					t("common.error"),
					t("moderation.undoError"),
					"error",
				);
			}
		} finally {
			setActionId(null);
		}
	};

	return (
		<section className="admin-kit-types-page moderation-section">
			<div className="admin-kit-types-header">
				<div>
					<h2 className="fw-bold mb-1">
						{t("moderation.kitTypes.title")}
					</h2>
				</div>
			</div>

			{loading ? (
				<div className="text-center py-5">
					<div
						className="spinner-border text-primary"
						role="status"
					/>
					<div className="text-muted mt-3">{t("common.loading")}</div>
				</div>
			) : null}

			{!loading && error ? (
				<div className="alert alert-danger" role="alert">
					{error}
				</div>
			) : null}

			{!loading && !error && items.length === 0 ? (
				<div className="admin-kit-types-empty">
					{t("admin.noSuggestions")}
				</div>
			) : null}

			{!loading && !error && items.length > 0 ? (
				<div className="admin-suggestions-grid">
					{items.map((item) => {
						const isBusy = actionId === item.id;
						const mergeChoices = approvedOptions.filter(
							(option) =>
								Number(option.value) !== item.kit_type_id,
						);

						return (
							<div
								key={item.id}
								className="card shadow-sm border-0 admin-suggestion-card"
							>
								<div className="card-body admin-suggestion-card-body">
									<div className="admin-suggestion-preview">
										{item.preview_image ? (
											<img
												src={item.preview_image}
												alt={item.kit_type_name}
												className="admin-suggestion-image"
											/>
										) : (
											<div className="admin-suggestion-image-placeholder">
												{t("admin.noPreview")}
											</div>
										)}
									</div>

									<div className="admin-suggestion-content">
										<div className="d-flex align-items-start justify-content-between gap-2">
											<div className="min-w-0">
												<div className="admin-kit-types-badge text-truncate">
													{item.kit_type_name}
												</div>
												<h2 className="h6 fw-bold mt-3 mb-1 text-truncate">
													{item.team_name}
												</h2>
												<div className="text-muted small">
													{t("admin.seasonLabel", {
														season: item.season,
													})}
												</div>
											</div>
											<div className="text-end small text-muted flex-shrink-0">
												<div>
													{t("admin.uploads", {
														count:
															item.upload_count ||
															0,
													})}
												</div>
												<div className="text-uppercase fw-semibold">
													{item.kit_type_status}
												</div>
											</div>
										</div>

										<div className="admin-kit-types-meta">
											<div>
												<strong>
													{t("admin.createdByLabel")}
												</strong>{" "}
												{item.created_by_username ||
													"—"}
											</div>
											<div>
												<strong>
													{t("admin.createdAtLabel")}
												</strong>{" "}
												{formatDate(
													item.created_at,
													locale,
												)}
											</div>
											<div>
												<strong>
													{t("admin.sourceLabel")}
												</strong>{" "}
												{item.source}
											</div>
											{item.museum_url ? (
												<div>
													<a
														href={item.museum_url}
														className="small"
													>
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
												onClick={() =>
													handleApprove(item)
												}
											>
												{t("admin.approve")}
											</button>
											<button
												type="button"
												className="btn btn-outline-danger"
												disabled={isBusy}
												onClick={() =>
													handleReject(item)
												}
											>
												{t("admin.reject")}
											</button>
										</div>

										<div className="admin-kit-types-merge">
											<label className="form-label small text-muted mb-1">
												{t("admin.mergeInto")}
											</label>
											<div className="d-flex flex-column gap-2">
												<select
													className="form-select form-select-sm"
													value={
														mergeTargets[item.id] ||
														""
													}
													disabled={isBusy}
													onChange={(event) =>
														setMergeTargets(
															(current) => ({
																...current,
																[item.id]:
																	event.target
																		.value,
															}),
														)
													}
												>
													<option value="">
														{t(
															"admin.selectMergeTarget",
														)}
													</option>
													{mergeChoices.map(
														(option) => (
															<option
																key={
																	option.value
																}
																value={
																	option.value
																}
															>
																{option.label}
															</option>
														),
													)}
												</select>
												<button
													type="button"
													className="btn btn-outline-secondary btn-sm"
													disabled={isBusy}
													onClick={() =>
														handleMerge(item)
													}
												>
													{t("admin.merge")}
												</button>
											</div>
										</div>
									</div>
								</div>
							</div>
						);
					})}
				</div>
			) : null}

			{!loading ? (
				<div className="admin-recent-actions-section">
					<div className="d-flex justify-content-between align-items-center gap-3 mb-3">
						<h2 className="h5 fw-bold m-0">
							{t("moderation.recentActions")}
						</h2>
					</div>

					{recentActions.length === 0 ? (
						<div className="admin-kit-types-empty">
							{t("moderation.noRecentActions")}
						</div>
					) : (
						<div className="admin-recent-actions-list">
							{recentActions.map((action) => {
								const isUndoBusy =
									actionId === `undo-${action.id}`;
								const isUndone = Boolean(action.undone_at);

								return (
									<div
										key={action.id}
										className="admin-recent-action-card"
									>
										<div className="admin-recent-action-top">
											<div className="min-w-0">
												<div className="admin-recent-action-summary">
													{getModerationActionSummary(
														action,
														t,
													)}
												</div>
												<div className="admin-recent-action-meta">
													<span>
														{action.actor_username}
													</span>
													<span>
														{formatDate(
															action.created_at,
															locale,
														)}
													</span>
												</div>
											</div>
											<div className="admin-recent-action-status">
												<span
													className={`badge rounded-pill ${isUndone ? "text-bg-secondary" : "text-bg-light"}`}
												>
													{isUndone
														? t("moderation.undone")
														: t(
																"moderation.active",
															)}
												</span>
											</div>
										</div>

										<div className="admin-recent-action-bottom">
											{action.can_undo ? (
												<button
													type="button"
													className="btn btn-sm btn-outline-secondary"
													disabled={isUndoBusy}
													onClick={() =>
														handleUndoAction(action)
													}
												>
													{t("moderation.undo")}
												</button>
											) : (
												<div className="admin-recent-action-note">
													{getUndoBlockText(
														action,
														t,
													)}
												</div>
											)}
										</div>
									</div>
								);
							})}
						</div>
					)}
				</div>
			) : null}
		</section>
	);
};

export default AdminKitTypesPage;
