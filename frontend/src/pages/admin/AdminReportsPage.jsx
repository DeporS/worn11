import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import AdminUserLink from "../../components/admin/AdminUserLink";
import {
	dismissAdminKitReport,
	getAdminKitReportDetail,
	getAdminKitReports,
	removeAdminReportedKit,
} from "../../services/api";

import "../../styles/admin.css";

const STATUS_TABS = ["pending", "resolved", "dismissed", "all"];

const formatDate = (value, language) => {
	if (!value) return "";
	const parsed = new Date(value);
	if (Number.isNaN(parsed.getTime())) return "";
	return new Intl.DateTimeFormat(language, {
		year: "numeric",
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	}).format(parsed);
};

const getGroupStatus = (group) => {
	if (group?.has_pending_reports) return "pending";
	if (group?.is_hidden_by_moderation) return "resolved";
	return "dismissed";
};

const getReporterSummary = (reporters, t) => {
	const list = Array.isArray(reporters) ? reporters : [];
	const visibleReporters = list.slice(0, 2);
	const moreCount = list.length - visibleReporters.length;

	if (visibleReporters.length === 0) {
		return (
			<span className="text-muted">
				{t("moderation.reports.unknownUser")}
			</span>
		);
	}

	return (
		<>
			{visibleReporters.map((reporter, index) => (
				<span key={reporter.id || reporter.username || index} className="admin-report-reporter-chip">
					{index > 0 ? ", " : ""}
					<AdminUserLink
						username={reporter.username}
						displayName={reporter.username ? `@${reporter.username}` : undefined}
						fallback={t("moderation.reports.unknownUser")}
					/>
				</span>
			))}
			{moreCount > 0 ? (
				<span className="text-muted">
					{visibleReporters.length > 0 ? ", " : ""}
					{t("moderation.reports.moreReporters", { count: moreCount })}
				</span>
			) : null}
		</>
	);
};

const AdminReportsPage = () => {
	const { t, i18n } = useTranslation();
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [notice, setNotice] = useState("");
	const [activeStatus, setActiveStatus] = useState("pending");
	const [queryInput, setQueryInput] = useState("");
	const [appliedQuery, setAppliedQuery] = useState("");
	const [reportGroups, setReportGroups] = useState([]);
	const [expandedId, setExpandedId] = useState(null);
	const [detailsById, setDetailsById] = useState({});
	const [busyById, setBusyById] = useState({});

	const loadReports = useCallback(
		async ({ status = activeStatus, query = appliedQuery } = {}) => {
			setLoading(true);
			setError("");
			try {
				const response = await getAdminKitReports({
					status,
					query,
				});
				setReportGroups(Array.isArray(response) ? response : []);
			} catch (loadError) {
				console.error("Failed to load kit reports", loadError);
				setError(t("moderation.reports.loadError"));
			} finally {
				setLoading(false);
			}
		},
		[activeStatus, appliedQuery, t],
	);

	const loadDetail = useCallback(
		async (id) => {
			const detail = await getAdminKitReportDetail(id);
			setDetailsById((current) => ({
				...current,
				[id]: detail,
			}));
			return detail;
		},
		[],
	);

	useEffect(() => {
		loadReports();
	}, [loadReports]);

	const handleTabChange = async (status) => {
		setActiveStatus(status);
		setExpandedId(null);
		await loadReports({ status, query: appliedQuery });
	};

	const handleSearchSubmit = async (event) => {
		event.preventDefault();
		setAppliedQuery(queryInput.trim());
		setExpandedId(null);
		await loadReports({ status: activeStatus, query: queryInput.trim() });
	};

	const handleToggleExpand = async (groupId) => {
		if (expandedId === groupId) {
			setExpandedId(null);
			return;
		}
		setExpandedId(groupId);
		if (!detailsById[groupId]) {
			try {
				await loadDetail(groupId);
			} catch (loadError) {
				console.error("Failed to load report detail", loadError);
				Swal.fire(t("common.error"), t("moderation.reports.loadDetailError"), "error");
			}
		}
	};

	const markBusy = (id, busy) => {
		setBusyById((current) => ({
			...current,
			[id]: busy,
		}));
	};

	const refreshAfterAction = async (id) => {
		setDetailsById((current) => {
			const next = { ...current };
			delete next[id];
			return next;
		});
		await loadReports();
		if (expandedId === id) {
			setExpandedId(null);
		}
	};

	const handleDismiss = async (group) => {
		const result = await Swal.fire({
			title: t("moderation.reports.dismissTitle"),
			input: "textarea",
			inputLabel: t("moderation.reports.note"),
			inputPlaceholder: t("moderation.reports.dismissNotePlaceholder"),
			icon: "question",
			showCancelButton: true,
			confirmButtonText: t("moderation.reports.dismiss"),
			cancelButtonText: t("common.cancel"),
			inputAutoTrim: true,
		});
		if (!result.isConfirmed) return;

		markBusy(group.id, true);
		try {
			await dismissAdminKitReport(group.id, { note: result.value || "" });
			setNotice(t("moderation.reports.dismissSuccess"));
			await refreshAfterAction(group.id);
		} catch (actionError) {
			console.error("Failed to dismiss kit reports", actionError);
			const message =
				actionError?.response?.data?.detail ||
				t("moderation.reports.actionError");
			Swal.fire(t("common.error"), message, "error");
		} finally {
			markBusy(group.id, false);
		}
	};

	const handleRemoveKit = async (group) => {
		const result = await Swal.fire({
			title: t("moderation.reports.removeTitle"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("moderation.reports.removeKit"),
			cancelButtonText: t("common.cancel"),
			input: "textarea",
			inputLabel: t("moderation.reports.note"),
			inputPlaceholder: t("moderation.reports.removeNotePlaceholder"),
			inputAutoTrim: true,
			html: `
				<div class="text-start">
					<p class="mb-2">${t("moderation.reports.removeWarning")}</p>
					<ul class="small text-muted ps-3 mb-0">
						<li>${t("moderation.reports.removeWarningProfiles")}</li>
						<li>${t("moderation.reports.removeWarningEvidence")}</li>
						<li>${t("moderation.reports.removeWarningOwner")}</li>
					</ul>
				</div>
			`,
			preConfirm: (value) => {
				const note = (value || "").trim();
				if (!note) {
					Swal.showValidationMessage(t("moderation.reports.noteRequired"));
					return false;
				}
				return note;
			},
		});
		if (!result.isConfirmed || !result.value) return;

		markBusy(group.id, true);
		try {
			await removeAdminReportedKit(group.id, { note: result.value });
			setNotice(t("moderation.reports.removeSuccess"));
			await refreshAfterAction(group.id);
		} catch (actionError) {
			console.error("Failed to remove reported kit", actionError);
			const message =
				actionError?.response?.data?.detail ||
				actionError?.response?.data?.note?.[0] ||
				t("moderation.reports.actionError");
			Swal.fire(t("common.error"), message, "error");
		} finally {
			markBusy(group.id, false);
		}
	};

	const pendingCountLabel = useMemo(
		() => t("moderation.reports.reportCount", { count: reportGroups.length }),
		[reportGroups.length, t],
	);

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

			<div className="admin-reports-toolbar">
				<div className="admin-reports-tabs" role="tablist" aria-label={t("moderation.reports.title")}>
					{STATUS_TABS.map((statusKey) => (
						<button
							key={statusKey}
							type="button"
							className={`admin-reports-tab ${activeStatus === statusKey ? "admin-reports-tab-active" : ""}`}
							onClick={() => handleTabChange(statusKey)}
						>
							{t(`moderation.reports.${statusKey}`)}
						</button>
					))}
				</div>

				<form className="admin-reports-search" onSubmit={handleSearchSubmit}>
					<input
						type="search"
						className="form-control"
						value={queryInput}
						onChange={(event) => setQueryInput(event.target.value)}
						placeholder={t("moderation.reports.searchPlaceholder")}
					/>
					<button type="submit" className="btn btn-outline-primary">
						{t("moderation.reports.search")}
					</button>
				</form>
			</div>

			<div className="d-flex flex-wrap align-items-center gap-3">
				<span className="admin-kit-types-badge">{pendingCountLabel}</span>
				{notice ? <span className="text-success fw-semibold">{notice}</span> : null}
			</div>

			{loading ? (
				<div className="moderation-placeholder">{t("common.loading")}</div>
			) : error ? (
				<div className="moderation-placeholder moderation-placeholder--denied">
					<div className="moderation-placeholder-title">{error}</div>
				</div>
			) : reportGroups.length === 0 ? (
				<div className="moderation-placeholder">
					<div className="moderation-placeholder-title">
						{t("moderation.reports.empty")}
					</div>
				</div>
			) : (
				<div className="admin-reports-list">
					{reportGroups.map((group) => {
						const detail = detailsById[group.id];
						const busy = Boolean(busyById[group.id]);
						const latestReport = group.latest_reports?.[0];
						const statusLabel = t(`moderation.reports.${getGroupStatus(group)}`);

						return (
							<article key={group.id} className="admin-report-card">
								<div className="admin-report-card-main">
									<div className="admin-report-card-preview">
										{group.preview_image ? (
											<img
												src={group.preview_image}
												alt={`${group.team_name} ${group.season}`}
												className="admin-report-card-image"
											/>
										) : (
											<div className="admin-suggestion-image-placeholder">
												{t("moderation.reports.noPreview")}
											</div>
										)}
									</div>

									<div className="admin-report-card-content">
										<div className="admin-report-card-top">
											<div>
												<h3 className="admin-report-card-title">
													{group.team_name}
												</h3>
												<div className="admin-report-card-subtitle">
													{[group.season, group.kit_type].filter(Boolean).join(" • ")}
												</div>
											</div>
											<span className={`admin-report-status admin-report-status--${getGroupStatus(group)}`}>
												{statusLabel}
											</span>
										</div>

										<div className="admin-report-card-meta">
											<span>
												<strong>{t("moderation.reports.owner")}:</strong>{" "}
												<AdminUserLink
													username={group.owner_username}
													displayName={group.owner_username ? `@${group.owner_username}` : undefined}
													fallback={t("moderation.reports.unknownUser")}
												/>
											</span>
											<span className="admin-report-card-reporter-summary">
												<strong>{t("moderation.reports.reportedBy")}:</strong>{" "}
												{getReporterSummary(group.reporters, t)}
											</span>
											<span>
												<strong>{t("moderation.reports.latestReport")}:</strong>{" "}
												{formatDate(group.latest_report_at, i18n.language)}
											</span>
											<span>
												<strong>{t("moderation.reports.reportCount", { count: group.report_count })}</strong>
											</span>
										</div>

										<div className="admin-report-card-reasons">
											{(group.reasons || []).map((reason) => (
												<span key={reason} className="admin-report-reason-pill">
													{t(`report.reasons.${reason}`)}
												</span>
											))}
										</div>

										{latestReport?.description ? (
											<p className="admin-report-card-snippet">{latestReport.description}</p>
										) : null}

										<div className="admin-report-card-actions">
											<button
												type="button"
												className="btn btn-outline-secondary btn-sm"
												onClick={() => handleToggleExpand(group.id)}
											>
												{expandedId === group.id
													? t("moderation.reports.hideDetails")
													: t("moderation.reports.viewDetails")}
											</button>
											<button
												type="button"
												className="btn btn-outline-success btn-sm"
												onClick={() => handleDismiss(group)}
												disabled={busy || !group.has_pending_reports}
											>
												{t("moderation.reports.dismiss")}
											</button>
											<button
												type="button"
												className="btn btn-danger btn-sm"
												onClick={() => handleRemoveKit(group)}
												disabled={busy || !group.has_pending_reports}
											>
												{t("moderation.reports.removeKit")}
											</button>
										</div>
									</div>
								</div>

								{expandedId === group.id ? (
									<div className="admin-report-detail">
										{detail ? (
											<>
												<div className="admin-report-detail-section">
													<h4>{t("moderation.reports.detailReports")}</h4>
													<div className="admin-report-detail-list">
														{(detail.reports || []).map((report) => (
															<div key={report.id} className="admin-report-detail-item">
																<div className="admin-report-detail-row">
																	<strong>{t("moderation.reports.reporter")}:</strong>{" "}
																	<AdminUserLink
																		username={report.reporter?.username}
																		displayName={report.reporter?.username ? `@${report.reporter.username}` : undefined}
																		fallback={t("moderation.reports.unknownUser")}
																	/>
																</div>
																<div className="admin-report-detail-row">
																	<strong>{t("moderation.reports.reason")}:</strong> {t(`report.reasons.${report.reason}`)}
																</div>
																<div className="admin-report-detail-row">
																	<strong>{t("moderation.reports.statusLabel")}:</strong> {report.status}
																</div>
																<div className="admin-report-detail-row">
																	<strong>{t("moderation.reports.latestReport")}:</strong> {formatDate(report.created_at, i18n.language)}
																</div>
																{report.description ? (
																	<div className="admin-report-detail-note">{report.description}</div>
																) : null}
																{report.resolution_note ? (
																	<div className="admin-report-detail-note admin-report-detail-note--muted">
																		<strong>{t("moderation.reports.note")}:</strong> {report.resolution_note}
																	</div>
																) : null}
															</div>
														))}
													</div>
												</div>

												{detail.moderation_actions?.length ? (
													<div className="admin-report-detail-section">
														<h4>{t("moderation.reports.actionHistory")}</h4>
														<div className="admin-report-detail-list">
															{detail.moderation_actions.map((action) => (
																<div key={action.id} className="admin-report-detail-item">
																	<div className="admin-report-detail-row">
																		<AdminUserLink
																			username={action.actor_username}
																			displayName={action.actor_username || undefined}
																			fallback={t("moderation.reports.unknownUser")}
																		/>
																		<span>{t(`moderation.reports.actionType.${action.action_type}`)}</span>
																		<span>{formatDate(action.created_at, i18n.language)}</span>
																	</div>
																	{action.note ? (
																		<div className="admin-report-detail-note admin-report-detail-note--muted">
																			{action.note}
																		</div>
																	) : null}
																</div>
															))}
														</div>
													</div>
												) : null}
											</>
										) : (
											<div className="text-muted">{t("common.loading")}</div>
										)}
									</div>
								) : null}
							</article>
						);
					})}
				</div>
			)}
		</section>
	);
};

export default AdminReportsPage;
