import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import CatalogImagePreview from "../../components/admin/CatalogImagePreview";
import CatalogModal from "../../components/admin/CatalogModal";
import {
	createAdminCatalogLeague,
	getAdminCatalogCountries,
	getAdminCatalogLeagues,
	updateAdminCatalogLeague,
} from "../../services/api";

import "../../styles/admin.css";

const buildLeagueForm = (league = null) => ({
	name: league?.name || "",
	country_id: league?.country_id || "",
	logo: null,
	hex_color: league?.hex_color || "#333333",
	order: league?.order ?? 0,
	is_active: league?.is_active ?? true,
});

const getApiErrorMessage = (error, fallback) => {
	const data = error?.response?.data;
	if (typeof data?.detail === "string") return data.detail;
	if (Array.isArray(data?.non_field_errors) && data.non_field_errors[0]) {
		return data.non_field_errors[0];
	}
	if (data && typeof data === "object") {
		const firstValue = Object.values(data)[0];
		if (Array.isArray(firstValue) && firstValue[0]) return firstValue[0];
		if (typeof firstValue === "string") return firstValue;
	}
	return fallback;
};

const formatDate = (value) => {
	if (!value) return "N/A";
	return new Date(value).toLocaleString();
};

const AdminLeaguesPage = () => {
	const { t } = useTranslation();
	const [countries, setCountries] = useState([]);
	const [leagues, setLeagues] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [notice, setNotice] = useState("");
	const [filters, setFilters] = useState({ q: "", active: "all", country_id: "" });
	const [modalOpen, setModalOpen] = useState(false);
	const [editingLeague, setEditingLeague] = useState(null);
	const [form, setForm] = useState(buildLeagueForm());
	const [logoPreviewSrc, setLogoPreviewSrc] = useState(null);
	const [submitting, setSubmitting] = useState(false);
	const [modalError, setModalError] = useState("");
	const logoPreviewObjectUrlRef = useRef(null);

	const clearLogoPreviewObjectUrl = () => {
		if (logoPreviewObjectUrlRef.current) {
			URL.revokeObjectURL(logoPreviewObjectUrlRef.current);
			logoPreviewObjectUrlRef.current = null;
		}
	};

	useEffect(() => {
		let cancelled = false;

		const loadPage = async () => {
			setLoading(true);
			setError("");
			try {
				const [countriesResponse, leaguesResponse] = await Promise.all([
					getAdminCatalogCountries({ active: "all" }),
					getAdminCatalogLeagues(filters),
				]);
				if (cancelled) return;
				setCountries(Array.isArray(countriesResponse) ? countriesResponse : []);
				setLeagues(Array.isArray(leaguesResponse) ? leaguesResponse : []);
			} catch (loadError) {
				console.error("Failed to load catalog leagues", loadError);
				if (!cancelled) {
					setError(t("admin.catalog.error"));
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
			clearLogoPreviewObjectUrl();
		};
	}, [filters, t]);

	const countryOptions = useMemo(
		() => [...countries].sort((left, right) => (left.name || "").localeCompare(right.name || "")),
		[countries],
	);

	const reloadLeagues = async () => {
		const response = await getAdminCatalogLeagues(filters);
		setLeagues(Array.isArray(response) ? response : []);
	};

	const closeModal = () => {
		clearLogoPreviewObjectUrl();
		setModalOpen(false);
		setEditingLeague(null);
		setForm(buildLeagueForm());
		setLogoPreviewSrc(null);
		setModalError("");
	};

	const openCreateModal = () => {
		clearLogoPreviewObjectUrl();
		setEditingLeague(null);
		setForm(buildLeagueForm());
		setLogoPreviewSrc(null);
		setModalError("");
		setModalOpen(true);
	};

	const openEditModal = (league) => {
		clearLogoPreviewObjectUrl();
		setEditingLeague(league);
		setForm(buildLeagueForm(league));
		setLogoPreviewSrc(league.logo || null);
		setModalError("");
		setModalOpen(true);
	};

	const handleSubmit = async (event) => {
		event.preventDefault();
		setSubmitting(true);
		setModalError("");
		try {
			const payload = {
				name: form.name,
				country_id: form.country_id,
				hex_color: form.hex_color,
				order: form.order,
				is_active: form.is_active,
			};
			if (form.logo instanceof File) {
				payload.logo = form.logo;
			}

			if (editingLeague) {
				await updateAdminCatalogLeague(editingLeague.id, payload);
				setNotice(t("admin.catalog.updated"));
			} else {
				await createAdminCatalogLeague(payload);
				setNotice(t("admin.catalog.created"));
			}
			await reloadLeagues();
			closeModal();
		} catch (submitError) {
			console.error("Failed to save league", submitError);
			setModalError(getApiErrorMessage(submitError, t("admin.catalog.error")));
		} finally {
			setSubmitting(false);
		}
	};

	const handleLogoChange = (event) => {
		const file = event.target.files?.[0] || null;
		setForm((current) => ({ ...current, logo: file }));
		clearLogoPreviewObjectUrl();

		if (file) {
			const objectUrl = URL.createObjectURL(file);
			logoPreviewObjectUrlRef.current = objectUrl;
			setLogoPreviewSrc(objectUrl);
			return;
		}

		setLogoPreviewSrc(editingLeague?.logo || null);
	};

	return (
		<section className="catalog-page moderation-section">
			<div className="admin-kit-types-header">
				<div>
					<h3 className="h4 fw-bold mb-1">{t("admin.catalog.leagues")}</h3>
				</div>
				<button type="button" className="btn btn-primary" onClick={openCreateModal}>
					{t("admin.catalog.addLeague")}
				</button>
			</div>

			<div className="catalog-filter-bar catalog-filter-bar--leagues">
				<div className="catalog-filter-field">
					<label htmlFor="leagues-search" className="catalog-filter-label">
						{t("admin.catalog.searchLeagues")}
					</label>
					<input
						id="leagues-search"
						type="search"
						className="form-control catalog-filter-control"
						placeholder={t("admin.catalog.searchLeagues")}
						value={filters.q}
						onChange={(event) =>
							setFilters((current) => ({ ...current, q: event.target.value }))
						}
					/>
				</div>
				<div className="catalog-filter-field">
					<label htmlFor="leagues-country" className="catalog-filter-label">
						{t("admin.catalog.filterCountry")}
					</label>
					<select
						id="leagues-country"
						className="form-select catalog-filter-control"
						value={filters.country_id}
						onChange={(event) =>
							setFilters((current) => ({ ...current, country_id: event.target.value }))
						}
					>
						<option value="">{t("admin.catalog.allCountries")}</option>
						{countryOptions.map((country) => (
							<option key={country.id} value={country.id}>
								{country.name}
							</option>
						))}
					</select>
				</div>
				<div className="catalog-filter-field">
					<label htmlFor="leagues-status" className="catalog-filter-label">
						{t("admin.catalog.filterStatus")}
					</label>
					<select
						id="leagues-status"
						className="form-select catalog-filter-control"
						value={filters.active}
						onChange={(event) =>
							setFilters((current) => ({ ...current, active: event.target.value }))
						}
					>
						<option value="all">{t("admin.catalog.allStatuses")}</option>
						<option value="active">{t("admin.catalog.active")}</option>
						<option value="inactive">{t("admin.catalog.inactive")}</option>
					</select>
				</div>
			</div>

			{notice ? <div className="alert alert-success">{notice}</div> : null}
			{error ? <div className="alert alert-danger">{error}</div> : null}
			{loading ? <div className="admin-kit-types-empty">Loading...</div> : null}
			{!loading && leagues.length === 0 ? (
				<div className="admin-kit-types-empty">{t("admin.catalog.empty")}</div>
			) : null}

			{!loading && leagues.length > 0 ? (
				<>
					<div className="catalog-table-wrapper">
						<table className="table align-middle catalog-table">
							<thead>
								<tr>
									<th>{t("admin.catalog.logo")}</th>
									<th>{t("admin.catalog.name")}</th>
									<th>{t("admin.catalog.country")}</th>
									<th>{t("admin.catalog.color")}</th>
									<th>{t("admin.catalog.order")}</th>
									<th>{t("admin.catalog.active")}</th>
									<th>{t("admin.catalog.teams")}</th>
									<th>{t("admin.catalog.createdBy")}</th>
									<th>{t("admin.catalog.createdAt")}</th>
									<th />
								</tr>
							</thead>
							<tbody>
								{leagues.map((league) => (
									<tr key={league.id}>
										<td>
											<CatalogImagePreview
												src={league.logo}
												alt={`${league.name} logo`}
												variant="logo"
												fallbackLabel={t("admin.catalog.noLogo")}
												className="catalog-thumbnail--table"
											/>
										</td>
										<td>{league.name}</td>
										<td>{league.country_name || "N/A"}</td>
										<td>
											<span className="catalog-color-chip" style={{ backgroundColor: league.hex_color }} />
											{league.hex_color}
										</td>
										<td>{league.order}</td>
										<td>
											<span className={`catalog-status-badge ${league.is_active ? "is-active" : "is-inactive"}`}>
												{league.is_active
													? t("admin.catalog.active")
													: t("admin.catalog.inactive")}
											</span>
										</td>
										<td>{league.teams_count}</td>
										<td>{league.created_by || "N/A"}</td>
										<td>{formatDate(league.created_at)}</td>
										<td className="text-end">
											<button
												type="button"
												className="btn btn-outline-secondary btn-sm"
												onClick={() => openEditModal(league)}
											>
												{t("admin.catalog.edit")}
											</button>
										</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>

					<div className="catalog-cards">
						{leagues.map((league) => (
							<article key={league.id} className="catalog-card">
								<div className="catalog-card-top">
									<CatalogImagePreview
										src={league.logo}
										alt={`${league.name} logo`}
										variant="logo"
										fallbackLabel={t("admin.catalog.noLogo")}
										className="catalog-thumbnail--card"
									/>
									<div>
										<div className="catalog-card-title">{league.name}</div>
										<div className="catalog-card-subtitle">{league.country_name || "N/A"}</div>
									</div>
									<span className={`catalog-status-badge ${league.is_active ? "is-active" : "is-inactive"}`}>
										{league.is_active
											? t("admin.catalog.active")
											: t("admin.catalog.inactive")}
									</span>
								</div>
								<div className="catalog-card-meta">
									<span>{t("admin.catalog.color")}: {league.hex_color}</span>
									<span>{t("admin.catalog.order")}: {league.order}</span>
									<span>{t("admin.catalog.teams")}: {league.teams_count}</span>
								</div>
								<div className="catalog-card-actions">
									<button
										type="button"
										className="btn btn-outline-secondary btn-sm"
										onClick={() => openEditModal(league)}
									>
										{t("admin.catalog.edit")}
									</button>
								</div>
							</article>
						))}
					</div>
				</>
			) : null}

			<CatalogModal
				isOpen={modalOpen}
				title={editingLeague ? t("admin.catalog.editLeague") : t("admin.catalog.addLeague")}
				onClose={closeModal}
				onSubmit={handleSubmit}
				submitting={submitting}
				error={modalError}
				submitLabel={editingLeague ? t("admin.catalog.save") : t("admin.catalog.create")}
				closeLabel={t("common.cancel")}
				cancelLabel={t("common.cancel")}
			>
				<div>
					<label className="form-label fw-semibold">{t("admin.catalog.name")}</label>
					<input
						type="text"
						className="form-control"
						value={form.name}
						onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
						disabled={submitting}
					/>
				</div>
				<div>
					<label className="form-label fw-semibold">{t("admin.catalog.country")}</label>
					<select
						className="form-select"
						value={form.country_id}
						onChange={(event) => setForm((current) => ({ ...current, country_id: event.target.value }))}
						disabled={submitting}
					>
						<option value="">{t("admin.catalog.selectCountry")}</option>
						{countryOptions.map((country) => (
							<option key={country.id} value={country.id}>
								{country.name}
							</option>
						))}
					</select>
				</div>
				<div>
					<label className="form-label fw-semibold">{t("admin.catalog.logo")}</label>
					<CatalogImagePreview
						src={logoPreviewSrc}
						alt={editingLeague ? `${editingLeague.name} logo` : t("admin.catalog.logoPreview")}
						variant="logo"
						previewLabel={t("admin.catalog.logoPreview")}
						fallbackLabel={t("admin.catalog.noLogo")}
						showLabel
						className="catalog-thumbnail--modal"
					/>
					<input
						type="file"
						className="form-control"
						accept="image/*"
						onChange={handleLogoChange}
						disabled={submitting}
					/>
					<div className="form-text">{t("admin.catalog.imagePreview")}</div>
				</div>
				<div className="catalog-form-grid">
					<div>
						<label className="form-label fw-semibold">{t("admin.catalog.color")}</label>
						<input
							type="text"
							className="form-control"
							value={form.hex_color}
							onChange={(event) =>
								setForm((current) => ({ ...current, hex_color: event.target.value }))
							}
							disabled={submitting}
						/>
					</div>
					<div>
						<label className="form-label fw-semibold">{t("admin.catalog.order")}</label>
						<input
							type="number"
							className="form-control"
							value={form.order}
							onChange={(event) =>
								setForm((current) => ({ ...current, order: event.target.value }))
							}
							disabled={submitting}
						/>
					</div>
				</div>
				<div className="form-check">
					<input
						id="league-active"
						type="checkbox"
						className="form-check-input"
						checked={form.is_active}
						onChange={(event) =>
							setForm((current) => ({ ...current, is_active: event.target.checked }))
						}
						disabled={submitting}
					/>
					<label htmlFor="league-active" className="form-check-label">
						{t("admin.catalog.active")}
					</label>
				</div>
			</CatalogModal>
		</section>
	);
};

export default AdminLeaguesPage;
