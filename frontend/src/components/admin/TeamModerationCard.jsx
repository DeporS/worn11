import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

const getPlaceholderLabel = (teamName) => {
	return (teamName || "?")
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0]?.toUpperCase() || "")
		.join("");
};

const formatSeasonSummary = (seasons) => {
	const list = Array.isArray(seasons) ? seasons.filter(Boolean) : [];
	if (list.length === 0) {
		return "";
	}

	const visible = list.slice(0, 3);
	const remaining = list.length - visible.length;
	return `${visible.join(", ")}${remaining > 0 ? ` +${remaining}` : ""}`;
};

const TeamModerationCard = ({
	team,
	form,
	countries,
	leagues,
	leaguesLoading,
	onNameChange,
	onCountryChange,
	onLeagueChange,
	onApprove,
	onMerge,
	onReject,
	onDeleteContent,
	onOpenAddCountry,
	onOpenAddLeague,
	onMergeQueryChange,
	onMergeTargetSelect,
	onClearMergeTarget,
	onSearchMergeTargets,
	onEnsureLeagues,
}) => {
	const { t } = useTranslation();
	const [isMergeOpen, setIsMergeOpen] = useState(false);
	const [highlightedIndex, setHighlightedIndex] = useState(-1);
	const mergeRef = useRef(null);
	const seasonsLabel = useMemo(
		() => formatSeasonSummary(team.seasons),
		[team.seasons],
	);

	useEffect(() => {
		if (!form.countryId) return;
		onEnsureLeagues(form.countryId);
	}, [form.countryId, onEnsureLeagues]);

	useEffect(() => {
		const query = (form.mergeQuery || "").trim();
		if (
			query.length < 3 ||
			(form.mergeTarget?.name || "").trim() === query
		) {
			return undefined;
		}

		const timeoutId = window.setTimeout(() => {
			onSearchMergeTargets(team.id, query);
		}, 300);

		return () => window.clearTimeout(timeoutId);
	}, [
		form.mergeQuery,
		form.mergeTarget?.name,
		onSearchMergeTargets,
		team.id,
	]);

	useEffect(() => {
		if (!isMergeOpen) return undefined;

		const handlePointerDown = (event) => {
			if (!mergeRef.current?.contains(event.target)) {
				setIsMergeOpen(false);
				setHighlightedIndex(-1);
			}
		};

		document.addEventListener("mousedown", handlePointerDown);
		return () =>
			document.removeEventListener("mousedown", handlePointerDown);
	}, [isMergeOpen]);

	const mergeOptions = useMemo(() => {
		const seen = new Set();
		return [...(form.mergeResults || [])].filter((candidate) => {
			if (
				!candidate ||
				candidate.id === team.id ||
				seen.has(candidate.id)
			) {
				return false;
			}
			seen.add(candidate.id);
			return true;
		});
	}, [form.mergeResults, team.id]);

	useEffect(() => {
		if (!mergeOptions.length) {
			setHighlightedIndex(-1);
			return;
		}
		setHighlightedIndex((current) => {
			if (current >= 0 && current < mergeOptions.length) {
				return current;
			}
			return 0;
		});
	}, [mergeOptions]);

	const approveDisabled =
		form.busyAction !== null || !form.name.trim() || !form.countryId;
	const mergeDisabled = form.busyAction !== null || !form.mergeTarget?.id;

	const handleMergeSelection = (candidate) => {
		onMergeTargetSelect(team.id, candidate);
		setIsMergeOpen(false);
		setHighlightedIndex(-1);
	};

	const handleMergeInputKeyDown = (event) => {
		if (
			!isMergeOpen &&
			(event.key === "ArrowDown" || event.key === "ArrowUp")
		) {
			setIsMergeOpen(true);
			return;
		}

		if (event.key === "Escape") {
			setIsMergeOpen(false);
			setHighlightedIndex(-1);
			return;
		}

		if (!mergeOptions.length) {
			return;
		}

		if (event.key === "ArrowDown") {
			event.preventDefault();
			setHighlightedIndex((current) =>
				current < mergeOptions.length - 1 ? current + 1 : 0,
			);
			return;
		}

		if (event.key === "ArrowUp") {
			event.preventDefault();
			setHighlightedIndex((current) =>
				current > 0 ? current - 1 : mergeOptions.length - 1,
			);
			return;
		}

		if (event.key === "Enter" && highlightedIndex >= 0) {
			event.preventDefault();
			handleMergeSelection(mergeOptions[highlightedIndex]);
		}
	};

	const showNoResults =
		isMergeOpen &&
		!form.searchLoading &&
		(form.mergeQuery || "").trim().length >= 3 &&
		mergeOptions.length === 0;

	const mergeListId = `team-merge-options-${team.id}`;
	const blockedReason =
		team.reject_block_reason || t("moderation.teams.inUse");

	return (
		<article className="card shadow-sm border-0 team-moderation-card">
			<div className="team-moderation-card-preview">
				{team.preview_image ? (
					<img
						src={team.preview_image}
						alt={team.name}
						className="team-moderation-card-image"
					/>
				) : (
					<div className="team-moderation-card-placeholder">
						<span>{getPlaceholderLabel(team.name)}</span>
					</div>
				)}
			</div>

			<div className="card-body team-moderation-card-body">
				<div className="d-flex align-items-start justify-content-between gap-2">
					<div className="min-w-0">
						<div className="team-moderation-status-badge">
							{t("moderation.teams.pendingBadge")}
						</div>
						<h2 className="h6 fw-bold mt-2 mb-1 text-truncate">
							{team.name}
						</h2>
						<div className="team-moderation-slug text-muted small text-truncate">
							/{team.slug}
						</div>
					</div>
					<div className="team-moderation-context">
						{team.country_name ? (
							<div className="team-moderation-context-item">
								<span>{team.country_name}</span>
							</div>
						) : null}
						{team.league_name ? (
							<div className="team-moderation-context-item">
								<span>{team.league_name}</span>
							</div>
						) : null}
					</div>
				</div>

				<div className="team-moderation-stats">
					<div>
						{t("moderation.teams.kits", {
							count: team.kits_count || 0,
						})}
					</div>
					<div>
						{t("moderation.teams.uploads", {
							count: team.userkits_count || 0,
						})}
					</div>
					<div>
						{t("moderation.teams.users", {
							count: team.unique_users_count || 0,
						})}
					</div>
					<div>
						{t("moderation.teams.wishlistItems", {
							count: team.wishlist_count || 0,
						})}
					</div>
					<div>
						{t("moderation.teams.favorites", {
							count: team.favorite_team_count || 0,
						})}
					</div>
				</div>

				<div className="team-moderation-seasons">
					<div className="team-moderation-section-label">
						{t("moderation.teams.seasons")}
					</div>
					<div
						className="team-moderation-seasons-value text-truncate"
						title={
							Array.isArray(team.seasons)
								? team.seasons.join(", ")
								: ""
						}
					>
						{seasonsLabel || (
							<span className="text-muted small">-</span>
						)}
					</div>
				</div>

				<div className="team-moderation-feedback-area">
					{form.error ? (
						<div
							className="team-moderation-feedback-message team-moderation-feedback-message--error"
							role="alert"
							title={form.error}
						>
							{form.error}
						</div>
					) : null}

					{!form.error && !team.can_reject ? (
						<div
							className="team-moderation-blocked-note team-moderation-feedback-message"
							title={blockedReason}
						>
							{blockedReason}
						</div>
					) : null}
				</div>

				<div className="team-moderation-form-grid">
					<div>
						<label className="form-label fw-semibold">
							{t("moderation.teams.officialName")}
						</label>
						<input
							type="text"
							className={`form-control form-control-sm ${form.fieldErrors.name ? "is-invalid" : ""}`}
							value={form.name}
							onChange={(event) =>
								onNameChange(team.id, event.target.value)
							}
							disabled={form.busyAction !== null}
						/>
						{form.fieldErrors.name ? (
							<div className="invalid-feedback">
								{form.fieldErrors.name}
							</div>
						) : null}
					</div>

					<div>
						<div className="d-flex align-items-center justify-content-between gap-2 mb-2">
							<label className="form-label fw-semibold mb-0">
								{t("moderation.teams.country")}
							</label>
							<button
								type="button"
								className="btn btn-link btn-sm p-0 team-moderation-inline-action"
								onClick={() => onOpenAddCountry(team.id)}
								disabled={form.busyAction !== null}
							>
								{t("moderation.teams.addCountry")}
							</button>
						</div>
						<select
							className={`form-select form-select-sm ${form.fieldErrors.country ? "is-invalid" : ""}`}
							value={form.countryId}
							onChange={(event) =>
								onCountryChange(team.id, event.target.value)
							}
							disabled={form.busyAction !== null}
						>
							<option value="">
								{t("moderation.teams.selectCountry")}
							</option>
							{countries.map((country) => (
								<option key={country.id} value={country.id}>
									{country.name}
									{country.code ? ` (${country.code})` : ""}
								</option>
							))}
						</select>
						{form.fieldErrors.country ? (
							<div className="invalid-feedback">
								{form.fieldErrors.country}
							</div>
						) : null}
					</div>

					<div>
						<div className="d-flex align-items-center justify-content-between gap-2 mb-2">
							<label className="form-label fw-semibold mb-0">
								{t("moderation.teams.league")}
							</label>
							<button
								type="button"
								className="btn btn-link btn-sm p-0 team-moderation-inline-action"
								onClick={() => onOpenAddLeague(team.id)}
								disabled={
									form.busyAction !== null || !form.countryId
								}
							>
								{t("moderation.teams.addLeague")}
							</button>
						</div>
						<select
							className={`form-select form-select-sm ${form.fieldErrors.league ? "is-invalid" : ""}`}
							value={form.leagueId}
							onChange={(event) =>
								onLeagueChange(team.id, event.target.value)
							}
							disabled={
								form.busyAction !== null || !form.countryId
							}
						>
							<option value="">
								{t("moderation.teams.selectLeague")}
							</option>
							{leagues.map((league) => (
								<option key={league.id} value={league.id}>
									{league.name}
								</option>
							))}
						</select>
						{form.countryId && leaguesLoading ? (
							<div className="form-text">
								{t("common.loading")}
							</div>
						) : null}
						{!form.countryId ? (
							<div className="form-text">
								{t("moderation.teams.selectCountryFirst")}
							</div>
						) : null}
						{form.fieldErrors.league ? (
							<div className="invalid-feedback">
								{form.fieldErrors.league}
							</div>
						) : null}
					</div>
				</div>

				<div className="team-moderation-actions">
					<button
						type="button"
						className="btn btn-primary btn-sm"
						disabled={approveDisabled}
						onClick={() => onApprove(team.id)}
					>
						{t("moderation.teams.approve")}
					</button>
					<button
						type="button"
						className={`btn btn-sm ${team.can_reject ? "btn-outline-danger" : "btn-danger"}`}
						disabled={form.busyAction !== null}
						onClick={() => (team.can_reject ? onReject(team.id) : onDeleteContent(team.id))}
					>
						{team.can_reject
							? t("moderation.teams.reject")
							: t("moderation.teams.delete")}
					</button>
				</div>

				<div className="team-moderation-merge-panel">
					<div className="team-moderation-section-label">
						{t("moderation.teams.mergeInto")}
					</div>
					<div
						className="team-moderation-merge-combobox"
						ref={mergeRef}
					>
						<div className="team-moderation-merge-input-row">
							<input
								type="text"
								className={`form-control form-control-sm ${form.fieldErrors.merge ? "is-invalid" : ""}`}
								value={form.mergeQuery}
								onChange={(event) => {
									const nextValue = event.target.value;
									onMergeQueryChange(team.id, nextValue);
									setIsMergeOpen(
										nextValue.trim().length >= 3,
									);
								}}
								onFocus={() => {
									if (
										(form.mergeQuery || "").trim().length >=
										3
									) {
										setIsMergeOpen(true);
									}
								}}
								onKeyDown={handleMergeInputKeyDown}
								placeholder={t(
									"moderation.teams.searchVerifiedTeam",
								)}
								disabled={form.busyAction !== null}
								role="combobox"
								aria-expanded={isMergeOpen}
								aria-controls={mergeListId}
								aria-autocomplete="list"
								aria-activedescendant={
									highlightedIndex >= 0
										? `${mergeListId}-option-${highlightedIndex}`
										: undefined
								}
							/>
							{form.mergeTarget ? (
								<button
									type="button"
									className="btn btn-link btn-sm team-moderation-clear-merge"
									onClick={() => {
										onClearMergeTarget(team.id);
										setIsMergeOpen(false);
									}}
									disabled={form.busyAction !== null}
								>
									{t("moderation.teams.clearSelection")}
								</button>
							) : null}
						</div>
						{isMergeOpen ? (
							<div
								className="team-moderation-merge-dropdown"
								role="presentation"
							>
								{form.searchLoading ? (
									<div className="team-moderation-merge-status">
										{t("moderation.teams.searchingTeams")}
									</div>
								) : null}
								{!form.searchLoading &&
								mergeOptions.length > 0 ? (
									<div
										className="team-moderation-merge-list"
										role="listbox"
										id={mergeListId}
									>
										{mergeOptions.map(
											(candidate, index) => {
												const meta = [
													candidate.league_name,
													candidate.country_name ||
														candidate.country_code,
												]
													.filter(Boolean)
													.join(" • ");
												return (
													<button
														key={candidate.id}
														type="button"
														id={`${mergeListId}-option-${index}`}
														role="option"
														aria-selected={
															Number(
																form.mergeTarget
																	?.id,
															) ===
															Number(candidate.id)
														}
														className={`team-moderation-merge-option ${index === highlightedIndex ? "team-moderation-merge-option-active" : ""}`}
														onMouseEnter={() =>
															setHighlightedIndex(
																index,
															)
														}
														onClick={() =>
															handleMergeSelection(
																candidate,
															)
														}
													>
														{candidate.logo ? (
															<img
																src={
																	candidate.logo
																}
																alt=""
																className="team-moderation-merge-option-logo"
															/>
														) : (
															<span className="team-moderation-merge-option-fallback">
																{getPlaceholderLabel(
																	candidate.name,
																)}
															</span>
														)}
														<span className="team-moderation-merge-option-text">
															<span className="team-moderation-merge-option-name">
																{candidate.name}
															</span>
															{meta ? (
																<span className="team-moderation-merge-option-meta">
																	{meta}
																</span>
															) : null}
														</span>
													</button>
												);
											},
										)}
									</div>
								) : null}
								{showNoResults ? (
									<div className="team-moderation-merge-status">
										{t("moderation.teams.noTeamResults")}
									</div>
								) : null}
							</div>
						) : null}
					</div>
					{form.mergeTarget ? (
						<div className="team-moderation-selected-target">
							<span className="team-moderation-section-label">
								{t("moderation.teams.selectedMergeTarget")}
							</span>
							<span className="team-moderation-selected-target-name">
								{form.mergeTarget.name}
							</span>
						</div>
					) : null}
					{form.fieldErrors.merge ? (
						<div className="invalid-feedback d-block">
							{form.fieldErrors.merge}
						</div>
					) : null}

					<div className="team-moderation-merge-warning">
						{t("moderation.teams.mergeWarning")}
					</div>

					<button
						type="button"
						className="btn btn-outline-primary btn-sm"
						disabled={mergeDisabled}
						onClick={() => onMerge(team.id)}
					>
						{t("moderation.teams.merge")}
					</button>
				</div>
			</div>
		</article>
	);
};

export default TeamModerationCard;
