import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Swal from "sweetalert2";

import { removeWishlistItem } from "../../services/api";

const FREE_WISHLIST_LIMIT = 10;
const SORT_NEWEST = "newest";
const SORT_OLDEST = "oldest";
const SORT_SEASON_NEWEST = "season_newest";
const SORT_SEASON_OLDEST = "season_oldest";
const SORT_TEAM_AZ = "team_az";
const SORT_TEAM_ZA = "team_za";

const compareStrings = (left, right, direction = "asc") => {
	const normalizedLeft = (left || "").trim();
	const normalizedRight = (right || "").trim();
	const result = normalizedLeft.localeCompare(normalizedRight, undefined, {
		sensitivity: "base",
		numeric: true,
	});
	return direction === "desc" ? result * -1 : result;
};

const compareKitType = (left, right) => compareStrings(left, right, "asc");

const parseSeasonPart = (part) => {
	if (!part) {
		return null;
	}

	const trimmedPart = String(part).trim();
	if (!/^\d{2,4}$/.test(trimmedPart)) {
		return null;
	}

	const numericPart = Number.parseInt(trimmedPart, 10);
	if (Number.isNaN(numericPart)) {
		return null;
	}

	if (trimmedPart.length === 4) {
		return numericPart;
	}

	return numericPart >= 50 ? 1900 + numericPart : 2000 + numericPart;
};

const parseSeasonYears = (season) => {
	if (!season) {
		return null;
	}

	const normalizedSeason = String(season).trim();
	const seasonParts = normalizedSeason.match(/\d{2,4}/g);
	if (!seasonParts || seasonParts.length === 0) {
		return null;
	}

	const startYear = parseSeasonPart(seasonParts[0]);
	if (!startYear) {
		return null;
	}

	const endYear = parseSeasonPart(seasonParts[1] || seasonParts[0]);
	return {
		startYear,
		endYear: endYear || startYear,
	};
};

const compareCreatedAt = (left, right, direction = "desc") => {
	const leftTimestamp = left ? Date.parse(left) : Number.NaN;
	const rightTimestamp = right ? Date.parse(right) : Number.NaN;
	const normalizedLeft = Number.isNaN(leftTimestamp) ? 0 : leftTimestamp;
	const normalizedRight = Number.isNaN(rightTimestamp) ? 0 : rightTimestamp;
	const result = normalizedLeft - normalizedRight;
	return direction === "desc" ? result * -1 : result;
};

const compareBySeason = (leftItem, rightItem, direction = "desc") => {
	const leftSeason = parseSeasonYears(leftItem.season);
	const rightSeason = parseSeasonYears(rightItem.season);

	if (!leftSeason && !rightSeason) {
		return 0;
	}

	if (!leftSeason) {
		return 1;
	}

	if (!rightSeason) {
		return -1;
	}

	const startDiff = leftSeason.startYear - rightSeason.startYear;
	if (startDiff !== 0) {
		return direction === "desc" ? startDiff * -1 : startDiff;
	}

	const endDiff = leftSeason.endYear - rightSeason.endYear;
	if (endDiff !== 0) {
		return direction === "desc" ? endDiff * -1 : endDiff;
	}

	return 0;
};

const WishlistSection = ({
	items,
	isOwner,
	isPro,
	heading,
	onRemoveSuccess,
}) => {
	const { t } = useTranslation();
	const [removingId, setRemovingId] = useState(null);
	const [sortMode, setSortMode] = useState(SORT_NEWEST);

	const sortedItems = useMemo(() => {
		const nextItems = [...items];

		nextItems.sort((leftItem, rightItem) => {
			if (sortMode === SORT_OLDEST) {
				const createdAtComparison = compareCreatedAt(
					leftItem.created_at,
					rightItem.created_at,
					"asc",
				);
				if (createdAtComparison !== 0) {
					return createdAtComparison;
				}
			} else if (sortMode === SORT_SEASON_NEWEST) {
				const seasonComparison = compareBySeason(leftItem, rightItem, "desc");
				if (seasonComparison !== 0) {
					return seasonComparison;
				}
				const teamComparison = compareStrings(
					leftItem.team_name,
					rightItem.team_name,
					"asc",
				);
				if (teamComparison !== 0) {
					return teamComparison;
				}
				return compareKitType(leftItem.kit_type, rightItem.kit_type);
			} else if (sortMode === SORT_SEASON_OLDEST) {
				const seasonComparison = compareBySeason(leftItem, rightItem, "asc");
				if (seasonComparison !== 0) {
					return seasonComparison;
				}
				const teamComparison = compareStrings(
					leftItem.team_name,
					rightItem.team_name,
					"asc",
				);
				if (teamComparison !== 0) {
					return teamComparison;
				}
				return compareKitType(leftItem.kit_type, rightItem.kit_type);
			} else if (sortMode === SORT_TEAM_AZ) {
				const teamComparison = compareStrings(
					leftItem.team_name,
					rightItem.team_name,
					"asc",
				);
				if (teamComparison !== 0) {
					return teamComparison;
				}
				const seasonComparison = compareBySeason(leftItem, rightItem, "desc");
				if (seasonComparison !== 0) {
					return seasonComparison;
				}
				return compareKitType(leftItem.kit_type, rightItem.kit_type);
			} else if (sortMode === SORT_TEAM_ZA) {
				const teamComparison = compareStrings(
					leftItem.team_name,
					rightItem.team_name,
					"desc",
				);
				if (teamComparison !== 0) {
					return teamComparison;
				}
				const seasonComparison = compareBySeason(leftItem, rightItem, "desc");
				if (seasonComparison !== 0) {
					return seasonComparison;
				}
				return compareKitType(leftItem.kit_type, rightItem.kit_type);
			}

			const createdAtComparison = compareCreatedAt(
				leftItem.created_at,
				rightItem.created_at,
				"desc",
			);
			if (createdAtComparison !== 0) {
				return createdAtComparison;
			}

			const teamComparison = compareStrings(
				leftItem.team_name,
				rightItem.team_name,
				"asc",
			);
			if (teamComparison !== 0) {
				return teamComparison;
			}

			const seasonComparison = compareBySeason(leftItem, rightItem, "desc");
			if (seasonComparison !== 0) {
				return seasonComparison;
			}

			return compareKitType(leftItem.kit_type, rightItem.kit_type);
		});

		return nextItems;
	}, [items, sortMode]);

	const handleRemove = async (itemId) => {
		if (removingId) {
			return;
		}

		try {
			setRemovingId(itemId);
			await removeWishlistItem(itemId);
			onRemoveSuccess?.(itemId);
		} catch (error) {
			console.error("Failed to remove wishlist item", error);
			Swal.fire(t("common.error"), t("wishlist.loadError"), "error");
		} finally {
			setRemovingId(null);
		}
	};

	return (
		<section className="mt-3">
			<div className="wishlist-page-header-row">
				<div className="wishlist-title-group">
					<h1 className="h3 fw-bold mb-0 wishlist-page-title">
						{heading || t("wishlist.title")}
					</h1>
					{isOwner ? (
						<div className="wishlist-limit-badge">
							{isPro
								? t("wishlist.proUnlimited")
								: t("wishlist.freeLimit", {
										count: items.length,
										limit: FREE_WISHLIST_LIMIT,
									})}
						</div>
					) : null}
				</div>

				{items.length > 0 ? (
					<div className="wishlist-sort-control">
						<label
							htmlFor="wishlist-sort-select"
							className="wishlist-sort-label"
						>
							{t("wishlist.sortBy")}
						</label>
						<select
							id="wishlist-sort-select"
							className="form-select wishlist-sort-select"
							value={sortMode}
							onChange={(event) => setSortMode(event.target.value)}
						>
							<option value={SORT_NEWEST}>{t("wishlist.sortNewest")}</option>
							<option value={SORT_OLDEST}>{t("wishlist.sortOldest")}</option>
							<option value={SORT_SEASON_NEWEST}>
								{t("wishlist.sortSeasonNewest")}
							</option>
							<option value={SORT_SEASON_OLDEST}>
								{t("wishlist.sortSeasonOldest")}
							</option>
							<option value={SORT_TEAM_AZ}>{t("wishlist.sortTeamAZ")}</option>
							<option value={SORT_TEAM_ZA}>{t("wishlist.sortTeamZA")}</option>
						</select>
					</div>
				) : null}
			</div>

			{items.length === 0 ? (
				<div className="wishlist-empty-state">
					{isOwner
						? t("wishlist.emptyOwner")
						: t("wishlist.emptyPublic")}
				</div>
			) : (
				<div className="row g-4">
					{sortedItems.map((item) => (
						<div key={item.id} className="col-12 col-sm-6 col-lg-4 col-xl-3">
							<div className="card h-100 border-0 shadow-sm wishlist-card">
								<div className="wishlist-card-preview">
									{item.preview_image ? (
										<img
											src={item.preview_image}
											alt={`${item.team_name} ${item.season} ${item.kit_type}`}
											className="wishlist-card-image"
										/>
									) : (
										<div className="wishlist-card-placeholder">
											<i className="bi bi-search"></i>
										</div>
									)}
								</div>
								<div className="card-body d-flex flex-column wishlist-card-body">
									<div className="wishlist-card-meta mb-3">
										<div className="fw-bold text-dark">{item.team_name}</div>
										<div className="text-muted small">
											{item.season} {item.kit_type}
										</div>
									</div>
									<div className="wishlist-card-actions mt-auto d-flex align-items-center justify-content-center gap-2 flex-wrap">
										<Link
											to={item.url}
											className="btn btn-sm btn-outline-secondary rounded-pill"
										>
											{t("wishlist.viewInMuseum")}
										</Link>
										{isOwner ? (
											<button
												type="button"
												className="btn btn-sm btn-outline-danger rounded-pill"
												onClick={() => handleRemove(item.id)}
												disabled={removingId === item.id}
											>
												{t("wishlist.remove")}
											</button>
										) : null}
									</div>
								</div>
							</div>
						</div>
					))}
				</div>
			)}
		</section>
	);
};

export default WishlistSection;
