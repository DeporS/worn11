import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import AdminUserLink from "../../components/admin/AdminUserLink";
import CatalogImagePreview from "../../components/admin/CatalogImagePreview";
import CatalogModal from "../../components/admin/CatalogModal";
import {
	createAdminCatalogCountry,
	getAdminCatalogCountries,
	updateAdminCatalogCountry,
} from "../../services/api";

import "../../styles/admin.css";

const buildCountryForm = (country = null) => ({
	name: country?.name || "",
	code: country?.code || "",
	flag: null,
	is_active: country?.is_active ?? true,
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

const AdminCountriesPage = () => {
	const { t } = useTranslation();
	const [countries, setCountries] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [notice, setNotice] = useState("");
	const [filters, setFilters] = useState({ q: "", active: "all" });
	const [modalOpen, setModalOpen] = useState(false);
	const [editingCountry, setEditingCountry] = useState(null);
	const [form, setForm] = useState(buildCountryForm());
	const [flagPreviewSrc, setFlagPreviewSrc] = useState(null);
	const [submitting, setSubmitting] = useState(false);
	const [modalError, setModalError] = useState("");
	const flagPreviewObjectUrlRef = useRef(null);

	const clearFlagPreviewObjectUrl = () => {
		if (flagPreviewObjectUrlRef.current) {
			URL.revokeObjectURL(flagPreviewObjectUrlRef.current);
			flagPreviewObjectUrlRef.current = null;
		}
	};

	useEffect(() => {
		let cancelled = false;

		const loadCountries = async () => {
			setLoading(true);
			setError("");
			try {
				const response = await getAdminCatalogCountries(filters);
				if (!cancelled) {
					setCountries(Array.isArray(response) ? response : []);
				}
			} catch (loadError) {
				console.error("Failed to load catalog countries", loadError);
				if (!cancelled) {
					setError(t("admin.catalog.error"));
				}
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		};

		loadCountries();

		return () => {
			cancelled = true;
			clearFlagPreviewObjectUrl();
		};
	}, [filters, t]);

	const openCreateModal = () => {
		clearFlagPreviewObjectUrl();
		setEditingCountry(null);
		setForm(buildCountryForm());
		setFlagPreviewSrc(null);
		setModalError("");
		setModalOpen(true);
	};

	const openEditModal = (country) => {
		clearFlagPreviewObjectUrl();
		setEditingCountry(country);
		setForm(buildCountryForm(country));
		setFlagPreviewSrc(country.flag || null);
		setModalError("");
		setModalOpen(true);
	};

	const closeModal = () => {
		clearFlagPreviewObjectUrl();
		setModalOpen(false);
		setEditingCountry(null);
		setForm(buildCountryForm());
		setFlagPreviewSrc(null);
		setModalError("");
	};

	const reloadCountries = async () => {
		const response = await getAdminCatalogCountries(filters);
		setCountries(Array.isArray(response) ? response : []);
	};

	const handleSubmit = async (event) => {
		event.preventDefault();
		setSubmitting(true);
		setModalError("");
		try {
			const payload = {
				name: form.name,
				code: form.code,
				is_active: form.is_active,
			};
			if (form.flag instanceof File) {
				payload.flag = form.flag;
			}

			if (editingCountry) {
				await updateAdminCatalogCountry(editingCountry.id, payload);
				setNotice(t("admin.catalog.updated"));
			} else {
				await createAdminCatalogCountry(payload);
				setNotice(t("admin.catalog.created"));
			}
			await reloadCountries();
			closeModal();
		} catch (submitError) {
			console.error("Failed to save country", submitError);
			setModalError(getApiErrorMessage(submitError, t("admin.catalog.error")));
		} finally {
			setSubmitting(false);
		}
	};

	const handleFlagChange = (event) => {
		const file = event.target.files?.[0] || null;
		setForm((current) => ({ ...current, flag: file }));
		clearFlagPreviewObjectUrl();

		if (file) {
			const objectUrl = URL.createObjectURL(file);
			flagPreviewObjectUrlRef.current = objectUrl;
			setFlagPreviewSrc(objectUrl);
			return;
		}

		setFlagPreviewSrc(editingCountry?.flag || null);
	};

	return (
		<section className="catalog-page moderation-section">
			<div className="admin-kit-types-header">
				<div>
					<h3 className="h4 fw-bold mb-1">{t("admin.catalog.countries")}</h3>
				</div>
				<button type="button" className="btn btn-primary" onClick={openCreateModal}>
					{t("admin.catalog.addCountry")}
				</button>
			</div>

			<div className="catalog-filter-bar catalog-filter-bar--countries">
				<div className="catalog-filter-field">
					<label htmlFor="countries-search" className="catalog-filter-label">
						{t("admin.catalog.searchCountries")}
					</label>
					<input
						id="countries-search"
						type="search"
						className="form-control catalog-filter-control"
						placeholder={t("admin.catalog.searchCountries")}
						value={filters.q}
						onChange={(event) =>
							setFilters((current) => ({ ...current, q: event.target.value }))
						}
					/>
				</div>
				<div className="catalog-filter-field">
					<label htmlFor="countries-status" className="catalog-filter-label">
						{t("admin.catalog.filterStatus")}
					</label>
					<select
						id="countries-status"
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
			{!loading && countries.length === 0 ? (
				<div className="admin-kit-types-empty">{t("admin.catalog.empty")}</div>
			) : null}

			{!loading && countries.length > 0 ? (
				<>
					<div className="catalog-table-wrapper">
						<table className="table align-middle catalog-table">
							<thead>
								<tr>
									<th>{t("admin.catalog.flag")}</th>
									<th>{t("admin.catalog.name")}</th>
									<th>{t("admin.catalog.code")}</th>
									<th>{t("admin.catalog.active")}</th>
									<th>{t("admin.catalog.leagues")}</th>
									<th>{t("admin.catalog.teams")}</th>
									<th>{t("admin.catalog.createdBy")}</th>
									<th>{t("admin.catalog.createdAt")}</th>
									<th />
								</tr>
							</thead>
							<tbody>
								{countries.map((country) => (
									<tr key={country.id}>
										<td>
											<CatalogImagePreview
												src={country.flag}
												alt={`${country.name} flag`}
												variant="flag"
												fallbackLabel={t("admin.catalog.noFlag")}
												className="catalog-thumbnail--table"
											/>
										</td>
										<td>{country.name}</td>
										<td>{country.code}</td>
										<td>
											<span className={`catalog-status-badge ${country.is_active ? "is-active" : "is-inactive"}`}>
												{country.is_active
													? t("admin.catalog.active")
													: t("admin.catalog.inactive")}
											</span>
										</td>
										<td>{country.leagues_count}</td>
										<td>{country.teams_count}</td>
										<td>
											<AdminUserLink
												username={country.created_by}
												displayName={country.created_by}
												fallback="N/A"
											/>
										</td>
										<td>{formatDate(country.created_at)}</td>
										<td className="text-end">
											<button
												type="button"
												className="btn btn-outline-secondary btn-sm"
												onClick={() => openEditModal(country)}
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
						{countries.map((country) => (
							<article key={country.id} className="catalog-card">
								<div className="catalog-card-top">
									<CatalogImagePreview
										src={country.flag}
										alt={`${country.name} flag`}
										variant="flag"
										fallbackLabel={t("admin.catalog.noFlag")}
										className="catalog-thumbnail--card"
									/>
									<div>
										<div className="catalog-card-title">{country.name}</div>
										<div className="catalog-card-subtitle">{country.code}</div>
									</div>
									<span className={`catalog-status-badge ${country.is_active ? "is-active" : "is-inactive"}`}>
										{country.is_active
											? t("admin.catalog.active")
											: t("admin.catalog.inactive")}
									</span>
								</div>
								<div className="catalog-card-meta">
									<span>{t("admin.catalog.leagues")}: {country.leagues_count}</span>
									<span>{t("admin.catalog.teams")}: {country.teams_count}</span>
									<span>
										{t("admin.catalog.createdBy")}:{` `}
										<AdminUserLink
											username={country.created_by}
											displayName={country.created_by}
											fallback="N/A"
										/>
									</span>
								</div>
								<div className="catalog-card-actions">
									<button
										type="button"
										className="btn btn-outline-secondary btn-sm"
										onClick={() => openEditModal(country)}
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
				title={editingCountry ? t("admin.catalog.editCountry") : t("admin.catalog.addCountry")}
				onClose={closeModal}
				onSubmit={handleSubmit}
				submitting={submitting}
				error={modalError}
				submitLabel={editingCountry ? t("admin.catalog.save") : t("admin.catalog.create")}
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
					<label className="form-label fw-semibold">{t("admin.catalog.code")}</label>
					<input
						type="text"
						className="form-control"
						value={form.code}
						onChange={(event) => setForm((current) => ({ ...current, code: event.target.value.toUpperCase() }))}
						disabled={submitting}
					/>
				</div>
				<div>
					<CatalogImagePreview
						src={flagPreviewSrc}
						alt={editingCountry ? `${editingCountry.name} flag` : t("admin.catalog.flagPreview")}
						variant="flag"
						previewLabel={t("admin.catalog.flagPreview")}
						fallbackLabel={t("admin.catalog.noFlag")}
						showLabel
						className="catalog-thumbnail--modal"
					/>
				</div>
				<div>
					<label className="form-label fw-semibold">{t("admin.catalog.flag")}</label>
					<input
						type="file"
						className="form-control"
						accept="image/*"
						onChange={handleFlagChange}
						disabled={submitting}
					/>
					<div className="form-text">{t("admin.catalog.imagePreview")}</div>
				</div>
				<div className="form-check">
					<input
						id="country-active"
						type="checkbox"
						className="form-check-input"
						checked={form.is_active}
						onChange={(event) =>
							setForm((current) => ({ ...current, is_active: event.target.checked }))
						}
						disabled={submitting}
					/>
					<label htmlFor="country-active" className="form-check-label">
						{t("admin.catalog.active")}
					</label>
				</div>
			</CatalogModal>
		</section>
	);
};

export default AdminCountriesPage;
