import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMyWishlist } from "../../services/api";
import SeasonRow from "./SeasonRow";

import "../../styles/history.css";

const normalizeHistoryKitType = (kitType) => {
	const normalized = (kitType || "").trim().toLowerCase().replace(/\s+/g, " ");
	if (["gk", "goalkeeper", "keeper", "goalie"].includes(normalized)) return "goalkeeper";
	if (normalized.startsWith("special")) return "special";
	return normalized;
};

const getCatalogTypeKey = (kitType) => `type:${kitType.id}`;

const prepareKitTypes = (kitTypes) =>
	(Array.isArray(kitTypes) ? kitTypes : []).map((kitType) => ({
		...kitType,
		key: getCatalogTypeKey(kitType),
	}));

const resolveUploadedType = (kit, catalogTypes) => {
	if (kit.kit_type_id) {
		const matchedById = catalogTypes.find((type) => type.id === kit.kit_type_id);
		if (matchedById) return matchedById;
	}

	const displayName = kit.kit_type_display || kit.kit_type;
	const normalizedName = normalizeHistoryKitType(displayName);
	const matchedByName = catalogTypes.find(
		(type) => normalizeHistoryKitType(type.name) === normalizedName,
	);
	if (matchedByName) return matchedByName;

	return {
		id: null,
		slug: kit.kit_type_slug || null,
		name: displayName,
		default_visibility: "none",
		sort_order: 1000,
		key: `legacy:${normalizedName}`,
	};
};

const buildWishlistKey = (teamId, season, kitType) =>
	`${teamId || ""}::${(season || "").trim()}::${normalizeHistoryKitType(kitType)}`;

const KitsGrid = ({ kits, kitTypes, loading, selectedTeamName, selectedTeamId, user }) => {
	const { t } = useTranslation();
	const [showEmpty, setShowEmpty] = useState(true);
	const [wishlistItems, setWishlistItems] = useState([]);
	const catalogTypes = useMemo(() => prepareKitTypes(kitTypes), [kitTypes]);

	const seasons = useMemo(() => {
		const years = [];
		const currentYear = new Date().getFullYear();
		for (let year = currentYear + 1; year >= 1940; year -= 1) {
			years.push(`${year - 1}/${year}`);
		}
		return years;
	}, []);

	const organizedKits = useMemo(() => {
		const map = {};
		(Array.isArray(kits) ? kits : []).forEach((userKit) => {
			const season = userKit.kit.season;
			const type = resolveUploadedType(userKit.kit, catalogTypes);
			const currentEntry = map[season]?.[type.key];
			const currentLikes = currentEntry?.kit?.likes_count || 0;
			const nextLikes = userKit.likes_count || 0;
			const shouldReplace =
				!currentEntry ||
				nextLikes > currentLikes ||
				(nextLikes === currentLikes &&
					new Date(userKit.added_at || 0).getTime() >
						new Date(currentEntry.kit.added_at || 0).getTime());

			if (!map[season]) map[season] = {};
			if (shouldReplace) map[season][type.key] = { kit: userKit, type };
		});
		return map;
	}, [catalogTypes, kits]);

	const wishlistKeySet = useMemo(
		() => new Set(
			(Array.isArray(wishlistItems) ? wishlistItems : []).map((item) =>
				buildWishlistKey(item.team_id, item.season, item.kit_type),
			),
		),
		[wishlistItems],
	);

	const isWishlistedForVariant = (teamId, season, kitType) =>
		wishlistKeySet.has(buildWishlistKey(teamId, season, kitType));

	const refreshWishlist = () => {
		if (!user) {
			setWishlistItems([]);
			return Promise.resolve([]);
		}
		return getMyWishlist()
			.then((items) => {
				const nextItems = Array.isArray(items) ? items : [];
				setWishlistItems(nextItems);
				return nextItems;
			})
			.catch((error) => {
				console.error("Failed to refresh wishlist for history page", error);
				return wishlistItems;
			});
	};

	useEffect(() => {
		if (!user) {
			setWishlistItems([]);
			return undefined;
		}
		let cancelled = false;
		getMyWishlist()
			.then((items) => {
				if (!cancelled) setWishlistItems(Array.isArray(items) ? items : []);
			})
			.catch((error) => {
				console.error("Failed to load wishlist for history page", error);
				if (!cancelled) setWishlistItems([]);
			});
		return () => {
			cancelled = true;
		};
	}, [user]);

	if (loading) return <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>;

	return (
		<div>
			<div className="d-flex justify-content-between align-items-center mb-4">
				<div>{kits.length === 0 && <span className="text-muted">{t("history.noKitsYet")}</span>}</div>
				<div className="form-check form-switch">
					<input
						className="form-check-input"
						type="checkbox"
						id="showEmptySwitch"
						checked={showEmpty}
						onChange={(event) => setShowEmpty(event.target.checked)}
					/>
					<label className="form-check-label small text-muted" htmlFor="showEmptySwitch">
						{t("history.showMissingKits")}
					</label>
				</div>
			</div>

			{seasons.map((season) => (
				<SeasonRow
					key={season}
					season={season}
					organizedKits={organizedKits}
					kitTypes={catalogTypes}
					showEmpty={showEmpty}
					selectedTeamName={selectedTeamName}
					selectedTeamId={selectedTeamId}
					user={user}
					isWishlistedForVariant={isWishlistedForVariant}
					onWishlistToggle={refreshWishlist}
				/>
			))}
		</div>
	);
};

export default KitsGrid;
