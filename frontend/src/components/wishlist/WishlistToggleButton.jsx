import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import { toggleWishlistItem } from "../../services/api";

const WishlistToggleButton = ({
	currentUser,
	teamId,
	season,
	kitType,
	sourceUserKitId = null,
	initialIsWishlisted = false,
	className = "",
	onToggle,
	iconOnly = false,
}) => {
	const { t } = useTranslation();
	const [isWishlisted, setIsWishlisted] = useState(Boolean(initialIsWishlisted));
	const [loading, setLoading] = useState(false);
	const buttonLabel = isWishlisted ? t("wishlist.remove") : t("wishlist.add");

	useEffect(() => {
		setIsWishlisted(Boolean(initialIsWishlisted));
	}, [initialIsWishlisted, teamId, season, kitType]);

	if (!teamId || !season || !kitType) {
		return null;
	}

	const handleClick = async (event) => {
		event?.stopPropagation?.();
		event?.preventDefault?.();

		if (!currentUser) {
			Swal.fire({
				title: t("wishlist.authTitle"),
				text: t("wishlist.authText"),
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: t("common.ok"),
			});
			return;
		}

		if (loading) {
			return;
		}

		try {
			setLoading(true);
			const data = await toggleWishlistItem({
				teamId,
				season,
				kitType,
				sourceUserKitId,
			});
			setIsWishlisted(Boolean(data?.is_wishlisted));
			onToggle?.(data);
		} catch (error) {
			const limit = error?.response?.data?.limit;
			if (error?.response?.data?.code === "wishlist_limit_reached") {
				Swal.fire({
					title: t("wishlist.limitReachedTitle"),
					text: t("wishlist.limitReachedBody", { limit }),
					icon: "info",
					confirmButtonColor: "#3085d6",
					confirmButtonText: t("common.ok"),
				});
				return;
			}

			Swal.fire(t("common.error"), t("wishlist.loadError"), "error");
		} finally {
			setLoading(false);
		}
	};

	return (
		<button
			type="button"
			className={className}
			onClick={handleClick}
			disabled={loading}
			aria-pressed={isWishlisted}
			aria-label={buttonLabel}
			title={buttonLabel}
		>
			<i
				className={`bi ${isWishlisted ? "bi-bookmark-check-fill" : "bi-bookmark-plus"} ${iconOnly ? "" : "me-1"}`}
				aria-hidden="true"
			></i>
			{iconOnly ? (
				<span className="visually-hidden">{buttonLabel}</span>
			) : (
				buttonLabel
			)}
		</button>
	);
};

export default WishlistToggleButton;
