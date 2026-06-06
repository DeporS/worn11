import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMyWishlist } from "../../services/api";
import SeasonRow from "./SeasonRow";

import "../../styles/history.css";

const normalizeHistoryKitType = (kitType) => {
    const normalized = (kitType || "").trim().toLowerCase();
    if (normalized === "gk" || normalized === "goalkeeper") {
        return "Goalkeeper";
    }
    if (normalized.startsWith("special")) {
        return "Special";
    }
    return kitType;
};

const buildWishlistKey = (teamId, season, kitType) =>
    `${teamId || ""}::${(season || "").trim()}::${normalizeHistoryKitType(kitType)}`;

const KitsGrid = ({
    kits,
    loading,
    selectedTeamName,
    selectedTeamId,
    user,
}) => {
    const { t } = useTranslation();
    const [showEmpty, setShowEmpty] = useState(true);
    const [wishlistItems, setWishlistItems] = useState([]);

    // Generate seasons from current year down to 1940/1941
    const seasons = useMemo(() => {
        const years = [];
        const currentYear = new Date().getFullYear();
        for (let y = currentYear + 1; y >= 1940; y--) {
            years.push(`${y-1}/${y}`);
        }
        return years;
    }, []);

    // Data organization: best kit per season and type
    const organizedKits = useMemo(() => {
        const map = {};
        if (!kits) return map;

        kits.forEach(userKit => {
            const season = userKit.kit.season;
            const type = normalizeHistoryKitType(userKit.kit.kit_type);
            const likes = userKit.likes_count || 0;
            const currentBestKit = map[season]?.[type];
            const currentBestLikes = currentBestKit?.likes_count || 0;
            const shouldReplace =
                !currentBestKit ||
                likes > currentBestLikes ||
                (likes === currentBestLikes &&
                    new Date(userKit.added_at || 0).getTime() >
                        new Date(currentBestKit.added_at || 0).getTime());

            if (!map[season]) map[season] = {};

            // Keep one deterministic representative per canonical type.
            if (shouldReplace) {
                map[season][type] = userKit;
            }
        });
        return map;
    }, [kits]);

    const wishlistKeySet = useMemo(() => {
        return new Set(
            (Array.isArray(wishlistItems) ? wishlistItems : []).map((item) =>
                buildWishlistKey(item.team_id, item.season, item.kit_type),
            ),
        );
    }, [wishlistItems]);

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
                if (cancelled) {
                    return;
                }
                setWishlistItems(Array.isArray(items) ? items : []);
            })
            .catch((error) => {
                console.error("Failed to load wishlist for history page", error);
                if (!cancelled) {
                    setWishlistItems([]);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [user]);


    if (loading) return <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>;

    return (
        <div>
            {/* --- TOP CONTROL BAR --- */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    {kits.length === 0 && (
                        <span className="text-muted">{t("history.noKitsYet")}</span>
                    )}
                </div>
                
                <div className="form-check form-switch">
                    <input 
                        className="form-check-input" 
                        type="checkbox" 
                        id="showEmptySwitch"
                        checked={showEmpty}
                        onChange={(e) => setShowEmpty(e.target.checked)}
                    />
                    <label className="form-check-label small text-muted" htmlFor="showEmptySwitch">
                        {t("history.showMissingKits")}
                    </label>
                </div>
            </div>

            {/* --- SEASONS LIST --- */}
            {seasons.map((season) => (
                <SeasonRow
                    key={season}
                    season={season}
                    organizedKits={organizedKits}
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

