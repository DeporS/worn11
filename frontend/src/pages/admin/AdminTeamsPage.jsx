import { useCallback, useMemo, useRef, useState } from "react";
import { useEffect } from "react";
import { useOutletContext } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import {
	approveTeam,
	createAdminCountry,
	createAdminLeague,
	deleteTeamContent,
	getAdminCountries,
	getAdminLeagues,
	getUnverifiedTeams,
	mergeTeam,
	rejectTeam,
	searchVerifiedTeams,
} from "../../services/api";
import AddCountryModal from "../../components/admin/AddCountryModal";
import AddLeagueModal from "../../components/admin/AddLeagueModal";
import TeamModerationCard from "../../components/admin/TeamModerationCard";

import "../../styles/admin.css";

const sortCountries = (countries) =>
	[...(Array.isArray(countries) ? countries : [])].sort((left, right) =>
		(left.name || "").localeCompare(right.name || ""),
	);

const DELETE_REASON_OPTIONS = [
	"spam",
	"offensive_name",
	"invalid_team",
	"duplicate_abuse",
	"other",
];

const escapeHtml = (value) =>
	String(value ?? "")
		.replaceAll("&", "&amp;")
		.replaceAll("<", "&lt;")
		.replaceAll(">", "&gt;")
		.replaceAll('"', "&quot;")
		.replaceAll("'", "&#39;");

const buildInitialForm = (team, previousForm = {}) => ({
	name:
		typeof previousForm.name === "string" ? previousForm.name : team.name || "",
	countryId:
		previousForm.countryId !== undefined
			? previousForm.countryId
			: team.country_id || "",
	leagueId:
		previousForm.leagueId !== undefined ? previousForm.leagueId : team.league_id || "",
	mergeTarget: previousForm.mergeTarget || null,
	mergeQuery: previousForm.mergeQuery || "",
	mergeResults: previousForm.mergeResults || [],
	searchLoading: previousForm.searchLoading || false,
	busyAction: previousForm.busyAction || null,
	error: previousForm.error || "",
	fieldErrors: previousForm.fieldErrors || {},
});

const AdminTeamsPage = () => {
	const { t } = useTranslation();
	const { refreshModerationSummary } = useOutletContext() || {};
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [notice, setNotice] = useState("");
	const [teams, setTeams] = useState([]);
	const [countries, setCountries] = useState([]);
	const [formsByTeamId, setFormsByTeamId] = useState({});
	const [leaguesByCountryId, setLeaguesByCountryId] = useState({});
	const [leaguesLoadingByCountryId, setLeaguesLoadingByCountryId] = useState({});
	const [countryModalState, setCountryModalState] = useState({
		open: false,
		teamId: null,
		submitting: false,
		error: "",
	});
	const [leagueModalState, setLeagueModalState] = useState({
		open: false,
		teamId: null,
		countryId: null,
		submitting: false,
		error: "",
	});

	const leagueRequestCacheRef = useRef({});
	const mergeSearchRequestIdsRef = useRef({});

	const hydrateForms = useCallback((incomingTeams) => {
		setFormsByTeamId((current) => {
			const next = {};
			for (const team of incomingTeams) {
				next[team.id] = buildInitialForm(team, current[team.id]);
			}
			return next;
		});
	}, []);

	useEffect(() => {
		let cancelled = false;

		const loadPage = async () => {
			setLoading(true);
			setError("");
			try {
				const [teamsResponse, countriesResponse] = await Promise.all([
					getUnverifiedTeams(),
					getAdminCountries(),
				]);
				if (cancelled) return;

				const nextTeams = Array.isArray(teamsResponse?.results)
					? teamsResponse.results
					: [];
				setTeams(nextTeams);
				setCountries(sortCountries(countriesResponse));
				hydrateForms(nextTeams);
			} catch (loadError) {
				console.error("Failed to load team moderation data", loadError);
				if (!cancelled) {
					setError(t("moderation.teams.loadError"));
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
	}, [hydrateForms, t]);

	const pendingCountLabel = useMemo(
		() => t("moderation.teams.pendingCount", { count: teams.length }),
		[t, teams.length],
	);

	const updateForm = useCallback((teamId, updater) => {
		setFormsByTeamId((current) => {
			const previous = current[teamId];
			if (!previous) return current;
			const nextValue =
				typeof updater === "function" ? updater(previous) : { ...previous, ...updater };
			return {
				...current,
				[teamId]: nextValue,
			};
		});
	}, []);

	const removeTeamFromQueue = useCallback((teamId) => {
		setTeams((current) => current.filter((team) => team.id !== teamId));
		setFormsByTeamId((current) => {
			const next = { ...current };
			delete next[teamId];
			return next;
		});
	}, []);

	const updateTeamRecord = useCallback((teamId, updater) => {
		setTeams((current) =>
			current.map((team) =>
				team.id === teamId ? { ...team, ...(typeof updater === "function" ? updater(team) : updater) } : team,
			),
		);
	}, []);

	const ensureLeagues = useCallback(async (countryId) => {
		const normalizedCountryId = Number(countryId);
		if (!normalizedCountryId) return [];

		if (Array.isArray(leaguesByCountryId[normalizedCountryId])) {
			return leaguesByCountryId[normalizedCountryId];
		}

		if (leagueRequestCacheRef.current[normalizedCountryId]) {
			return leagueRequestCacheRef.current[normalizedCountryId];
		}

		setLeaguesLoadingByCountryId((current) => ({
			...current,
			[normalizedCountryId]: true,
		}));

		const request = getAdminLeagues(normalizedCountryId)
			.then((response) => {
				const nextLeagues = Array.isArray(response) ? response : [];
				setLeaguesByCountryId((current) => ({
					...current,
					[normalizedCountryId]: nextLeagues,
				}));
				return nextLeagues;
			})
			.catch((loadError) => {
				console.error("Failed to load leagues for country", loadError);
				throw loadError;
			})
			.finally(() => {
				setLeaguesLoadingByCountryId((current) => ({
					...current,
					[normalizedCountryId]: false,
				}));
				delete leagueRequestCacheRef.current[normalizedCountryId];
			});

		leagueRequestCacheRef.current[normalizedCountryId] = request;
		return request;
	}, [leaguesByCountryId]);

	const handleNameChange = useCallback((teamId, value) => {
		updateForm(teamId, (current) => ({
			...current,
			name: value,
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				name: "",
			},
		}));
	}, [updateForm]);

	const handleCountryChange = useCallback((teamId, value) => {
		const nextCountryId = value ? Number(value) : "";
		updateForm(teamId, (current) => ({
			...current,
			countryId: nextCountryId,
			leagueId: "",
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				country: "",
				league: "",
			},
		}));

		if (nextCountryId) {
			ensureLeagues(nextCountryId).catch(() => {});
		}
	}, [ensureLeagues, updateForm]);

	const handleLeagueChange = useCallback((teamId, value) => {
		updateForm(teamId, (current) => ({
			...current,
			leagueId: value ? Number(value) : "",
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				league: "",
			},
		}));
	}, [updateForm]);

	const handleMergeQueryChange = useCallback((teamId, value) => {
		updateForm(teamId, (current) => ({
			...current,
			mergeQuery: value,
			mergeTarget: null,
			mergeResults: value.trim().length < 3 ? [] : current.mergeResults,
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				merge: "",
			},
		}));
	}, [updateForm]);

	const handleMergeTargetSelect = useCallback((teamId, candidate) => {
		updateForm(teamId, (current) => ({
			...current,
			mergeTarget: candidate || null,
			mergeQuery: candidate?.name || "",
			mergeResults: candidate ? [] : current.mergeResults,
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				merge: "",
			},
		}));
	}, [updateForm]);

	const handleSearchMergeTargets = useCallback(async (teamId, query) => {
		const normalizedQuery = query.trim();
		if (normalizedQuery.length < 3) {
			updateForm(teamId, (current) => ({
				...current,
				searchLoading: false,
				mergeResults: [],
			}));
			return;
		}

		const requestId = (mergeSearchRequestIdsRef.current[teamId] || 0) + 1;
		mergeSearchRequestIdsRef.current[teamId] = requestId;

		updateForm(teamId, (current) => ({
			...current,
			searchLoading: true,
		}));

		try {
			const response = await searchVerifiedTeams(normalizedQuery);
			updateForm(teamId, (current) => ({
				...current,
				searchLoading:
					mergeSearchRequestIdsRef.current[teamId] === requestId
						? false
						: current.searchLoading,
				mergeResults:
					mergeSearchRequestIdsRef.current[teamId] === requestId &&
					current.mergeQuery.trim() === normalizedQuery
						? Array.isArray(response)
							? response
							: []
						: current.mergeResults,
			}));
		} catch (searchError) {
			console.error("Failed to search verified teams", searchError);
			updateForm(teamId, (current) => ({
				...current,
				searchLoading:
					mergeSearchRequestIdsRef.current[teamId] === requestId
						? false
						: current.searchLoading,
				mergeResults:
					mergeSearchRequestIdsRef.current[teamId] === requestId &&
					current.mergeQuery.trim() === normalizedQuery
						? []
						: current.mergeResults,
			}));
		}
	}, [updateForm]);

	const handleClearMergeTarget = useCallback((teamId) => {
		updateForm(teamId, (current) => ({
			...current,
			mergeTarget: null,
			mergeQuery: "",
			mergeResults: [],
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				merge: "",
			},
		}));
	}, [updateForm]);

	const handleOpenAddCountry = useCallback((teamId) => {
		setCountryModalState({
			open: true,
			teamId,
			submitting: false,
			error: "",
		});
	}, []);

	const handleOpenAddLeague = useCallback((teamId) => {
		const form = formsByTeamId[teamId];
		if (!form?.countryId) {
			updateForm(teamId, (current) => ({
				...current,
				fieldErrors: {
					...current.fieldErrors,
					country: t("moderation.teams.selectCountryFirst"),
				},
			}));
			return;
		}

		setLeagueModalState({
			open: true,
			teamId,
			countryId: Number(form.countryId),
			submitting: false,
			error: "",
		});
	}, [formsByTeamId, t, updateForm]);

	const closeCountryModal = useCallback(() => {
		setCountryModalState({
			open: false,
			teamId: null,
			submitting: false,
			error: "",
		});
	}, []);

	const closeLeagueModal = useCallback(() => {
		setLeagueModalState({
			open: false,
			teamId: null,
			countryId: null,
			submitting: false,
			error: "",
		});
	}, []);

	const handleCreateCountry = useCallback(async (payload) => {
		setCountryModalState((current) => ({
			...current,
			submitting: true,
			error: "",
		}));

		try {
			const createdCountry = await createAdminCountry(payload);
			setCountries((current) => sortCountries([...current, createdCountry]));
			if (countryModalState.teamId) {
				updateForm(countryModalState.teamId, (current) => ({
					...current,
					countryId: createdCountry.id,
					leagueId: "",
					fieldErrors: {
						...current.fieldErrors,
						country: "",
						league: "",
					},
				}));
			}
			setNotice(t("moderation.countries.created"));
			closeCountryModal();
		} catch (createError) {
			console.error("Failed to create country", createError);
			setCountryModalState((current) => ({
				...current,
				submitting: false,
				error: createError?.response?.data?.detail || t("moderation.countries.error"),
			}));
		}
	}, [closeCountryModal, countryModalState.teamId, t, updateForm]);

	const handleCreateLeague = useCallback(async (payload) => {
		setLeagueModalState((current) => ({
			...current,
			submitting: true,
			error: "",
		}));

		try {
			const createdLeague = await createAdminLeague(payload);
			setLeaguesByCountryId((current) => ({
				...current,
				[payload.country_id]: [...(current[payload.country_id] || []), createdLeague].sort((left, right) => {
					if ((left.order || 0) !== (right.order || 0)) {
						return (left.order || 0) - (right.order || 0);
					}
					return (left.name || "").localeCompare(right.name || "");
				}),
			}));
			if (leagueModalState.teamId) {
				updateForm(leagueModalState.teamId, (current) => ({
					...current,
					leagueId: createdLeague.id,
					fieldErrors: {
						...current.fieldErrors,
						league: "",
					},
				}));
			}
			setNotice(t("moderation.leagues.created"));
			closeLeagueModal();
		} catch (createError) {
			console.error("Failed to create league", createError);
			setLeagueModalState((current) => ({
				...current,
				submitting: false,
				error: createError?.response?.data?.detail || t("moderation.leagues.error"),
			}));
		}
	}, [closeLeagueModal, leagueModalState.teamId, t, updateForm]);

	const handleApprove = useCallback(async (teamId) => {
		const team = teams.find((entry) => entry.id === teamId);
		const form = formsByTeamId[teamId];
		if (!form || !team) return;

		const trimmedName = form.name.trim();
		const fieldErrors = {};
		if (!trimmedName) {
			fieldErrors.name = t("moderation.teams.nameRequired");
		}
		if (!form.countryId) {
			fieldErrors.country = t("moderation.teams.countryRequired");
		}
		if (Object.keys(fieldErrors).length > 0) {
			updateForm(teamId, (current) => ({
				...current,
				fieldErrors: {
					...current.fieldErrors,
					...fieldErrors,
				},
			}));
			return;
		}

		updateForm(teamId, (current) => ({
			...current,
			busyAction: "approve",
			error: "",
			fieldErrors: {},
		}));

		try {
			await approveTeam(teamId, {
				name: trimmedName,
				country_id: Number(form.countryId),
				league_id: form.leagueId ? Number(form.leagueId) : null,
			});
			removeTeamFromQueue(teamId);
			setNotice(t("moderation.teams.approveSuccess"));
			await refreshModerationSummary?.();
		} catch (actionError) {
			console.error("Failed to approve team", actionError);
			const payload = actionError?.response?.data || {};

			updateForm(teamId, (current) => {
				const nextFieldErrors = {};
				let nextError = payload.detail || t("moderation.teams.actionError");

				if (payload.country_id) {
					nextFieldErrors.country = Array.isArray(payload.country_id)
						? payload.country_id[0]
						: payload.country_id;
				}
				if (payload.league_id) {
					nextFieldErrors.league = Array.isArray(payload.league_id)
						? payload.league_id[0]
						: payload.league_id;
				}
				if (payload.name) {
					nextFieldErrors.name = Array.isArray(payload.name)
						? payload.name[0]
						: payload.name;
				}
				if (payload.code === "league_country_mismatch") {
					nextFieldErrors.league = nextError;
				}
				if (payload.code === "team_name_conflict") {
					nextError = t("moderation.teams.nameConflict");
				}
				const conflictCandidate =
					payload.code === "team_name_conflict" && payload.existing_team_id
						? (current.mergeResults || []).find(
								(candidate) => Number(candidate.id) === Number(payload.existing_team_id),
						  ) || {
								id: payload.existing_team_id,
								name: `#${payload.existing_team_id}`,
						  }
						: null;

				return {
					...current,
					busyAction: null,
					leagueId:
						payload.code === "league_country_mismatch" ? "" : current.leagueId,
					mergeTarget: conflictCandidate || current.mergeTarget,
					mergeQuery: conflictCandidate?.name || current.mergeQuery,
					error: nextError,
					fieldErrors: nextFieldErrors,
				};
			});
			return;
		}

		updateForm(teamId, (current) => ({
			...current,
			busyAction: null,
		}));
	}, [formsByTeamId, removeTeamFromQueue, t, updateForm]);

	const handleMerge = useCallback(async (teamId) => {
		const team = teams.find((entry) => entry.id === teamId);
		const form = formsByTeamId[teamId];
		if (!team || !form) return;

		if (!form.mergeTarget?.id) {
			updateForm(teamId, (current) => ({
				...current,
				fieldErrors: {
					...current.fieldErrors,
					merge: t("moderation.teams.selectMergeTarget"),
				},
			}));
			return;
		}

		const targetName = form.mergeTarget?.name || `#${form.mergeTarget.id}`;

		const result = await Swal.fire({
			title: t("moderation.teams.merge"),
			text: `${team.name} -> ${targetName}. ${t("moderation.teams.mergeWarning")}`,
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("moderation.teams.merge"),
			cancelButtonText: t("common.cancel"),
		});
		if (!result.isConfirmed) return;

		updateForm(teamId, (current) => ({
			...current,
			busyAction: "merge",
			error: "",
			fieldErrors: {
				...current.fieldErrors,
				merge: "",
			},
		}));

		try {
			const response = await mergeTeam(teamId, Number(form.mergeTarget.id));
			removeTeamFromQueue(teamId);
			const mergedCount = response?.moved_kits || response?.merged_duplicate_kits;
			setNotice(
				mergedCount
					? `${t("moderation.teams.mergeSuccess")} (${mergedCount})`
					: t("moderation.teams.mergeSuccess"),
			);
			await refreshModerationSummary?.();
		} catch (actionError) {
			console.error("Failed to merge team", actionError);
			const payload = actionError?.response?.data || {};
			updateForm(teamId, (current) => ({
				...current,
				busyAction: null,
				error: payload.detail || t("moderation.teams.actionError"),
				fieldErrors: {
					...current.fieldErrors,
					merge: payload.target_team_id || "",
				},
			}));
		}
	}, [formsByTeamId, removeTeamFromQueue, t, teams, updateForm]);

	const handleReject = useCallback(async (teamId) => {
		const team = teams.find((entry) => entry.id === teamId);
		if (!team) return;
		if (!team.can_reject) return;

		const result = await Swal.fire({
			title: t("moderation.teams.reject"),
			text: t("moderation.teams.rejectWarning"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("moderation.teams.reject"),
			cancelButtonText: t("common.cancel"),
		});
		if (!result.isConfirmed) return;

		updateForm(teamId, (current) => ({
			...current,
			busyAction: "reject",
			error: "",
			fieldErrors: {},
		}));

		try {
			await rejectTeam(teamId);
			removeTeamFromQueue(teamId);
			setNotice(t("moderation.teams.rejectSuccess"));
			await refreshModerationSummary?.();
		} catch (actionError) {
			console.error("Failed to reject team", actionError);
			const payload = actionError?.response?.data || {};

			if (payload.code === "team_in_use") {
				const usage = payload.usage || {};
				updateTeamRecord(teamId, {
					can_reject: false,
					reject_block_reason: payload.detail || t("moderation.teams.inUse"),
					kits_count: usage.kits ?? team.kits_count,
					userkits_count: usage.userkits ?? team.userkits_count,
					wishlist_count: usage.wishlist_items ?? team.wishlist_count,
					favorite_team_count: usage.favorite_profiles ?? team.favorite_team_count,
					usage: {
						kits: usage.kits ?? team.usage?.kits,
						orphan_kits: usage.orphan_kits ?? team.usage?.orphan_kits,
						userkits: usage.userkits ?? team.usage?.userkits,
						wishlist_items: usage.wishlist_items ?? team.usage?.wishlist_items,
						favorite_profiles: usage.favorite_profiles ?? team.usage?.favorite_profiles,
						team_season_types: usage.team_season_types ?? team.usage?.team_season_types,
						approved_team_season_types:
							usage.approved_team_season_types ??
							team.usage?.approved_team_season_types,
						pending_team_season_types:
							usage.pending_team_season_types ??
							team.usage?.pending_team_season_types,
						rejected_team_season_types:
							usage.rejected_team_season_types ??
							team.usage?.rejected_team_season_types,
					},
				});
			}

			updateForm(teamId, (current) => ({
				...current,
				busyAction: null,
				error: payload.detail || t("moderation.teams.actionError"),
			}));
		}
	}, [removeTeamFromQueue, t, teams, updateForm, updateTeamRecord]);

	const handleDeleteContent = useCallback(async (teamId) => {
		const team = teams.find((entry) => entry.id === teamId);
		if (!team) return;
		const escapedTeamName = escapeHtml(team.name);
		const reasonLabelByCode = {
			spam: t("moderation.teams.deleteReasonSpam"),
			offensive_name: t("moderation.teams.deleteReasonOffensive"),
			invalid_team: t("moderation.teams.deleteReasonInvalid"),
			duplicate_abuse: t("moderation.teams.deleteReasonDuplicateAbuse"),
			other: t("moderation.teams.deleteReasonOther"),
		};

		const result = await Swal.fire({
			title: t("moderation.teams.deleteTitle"),
			icon: "warning",
			showCancelButton: true,
			confirmButtonText: t("moderation.teams.delete"),
			cancelButtonText: t("common.cancel"),
			focusConfirm: false,
			html: `
				<div class="text-start">
					<p class="mb-3">${escapeHtml(t("moderation.teams.deleteWarning"))}</p>
					<ul class="small text-muted ps-3 mb-3">
						<li>${escapeHtml(t("moderation.teams.uploads", { count: team.userkits_count || 0 }))}</li>
						<li>${escapeHtml(t("moderation.teams.wishlistItems", { count: team.wishlist_count || 0 }))}</li>
						<li>${escapeHtml(t("moderation.teams.favorites", { count: team.favorite_team_count || 0 }))}</li>
						<li>${team.usage?.team_season_types || 0} Kit Museum suggestions</li>
					</ul>
					<label class="form-label fw-semibold" for="swal-delete-reason">${escapeHtml(t("moderation.teams.deleteReason"))}</label>
					<select id="swal-delete-reason" class="swal2-select">
						<option value="">${escapeHtml(t("moderation.teams.deleteReason"))}</option>
						${DELETE_REASON_OPTIONS.map((reason) => `<option value="${reason}">${escapeHtml(reasonLabelByCode[reason])}</option>`).join("")}
					</select>
					<label class="form-label fw-semibold mt-3" for="swal-delete-note">${escapeHtml(t("moderation.teams.deleteNote"))}</label>
					<textarea id="swal-delete-note" class="swal2-textarea" placeholder="${escapeHtml(t("moderation.teams.deleteNote"))}"></textarea>
					<label class="form-label fw-semibold mt-3" for="swal-delete-confirmation">${escapeHtml(t("moderation.teams.deleteConfirmationLabel", { team: team.name }))}</label>
					<input id="swal-delete-confirmation" class="swal2-input" autocomplete="off" />
					<p class="small text-danger mb-0">${escapeHtml(t("moderation.teams.irreversible"))}</p>
					<p class="small text-muted mb-0 mt-2"><code>${escapedTeamName}</code></p>
				</div>
			`,
			preConfirm: () => {
				const reason = document.getElementById("swal-delete-reason")?.value || "";
				const note = document.getElementById("swal-delete-note")?.value || "";
				const confirmation = document.getElementById("swal-delete-confirmation")?.value || "";

				if (!reason) {
					Swal.showValidationMessage(t("moderation.teams.deleteReason"));
					return false;
				}
				if (confirmation.trim() !== team.name) {
					Swal.showValidationMessage(
						t("moderation.teams.deleteConfirmationLabel", { team: team.name }),
					);
					return false;
				}

				return { reason, note, confirmation };
			},
		});

		if (!result.isConfirmed || !result.value) return;

		updateForm(teamId, (current) => ({
			...current,
			busyAction: "delete-content",
			error: "",
			fieldErrors: {},
		}));

		try {
			await deleteTeamContent(teamId, result.value);
			removeTeamFromQueue(teamId);
			setNotice(t("moderation.teams.deleteSuccess"));
			await refreshModerationSummary?.();
		} catch (actionError) {
			console.error("Failed to delete team content", actionError);
			const payload = actionError?.response?.data || {};
			updateForm(teamId, (current) => ({
				...current,
				busyAction: null,
				error: payload.detail || t("moderation.teams.deleteError"),
			}));
			return;
		}

		updateForm(teamId, (current) => ({
			...current,
			busyAction: null,
		}));
	}, [removeTeamFromQueue, t, teams, updateForm]);

	return (
		<section className="admin-teams-page moderation-section">
			<div className="admin-kit-types-header team-moderation-page-header">
				<div>
					<h2 className="fw-bold mb-1">{t("moderation.teams.title")}</h2>
					<p className="text-muted mb-0">
						{t("moderation.teams.description")}
					</p>
				</div>
				<div className="team-moderation-summary-pill">{pendingCountLabel}</div>
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

			{!loading && !error && notice ? (
				<div className="alert alert-success" role="status">
					{notice}
				</div>
			) : null}

			{!loading && !error && teams.length === 0 ? (
				<div className="admin-kit-types-empty">{t("moderation.teams.empty")}</div>
			) : null}

			{!loading && !error && teams.length > 0 ? (
				<div className="team-moderation-grid">
					{teams.map((team) => {
						const form = formsByTeamId[team.id] || buildInitialForm(team);
						const selectedCountryId = Number(form.countryId) || null;
						return (
							<TeamModerationCard
								key={team.id}
								team={team}
								form={form}
								countries={countries}
								leagues={selectedCountryId ? leaguesByCountryId[selectedCountryId] || [] : []}
								leaguesLoading={Boolean(selectedCountryId && leaguesLoadingByCountryId[selectedCountryId])}
								onNameChange={handleNameChange}
								onCountryChange={handleCountryChange}
								onLeagueChange={handleLeagueChange}
								onApprove={handleApprove}
								onMerge={handleMerge}
								onReject={handleReject}
								onDeleteContent={handleDeleteContent}
								onOpenAddCountry={handleOpenAddCountry}
								onOpenAddLeague={handleOpenAddLeague}
								onMergeQueryChange={handleMergeQueryChange}
								onMergeTargetSelect={handleMergeTargetSelect}
								onClearMergeTarget={handleClearMergeTarget}
								onSearchMergeTargets={handleSearchMergeTargets}
								onEnsureLeagues={ensureLeagues}
							/>
						);
					})}
				</div>
			) : null}

			<AddCountryModal
				isOpen={countryModalState.open}
				onClose={closeCountryModal}
				onSubmit={handleCreateCountry}
				submitting={countryModalState.submitting}
				error={countryModalState.error}
			/>

			<AddLeagueModal
				isOpen={leagueModalState.open}
				onClose={closeLeagueModal}
				onSubmit={handleCreateLeague}
				submitting={leagueModalState.submitting}
				error={leagueModalState.error}
				countries={countries}
				selectedCountryId={leagueModalState.countryId}
			/>
		</section>
	);
};

export default AdminTeamsPage;
