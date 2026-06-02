import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import CommentsModal from "../components/comments/CommentsModal";
import { getExploreKits, searchKitSuggestions, searchUsers } from "../services/api";
import SearchBar from "../components/SearchBar";
import UserCard from "../components/UserCard";
import ExploreKitCard from "../components/explore/ExploreKitCard";

const EXPLORE_SECTIONS = [
	{ key: "trending", labelKey: "explore.trending", sort: "trending" },
	{ key: "most_liked", labelKey: "explore.mostLiked", sort: "most_liked" },
	{ key: "latest", labelKey: "explore.latest", sort: "latest" },
	{ key: "for_sale", labelKey: "explore.forSale", sort: "for_sale" },
];

const SECTION_LIMIT = 8;
const KIT_SUGGESTION_LIMIT = 8;

const createSectionState = () =>
	EXPLORE_SECTIONS.reduce((acc, section) => {
		acc[section.key] = {
			items: [],
			loading: true,
			error: null,
		};
		return acc;
	}, {});

const CollectionPage = ({ user }) => {
	const { t } = useTranslation();
	const [kitSuggestions, setKitSuggestions] = useState([]);
	const [users, setUsers] = useState([]);
	const [loadingKits, setLoadingKits] = useState(false);
	const [loadingUsers, setLoadingUsers] = useState(false);
	const [searchError, setSearchError] = useState(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [exploreSections, setExploreSections] = useState(createSectionState);
	const [selectedKit, setSelectedKit] = useState(null);
	const [selectedImageIndex, setSelectedImageIndex] = useState(0);

	const trimmedQuery = searchQuery.trim();
	const hasActiveSearch = trimmedQuery.length > 0;
	const canRunKitSearch = trimmedQuery.length >= 2;
	const canRunUserSearch = trimmedQuery.length >= 3;
	const isFirstSearchLoad =
		(loadingKits || loadingUsers) &&
		kitSuggestions.length === 0 &&
		users.length === 0 &&
		!searchError &&
		(canRunKitSearch || canRunUserSearch);

	useEffect(() => {
		if (!hasActiveSearch) {
			setKitSuggestions([]);
			setUsers([]);
			setSearchError(null);
			setLoadingKits(false);
			setLoadingUsers(false);
			return;
		}

		if (!canRunKitSearch && !canRunUserSearch) {
			setKitSuggestions([]);
			setUsers([]);
			setLoadingKits(false);
			setLoadingUsers(false);
			return;
		}

		let cancelled = false;

		const delayDebounceFn = window.setTimeout(() => {
			setSearchError(null);
			setLoadingKits(canRunKitSearch);
			setLoadingUsers(canRunUserSearch);

			const kitPromise = canRunKitSearch
				? searchKitSuggestions(trimmedQuery, KIT_SUGGESTION_LIMIT)
				: Promise.resolve([]);
			const userPromise = canRunUserSearch
				? searchUsers(trimmedQuery)
				: Promise.resolve([]);

			Promise.allSettled([kitPromise, userPromise]).then((results) => {
				if (cancelled) return;

				const [kitResult, userResult] = results;
				const nextKitSuggestions =
					kitResult.status === "fulfilled" && Array.isArray(kitResult.value)
						? kitResult.value
						: [];
				const nextUsers =
					userResult.status === "fulfilled" && Array.isArray(userResult.value)
						? userResult.value
						: [];
				const hasFailedRequest =
					kitResult.status === "rejected" || userResult.status === "rejected";

				if (kitResult.status === "rejected") {
					console.error(kitResult.reason);
				}
				if (userResult.status === "rejected") {
					console.error(userResult.reason);
				}

				setKitSuggestions(nextKitSuggestions);
				setUsers(nextUsers);
				setSearchError(hasFailedRequest ? t("explore.searchError") : null);
				setLoadingKits(false);
				setLoadingUsers(false);
			});
		}, 500);

		return () => {
			cancelled = true;
			window.clearTimeout(delayDebounceFn);
		};
	}, [trimmedQuery, canRunKitSearch, canRunUserSearch, hasActiveSearch, t]);

	useEffect(() => {
		if (hasActiveSearch) return;

		let cancelled = false;

		const loadExploreSections = async () => {
			setExploreSections(createSectionState());

			const results = await Promise.allSettled(
				EXPLORE_SECTIONS.map((section) =>
					getExploreKits(section.sort, SECTION_LIMIT),
				),
			);

			if (cancelled) return;

			setExploreSections(
				results.reduce((acc, result, index) => {
					const section = EXPLORE_SECTIONS[index];
					if (result.status === "fulfilled") {
						acc[section.key] = {
							items: Array.isArray(result.value) ? result.value : [],
							loading: false,
							error: null,
						};
					} else {
						console.error(`Failed to load ${section.key} kits`, result.reason);
						acc[section.key] = {
							items: [],
							loading: false,
							error: t("explore.sectionError"),
						};
					}
					return acc;
				}, {}),
			);
		};

		loadExploreSections();

		return () => {
			cancelled = true;
		};
	}, [hasActiveSearch, t]);

	const renderSearchResults = () => (
		<section>
			{searchError && (
				<div className="alert alert-danger text-center">{searchError}</div>
			)}

			{isFirstSearchLoad && (
				<div className="text-center py-5">
					<div
						className="spinner-border text-primary"
						style={{ width: "3rem", height: "3rem" }}
					></div>
				</div>
			)}

			{!canRunKitSearch && !canRunUserSearch && (
				<div className="text-center text-muted py-5">
					{t("explore.searchHint")}
				</div>
			)}

			<div
				style={{
					opacity:
						(loadingKits && kitSuggestions.length > 0) ||
						(loadingUsers && users.length > 0)
							? 0.5
							: 1,
					transition: "opacity 0.2s ease-in-out",
				}}
			>
				{kitSuggestions.length > 0 && (
					<section className="mb-5">
						<h2 className="h4 fw-bold mb-3">{t("search.kits")}</h2>
						<div className="list-group shadow-sm">
							{kitSuggestions.map((suggestion) => (
								<button
									key={`${suggestion.team_id}-${suggestion.season}-${suggestion.kit_type}`}
									type="button"
									className="list-group-item list-group-item-action d-flex align-items-center gap-3 py-3"
									onClick={() => navigate(suggestion.url)}
								>
									<div
										className="flex-shrink-0 rounded-3 overflow-hidden d-flex align-items-center justify-content-center bg-light border"
										style={{ width: "52px", height: "52px" }}
									>
										{suggestion.preview_image ? (
											<img
												src={suggestion.preview_image}
												alt={suggestion.label}
												style={{
													width: "100%",
													height: "100%",
													objectFit: "cover",
												}}
											/>
										) : (
											<i className="bi bi-search text-muted"></i>
										)}
									</div>
									<div className="min-w-0 text-start">
										<div className="fw-medium text-truncate">{suggestion.label}</div>
									</div>
								</button>
							))}
						</div>
					</section>
				)}

				{(users.length > 0 || (!loadingUsers && canRunUserSearch)) && (
					<section>
						<h2 className="h4 fw-bold mb-3">{t("search.collectors")}</h2>
						<div className="row g-4">
							{users.map((user) => (
								<div
									key={user.id}
									className="col-12 col-sm-6 col-md-4 col-lg-3"
								>
									<UserCard user={user} />
								</div>
							))}

							{!loadingUsers &&
								users.length === 0 &&
								canRunUserSearch &&
								!searchError && (
									<div className="col-12 text-center text-muted py-5">
										<h4 className="mb-0">
											{t("explore.noUsersFound", { query: trimmedQuery })}
										</h4>
									</div>
								)}
						</div>
					</section>
				)}

				{!loadingKits &&
					!loadingUsers &&
					kitSuggestions.length === 0 &&
					(!canRunUserSearch || users.length === 0) &&
					canRunKitSearch &&
					!searchError && (
						<div className="text-center text-muted py-5">
							{t("search.noKitSuggestions")}
						</div>
					)}
			</div>
		</section>
	);

	const renderExploreSection = (section) => {
		const sectionState = exploreSections[section.key] || {
			items: [],
			loading: true,
			error: null,
		};

		return (
			<section className="mb-5" key={section.key} style={{ marginBottom: "4.5rem" }}>
				<div className="text-center mb-4 mt-5">
					<h3 className="h2 fw-bold mb-0">{t(section.labelKey)}</h3>
				</div>

				{sectionState.loading ? (
					<div className="text-center py-4">
						<div className="spinner-border text-dark" role="status"></div>
					</div>
				) : sectionState.error ? (
					<div className="alert alert-danger text-center">
						{sectionState.error}
					</div>
				) : sectionState.items.length === 0 ? (
					<div className="text-center text-muted py-4">
						{t("explore.noKits")}
					</div>
				) : (
					<div className="row g-3 g-md-4">
						{sectionState.items.map((item) => (
							<div
								key={item.id}
								className="col-6 col-md-4 col-lg-3"
							>
								<ExploreKitCard item={item} onOpenKit={handleOpenKit} />
							</div>
						))}
					</div>
				)}
			</section>
		);
	};

	const handleOpenKit = (kitItem, imageIndex = 0) => {
		setSelectedKit(kitItem);
		setSelectedImageIndex(imageIndex);
	};

	const handleCloseKit = () => {
		setSelectedKit(null);
		setSelectedImageIndex(0);
	};

	return (
		<div className="container py-4 py-lg-5">
			<header className="mb-4 text-center">
				<h1 className="display-6 fw-bold mb-2">{t("explore.title")}</h1>
				<p className="text-muted mb-0">
					{t("explore.description")}
				</p>
			</header>

			<div className="mb-4 mx-auto" style={{ maxWidth: "420px" }}>
				<SearchBar value={searchQuery} onChange={setSearchQuery} />
			</div>

			{hasActiveSearch ? (
				renderSearchResults()
			) : (
				<div className="explore-section-stack">
					{EXPLORE_SECTIONS.map((section) => renderExploreSection(section))}
				</div>
			)}

			{selectedKit ? (
				<CommentsModal
					isOpen={Boolean(selectedKit)}
					onClose={handleCloseKit}
					kitId={selectedKit.id}
					currentUser={user}
					item={selectedKit}
					initialImageIndex={selectedImageIndex}
				/>
			) : null}
		</div>
	);
};

export default CollectionPage;
