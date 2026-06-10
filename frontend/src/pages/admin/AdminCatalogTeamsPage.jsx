import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import CatalogImagePreview from "../../components/admin/CatalogImagePreview";
import CatalogModal from "../../components/admin/CatalogModal";
import {
	createAdminCatalogTeam,
	getAdminCatalogCountries,
	getAdminCatalogLeagues,
	getAdminCatalogTeams,
	updateAdminCatalogTeam,
} from "../../services/api";

import "../../styles/admin.css";

const buildTeamForm = (team = null) => ({
	name: team?.name || "",
	country_id: team?.country_id || "",
	league_id: team?.league_id || "",
	logo: null,
	is_verified: team?.is_verified ?? true,
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

const AdminCatalogTeamsPage = () => {
	const { t } = useTranslation();
	const [countries, setCountries] = useState([]);
	const [teams, setTeams] = useState([]);
	const [leagues, setLeagues] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [notice, setNotice] = useState("");
	const [filters, setFilters] = useState({
		q: "",
		country_id: "",
		league_id: "",
		verified: "all",
	});
	const [modalOpen, setModalOpen] = useState(false);
	const [editingTeam, setEditingTeam] = useState(null);
	const [form, setForm] = useState(buildTeamForm());
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
				const [countriesResponse, leaguesResponse, teamsResponse] = await Promise.all([
					getAdminCatalogCountries({ active: "all" }),
					getAdminCatalogLeagues({ active: "all" }),
					getAdminCatalogTeams(filters),
				]);
				if (cancelled) return;
				setCountries(Array.isArray(countriesResponse) ? countriesResponse : []);
				setLeagues(Array.isArray(leaguesResponse) ? leaguesResponse : []);
				setTeams(Array.isArray(teamsResponse) ? teamsResponse : []);
			} catch (loadError) {
				console.error("Failed to load catalog teams", loadError);
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

	const availableLeagues = useMemo(() => {
		if (!form.country_id) return [];
		return leagues.filter((league) => Number(league.country_id) === Number(form.country_id));
	}, [form.country_id, leagues]);

	const leagueFilterOptions = useMemo(() => {
		if (!filters.country_id) return leagues;
		return leagues.filter((league) => Number(league.country_id) === Number(filters.country_id));
	}, [filters.country_id, leagues]);

	const reloadTeams = async () => {
		const response = await getAdminCatalogTeams(filters);
		setTeams(Array.isArray(response) ? response : []);
	};

	const closeModal = () => {
		clearLogoPreviewObjectUrl();
		setModalOpen(false);
		setEditingTeam(null);
		setForm(buildTeamForm());
		setLogoPreviewSrc(null);
		setModalError("");
	};

	const openCreateModal = () => {
		clearLogoPreviewObjectUrl();
		setEditingTeam(null);
		setForm(buildTeamForm());
		setLogoPreviewSrc(null);
		setModalError("");
		setModalOpen(true);
	};

	const openEditModal = (team) => {
		clearLogoPreviewObjectUrl();
		setEditingTeam(team);
		setForm(buildTeamForm(team));
		setLogoPreviewSrc(team.logo || null);
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
				country_id: form.country_id || null,
				league_id: form.league_id || null,
				is_verified: form.is_verified,
			};
			if (form.logo instanceof File) {
				payload.logo = form.logo;
			}

			if (editingTeam) {
				await updateAdminCatalogTeam(editingTeam.id, payload);
				setNotice(t("admin.catalog.updated"));
			} else {
				await createAdminCatalogTeam(payload);
				setNotice(t("admin.catalog.created"));
			}
			await reloadTeams();
			closeModal();
		} catch (submitError) {
			console.error("Failed to save catalog team", submitError);
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

		setLogoPreviewSrc(editingTeam?.logo || null);
	};

	return (
		<section className="catalog-page moderation-section">
			<div className="admin-kit-types-header">
				<div>
					<h3 className="h4 fw-bold mb-1">{t("admin.catalog.teams")}</h3>
				</div>
				<button
					type="button"
					className="btn btn-primary"
					onClick={openCreateModal}
				>
					{t("admin.catalog.addTeam")}
				</button>
			</div>

			<div className="catalog-filter-bar catalog-filter-bar--teams">
				<div className="catalog-filter-field">
					<label htmlFor="teams-search" className="catalog-filter-label">
						{t("admin.catalog.searchTeams")}
					</label>
					<input
						id="teams-search"
						type="search"
						className="form-control catalog-filter-control"
						placeholder={t("admin.catalog.searchTeams")}
						value={filters.q}
						onChange={(event) =>
							setFilters((current) => ({ ...current, q: event.target.value }))
						}
					/>
				</div>
				<div className="catalog-filter-field">
					<label htmlFor="teams-country" className="catalog-filter-label">
						{t("admin.catalog.filterCountry")}
					</label>
					<select
						id="teams-country"
						className="form-select catalog-filter-control"
						value={filters.country_id}
						onChange={(event) =>
							setFilters((current) => ({
								...current,
								country_id: event.target.value,
								league_id: "",
							}))
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
					<label htmlFor="teams-league" className="catalog-filter-label">
						{t("admin.catalog.filterLeague")}
					</label>
					<select
						id="teams-league"
						className="form-select catalog-filter-control"
						value={filters.league_id}
						onChange={(event) =>
							setFilters((current) => ({ ...current, league_id: event.target.value }))
						}
					>
						<option value="">{t("admin.catalog.allLeagues")}</option>
						{leagueFilterOptions.map((league) => (
							<option key={league.id} value={league.id}>
								{league.name}
							</option>
						))}
					</select>
				</div>
				<div className="catalog-filter-field">
					<label htmlFor="teams-verification" className="catalog-filter-label">
						{t("admin.catalog.filterVerification")}
					</label>
					<select
						id="teams-verification"
						className="form-select catalog-filter-control"
						value={filters.verified}
						onChange={(event) =>
							setFilters((current) => ({ ...current, verified: event.target.value }))
						}
					>
						<option value="all">{t("admin.catalog.allTeams")}</option>
						<option value="verified">{t("admin.catalog.verified")}</option>
						<option value="unverified">{t("admin.catalog.unverified")}</option>
					</select>
				</div>
			</div>

			{notice ? <div className="alert alert-success">{notice}</div> : null}
			{error ? <div className="alert alert-danger">{error}</div> : null}
			{loading ? <div className="admin-kit-types-empty">Loading...</div> : null}
			{!loading && teams.length === 0 ? (
				<div className="admin-kit-types-empty">{t("admin.catalog.empty")}</div>
			) : null}

			{!loading && teams.length > 0 ? (
				<>
					<div className="catalog-table-wrapper">
						<table className="table align-middle catalog-table">
							<thead>
								<tr>
									<th>{t("admin.catalog.logo")}</th>
									<th>{t("admin.catalog.name")}</th>
									<th>{t("admin.catalog.country")}</th>
									<th>{t("admin.catalog.league")}</th>
									<th>{t("admin.catalog.verified")}</th>
									<th>Kits</th>
									<th>Uploads</th>
									<th>Wishlist</th>
									<th>Favorites</th>
									<th />
								</tr>
							</thead>
							<tbody>
								{teams.map((team) => (
									<tr key={team.id}>
										<td>
											<CatalogImagePreview
												src={team.logo}
												alt={`${team.name} logo`}
												variant="logo"
												fallbackLabel={t("admin.catalog.noLogo")}
												className="catalog-thumbnail--table"
											/>
										</td>
										<td>{team.name}</td>
										<td>{team.country_name || "N/A"}</td>
										<td>{team.league_name || "N/A"}</td>
										<td>
											<span className={`catalog-status-badge ${team.is_verified ? "is-active" : "is-inactive"}`}>
												{team.is_verified
													? t("admin.catalog.verified")
													: t("admin.catalog.unverified")}
											</span>
										</td>
										<td>{team.kits_count}</td>
										<td>{team.userkits_count}</td>
										<td>{team.wishlist_count}</td>
										<td>{team.favorite_team_count}</td>
										<td className="text-end">
											<button
												type="button"
												className="btn btn-outline-secondary btn-sm"
												onClick={() => openEditModal(team)}
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
						{teams.map((team) => (
							<article key={team.id} className="catalog-card">
								<div className="catalog-card-top">
									<CatalogImagePreview
										src={team.logo}
										alt={`${team.name} logo`}
										variant="logo"
										fallbackLabel={t("admin.catalog.noLogo")}
										className="catalog-thumbnail--card"
									/>
									<div>
										<div className="catalog-card-title">{team.name}</div>
										<div className="catalog-card-subtitle">
											{team.country_name || "N/A"} / {team.league_name || "N/A"}
										</div>
									</div>
									<span className={`catalog-status-badge ${team.is_verified ? "is-active" : "is-inactive"}`}>
										{team.is_verified
											? t("admin.catalog.verified")
											: t("admin.catalog.unverified")}
									</span>
								</div>
								<div className="catalog-card-meta">
									<span>Kits: {team.kits_count}</span>
									<span>Uploads: {team.userkits_count}</span>
									<span>Wishlist: {team.wishlist_count}</span>
									<span>Favorites: {team.favorite_team_count}</span>
								</div>
								<div className="catalog-card-actions">
										<button
											type="button"
											className="btn btn-outline-secondary btn-sm"
											onClick={() => openEditModal(team)}
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
				title={editingTeam ? t("admin.catalog.editTeam") : t("admin.catalog.addTeam")}
				onClose={closeModal}
				onSubmit={handleSubmit}
				submitting={submitting}
				error={modalError}
				submitLabel={editingTeam ? t("admin.catalog.save") : t("admin.catalog.create")}
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
				<div className="catalog-form-grid">
					<div>
						<label className="form-label fw-semibold">{t("admin.catalog.country")}</label>
						<select
							className="form-select"
							value={form.country_id}
							onChange={(event) =>
								setForm((current) => {
									const nextCountryId = event.target.value;
									const nextLeagues = leagues.filter(
										(league) => Number(league.country_id) === Number(nextCountryId),
									);
									const leagueStillValid = nextLeagues.some(
										(league) => Number(league.id) === Number(current.league_id),
									);
									return {
										...current,
										country_id: nextCountryId,
										league_id: leagueStillValid ? current.league_id : "",
									};
								})
							}
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
						<label className="form-label fw-semibold">{t("admin.catalog.league")}</label>
						<select
							className="form-select"
							value={form.league_id}
							onChange={(event) =>
								setForm((current) => ({ ...current, league_id: event.target.value }))
							}
							disabled={submitting || !form.country_id}
						>
							<option value="">{t("admin.catalog.noLeague")}</option>
							{availableLeagues.map((league) => (
								<option key={league.id} value={league.id}>
									{league.name}
								</option>
							))}
						</select>
					</div>
				</div>
				<div>
					<label className="form-label fw-semibold">{t("admin.catalog.logo")}</label>
					<CatalogImagePreview
						src={logoPreviewSrc}
						alt={editingTeam ? `${editingTeam.name} logo` : t("admin.catalog.logoPreview")}
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
				<div className="form-check">
					<input
						id="team-verified"
						type="checkbox"
						className="form-check-input"
						checked={form.is_verified}
						onChange={(event) =>
							setForm((current) => ({ ...current, is_verified: event.target.checked }))
						}
						disabled={submitting}
					/>
					<label htmlFor="team-verified" className="form-check-label">
						{t("admin.catalog.verified")}
					</label>
				</div>
			</CatalogModal>
		</section>
	);
};

export default AdminCatalogTeamsPage;
