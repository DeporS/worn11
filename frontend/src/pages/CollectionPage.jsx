import { useEffect, useState } from "react";

import { getExploreKits, searchUsers } from "../services/api";
import SearchBar from "../components/SearchBar";
import UserCard from "../components/UserCard";
import ExploreKitCard from "../components/explore/ExploreKitCard";

const EXPLORE_SECTIONS = [
	{ key: "trending", label: "Trending", sort: "trending" },
	{ key: "most_liked", label: "Most liked", sort: "most_liked" },
	{ key: "latest", label: "Latest", sort: "latest" },
	{ key: "for_sale", label: "For sale", sort: "for_sale" },
];

const SECTION_LIMIT = 8;

const createSectionState = () =>
	EXPLORE_SECTIONS.reduce((acc, section) => {
		acc[section.key] = {
			items: [],
			loading: true,
			error: null,
		};
		return acc;
	}, {});

const CollectionPage = () => {
	const [users, setUsers] = useState([]);
	const [loadingUsers, setLoadingUsers] = useState(false);
	const [searchError, setSearchError] = useState(null);
	const [searchQuery, setSearchQuery] = useState("");
	const [exploreSections, setExploreSections] = useState(createSectionState);

	const trimmedQuery = searchQuery.trim();
	const hasActiveSearch = trimmedQuery.length > 0;
	const canRunUserSearch = trimmedQuery.length >= 3;
	const isFirstSearchLoad =
		loadingUsers && users.length === 0 && !searchError && canRunUserSearch;

	useEffect(() => {
		if (!hasActiveSearch) {
			setUsers([]);
			setSearchError(null);
			setLoadingUsers(false);
			return;
		}

		if (!canRunUserSearch) {
			setUsers([]);
			setLoadingUsers(false);
			return;
		}

		const delayDebounceFn = window.setTimeout(() => {
			setLoadingUsers(true);
			setSearchError(null);

			searchUsers(trimmedQuery)
				.then((data) => {
					setUsers(Array.isArray(data) ? data : []);
					setLoadingUsers(false);
				})
				.catch((error) => {
					console.error(error);
					setSearchError("Failed to fetch users.");
					setLoadingUsers(false);
				});
		}, 500);

		return () => window.clearTimeout(delayDebounceFn);
	}, [trimmedQuery, canRunUserSearch, hasActiveSearch]);

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
							error: "Could not load this section.",
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
	}, [hasActiveSearch]);

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

			{!canRunUserSearch && (
				<div className="text-center text-muted py-5">
					Type at least 3 characters to search collectors.
				</div>
			)}

			<div
				className="row g-4"
				style={{
					opacity: loadingUsers && users.length > 0 ? 0.5 : 1,
					transition: "opacity 0.2s ease-in-out",
				}}
			>
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
								No users found matching "{trimmedQuery}"
							</h4>
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
					<h3 className="h2 fw-bold mb-0">{section.label}</h3>
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
						No kits available in this section yet.
					</div>
				) : (
					<div className="row g-3 g-md-4">
						{sectionState.items.map((item) => (
							<div
								key={item.id}
								className="col-6 col-md-4 col-lg-3"
							>
								<ExploreKitCard item={item} />
							</div>
						))}
					</div>
				)}
			</section>
		);
	};

	return (
		<div className="container py-4 py-lg-5">
			<header className="mb-4 text-center">
				<h1 className="display-6 fw-bold mb-2">Explore Page</h1>
				<p className="text-muted mb-0">
					Discover trending kits from collectors around Worn11.
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
		</div>
	);
};

export default CollectionPage;
