import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import KitCardHistory from "./KitCardHistory";
import WishlistToggleButton from "../wishlist/WishlistToggleButton";

import "../../styles/history.css";

const uniqueTypes = (types) => {
	const seen = new Set();
	return types.filter((type) => {
		if (seen.has(type.key)) return false;
		seen.add(type.key);
		return true;
	});
};

const SeasonRow = ({
	season,
	organizedKits,
	kitTypes,
	approvedTypes,
	showEmpty,
	selectedTeamName,
	selectedTeamId,
	user,
	isWishlistedForVariant,
	onWishlistToggle,
}) => {
	const { t } = useTranslation();
	const [isExpanded, setIsExpanded] = useState(false);
	const seasonKits = organizedKits[season] || {};
	const actualEntries = Object.values(seasonKits);
	const primaryTypes = kitTypes.filter(
		(type) => type.default_visibility === "primary",
	);
	const expandedTypes = kitTypes.filter(
		(type) => type.default_visibility === "expanded",
	);
	const defaultKeys = new Set(
		[...primaryTypes, ...expandedTypes].map((type) => type.key),
	);
	const approvedExtraTypes = (approvedTypes || []).filter(
		(type) => !defaultKeys.has(type.key),
	);
	const uploadedExtraTypes = actualEntries
		.map((entry) => entry.type)
		.filter((type) => !defaultKeys.has(type.key));

	const visibleTypes = showEmpty
		? uniqueTypes([
			...primaryTypes,
			...(isExpanded ? expandedTypes : []),
			...approvedExtraTypes,
			...uploadedExtraTypes,
		])
		: uniqueTypes(actualEntries.map((entry) => entry.type));

	if (visibleTypes.length === 0) return null;

	return (
		<div className="mb-5">
			<div className="d-flex align-items-center gap-3 mb-3">
				<h3
					className="m-0 fw-bold text-dark"
					style={{ fontFamily: "monospace", letterSpacing: "-1px" }}
				>
					{season}
				</h3>
				<div className="flex-grow-1 border-bottom"></div>
			</div>

			<div className="row g-2 g-md-3 row-cols-2 row-cols-md-2 row-cols-lg-3 row-cols-xl-4 history-season-grid">
				{visibleTypes.map((type) => {
					const bestKit = seasonKits[type.key]?.kit;
					const wishlistKitType = type.name;
					const wishlistTeamId = bestKit?.kit?.team?.id || selectedTeamId;
					const wishlistIsActive = isWishlistedForVariant?.(
						wishlistTeamId,
						season,
						wishlistKitType,
					);

					return (
						<div key={`${season}-${type.key}`} className="col d-flex justify-content-center">
							<div className="d-flex flex-column h-100 w-100 history-slot-shell" style={{ minHeight: "240px" }}>
								<div className="text-center mb-2">
									{bestKit ? (
										<Link
											to={`/history/team/${bestKit.kit.team.slug || bestKit.kit.team.id}/variants?season=${encodeURIComponent(season)}&type=${encodeURIComponent(type.name)}`}
											className="text-decoration-none"
											title={t("history.seeAllUploadsTitle", { season, type: type.name })}
										>
											<span className="badge rounded-pill bg-primary">{type.name}</span>
										</Link>
									) : (
										<span className="badge rounded-pill bg-light text-muted border">{type.name}</span>
									)}
								</div>

								{bestKit ? (
									<div className="position-relative history-card-entry">
										<WishlistToggleButton
											currentUser={user}
											teamId={bestKit.kit?.team?.id}
											season={season}
											kitType={wishlistKitType}
											sourceUserKitId={bestKit.id}
											initialIsWishlisted={wishlistIsActive}
											className="btn btn-light btn-sm rounded-circle shadow-sm history-wishlist-button"
											iconOnly
											onToggle={onWishlistToggle}
										/>
										<KitCardHistory item={bestKit} user={user} />
									</div>
								) : (
									<div className="d-flex flex-grow-1 align-items-center justify-content-center p-3 position-relative history-missing-slot">
										<Link
											to="/add-kit"
											className="add-missing-card"
											title={t("history.addMissingKitTitle", { season, type: type.name })}
											state={{ prefill: { season, type: type.name, team: selectedTeamName } }}
											style={{ minHeight: "100%" }}
										>
											<span className="add-missing-text">{t("history.addMissingKit")}</span>
										</Link>
										<WishlistToggleButton
											currentUser={user}
											teamId={selectedTeamId}
											season={season}
											kitType={wishlistKitType}
											initialIsWishlisted={wishlistIsActive}
											className="btn btn-light btn-sm rounded-circle shadow-sm history-wishlist-button"
											iconOnly
											onToggle={onWishlistToggle}
										/>
									</div>
								)}
							</div>
						</div>
					);
				})}
			</div>

			{showEmpty && expandedTypes.length > 0 && (
				<div className="text-center mt-3">
					<button
						type="button"
						onClick={() => setIsExpanded((current) => !current)}
						className="btn btn-sm btn-outline-secondary rounded-pill px-4"
					>
						{isExpanded ? t("history.hide") : t("history.showMore", { count: expandedTypes.length })}
						<i className={`bi bi-chevron-${isExpanded ? "up" : "down"} ms-1`}></i>
					</button>
				</div>
			)}
		</div>
	);
};

export default SeasonRow;
