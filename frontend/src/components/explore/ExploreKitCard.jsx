import { useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import { toggleLike } from "../../services/api";

const ExploreKitCard = ({ item, onOpenKit }) => {
	const { t } = useTranslation();
	const [isLiked, setIsLiked] = useState(Boolean(item.is_liked));
	const [likesCount, setLikesCount] = useState(item.likes_count ?? 0);
	const [likeLoading, setLikeLoading] = useState(false);

	const handleClick = () => {
		if (!item?.id || !onOpenKit) return;
		onOpenKit(item, 0);
	};

	const handleLikeClick = async (event) => {
		event.stopPropagation();

		if (!item?.id) return;

		if (!localStorage.getItem("access_token")) {
			Swal.fire({
				title: t("exploreCard.authLikeTitle"),
				text: t("exploreCard.authLikeText"),
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: t("common.ok"),
			});
			return;
		}

		if (likeLoading) return;

		const previousLiked = isLiked;
		const previousCount = likesCount;
		const nextLiked = !previousLiked;
		const nextCount = Math.max(previousCount + (nextLiked ? 1 : -1), 0);

		setIsLiked(nextLiked);
		setLikesCount(nextCount);

		try {
			setLikeLoading(true);
			const data = await toggleLike(item.id);
			setIsLiked(data.liked);
			setLikesCount(data.likes_count);
		} catch (error) {
			console.error("Failed to toggle like", error);
			setIsLiked(previousLiked);
			setLikesCount(previousCount);
			Swal.fire(t("common.error"), t("exploreCard.likeError"), "error");
		} finally {
			setLikeLoading(false);
		}
	};

	const mainImage = item.images?.[0]?.image || null;
	const seasonText = [item.kit?.season, item.kit?.kit_type]
		.filter(Boolean)
		.join(" ");

	return (
		<div
			className="card h-100 shadow-sm border-0 kit-card-relative text-start w-100 p-0"
			onClick={handleClick}
			role="button"
			tabIndex={0}
			onKeyDown={(event) => {
				if (event.key === "Enter" || event.key === " ") {
					event.preventDefault();
					handleClick();
				}
			}}
			style={{ cursor: item?.owner_username ? "pointer" : "default" }}
		>
			{item.for_sale && item.in_the_collection && (
				<div className="ribbon">{t("exploreCard.forSale")}</div>
			)}

			<div className="p-2">
				{mainImage ? (
					<div className="position-relative">
						<img
							src={mainImage}
							alt={`${item.kit?.team?.name || "Kit"} ${item.kit?.season || ""}`.trim()}
							className="rounded"
							style={{
								width: "100%",
								aspectRatio: "3 / 4",
								objectFit: "cover",
								display: "block",
							}}
						/>
						{(item.images?.length || 0) > 1 && (
							<div
								className="position-absolute bottom-0 end-0 m-2 badge bg-dark bg-opacity-75"
								style={{ fontSize: "0.7rem" }}
							>
								<i className="bi bi-images me-1"></i>
								{item.images.length}
							</div>
						)}
					</div>
				) : (
					<div
						className="bg-light d-flex align-items-center justify-content-center rounded text-muted"
						style={{ width: "100%", aspectRatio: "3 / 4" }}
					>
						<small>{t("exploreCard.noPhoto")}</small>
					</div>
				)}
			</div>

			<div className="card-body d-flex flex-column pt-0 p-3">
				<div className="d-flex justify-content-between align-items-start gap-2 mb-2">
					<div className="min-w-0">
						<div className="fw-bold text-dark text-truncate">
							{item.kit?.team?.name || t("exploreCard.unknownTeam")}
						</div>
						<div className="small text-muted text-truncate mt-1">
							{seasonText}
						</div>
					</div>
				</div>

				<div className="d-flex justify-content-between align-items-center small text-muted mt-auto">
					<span className="text-truncate me-2">
						<i className="bi bi-person me-1"></i>
						<span className="username">{item.owner_username || t("exploreCard.unknownOwner")}</span>
					</span>
					<button
						type="button"
						className="btn btn-link p-0 text-decoration-none text-muted flex-shrink-0 d-inline-flex align-items-center"
						onClick={handleLikeClick}
						style={{
							border: "none",
							boxShadow: "none",
						}}
					>
						{isLiked ? (
							<i
								className="bi bi-heart-fill text-danger me-1"
								style={{ fontSize: "1.15rem" }}
							></i>
						) : (
							<i
								className="bi bi-heart me-1"
								style={{ fontSize: "1.15rem" }}
							></i>
						)}
						<span>{likesCount}</span>
					</button>
				</div>
			</div>
		</div>
	);
};

export default ExploreKitCard;
