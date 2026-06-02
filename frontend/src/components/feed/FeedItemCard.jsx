import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Swal from "sweetalert2";

import UserAvatar from "../UserAvatar";
import { formatLocalizedDate } from "../../utils/dateFormat";
import { toggleLike } from "../../services/api";

const getFeedTimestampLabel = (value, t, language) => {
	if (!value) return "";

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) {
		return "";
	}

	const diffMilliseconds = Date.now() - date.getTime();
	const diffMinutes = Math.floor(diffMilliseconds / 60000);

	if (diffMinutes < 1) return t("messages.justNow");
	if (diffMinutes < 60) {
		return t(
			diffMinutes === 1 ? "messages.minAgo_one" : "messages.minAgo_other",
			{ count: diffMinutes },
		);
	}

	const diffHours = Math.floor(diffMinutes / 60);
	if (diffHours < 24) {
		return t(
			diffHours === 1 ? "messages.hourAgo_one" : "messages.hourAgo_other",
			{ count: diffHours },
		);
	}

	return formatLocalizedDate(value, language, {
		hour: "2-digit",
		minute: "2-digit",
	});
};

const FeedItemCard = ({ item, onOpenKit }) => {
	const { t, i18n } = useTranslation();
	const [isLiked, setIsLiked] = useState(Boolean(item.is_liked));
	const [likesCount, setLikesCount] = useState(item.likes_count ?? 0);
	const [likeLoading, setLikeLoading] = useState(false);

	const owner = {
		username: item.owner_username,
		avatar: item.owner_avatar,
	};
	const mainImage = item.images?.[0]?.image || null;
	const seasonText = [item.kit?.season, item.kit?.kit_type]
		.filter(Boolean)
		.join(" ");
	const addedLabel = getFeedTimestampLabel(item.added_at, t, i18n.language);
	const isInCollection = item.in_the_collection !== false;
	const canShowSale = isInCollection && item.for_sale;
	const valueSource =
		Number(item.final_value ?? 0) > 0
			? item.final_value
			: Number(item.manual_value ?? 0) > 0
				? item.manual_value
				: null;
	const valueLabel = valueSource
		? `$${Number(valueSource).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
		: null;
	const playerLabel = [item.player_name, item.player_number]
		.filter(Boolean)
		.join(" ") || "-";

	const metadataItems = [
		{
			icon: "bi bi-calendar3",
			label: item.kit?.season,
			title: t("kitCard.season"),
		},
		{
			icon: "bi bi-palette2",
			label: item.kit?.kit_type,
			title: t("kitCard.kitType"),
		},
		{
			icon: "bi bi-layers",
			label: item.technology_display,
			title: t("kitCard.technology"),
		},
		{
			icon: "bi bi-arrows-angle-expand",
			label: item.size_display || item.size,
			title: t("kitCard.size"),
		},
		{
			icon: "bi bi-gem",
			label: item.condition_display,
			title: t("kitCard.condition"),
		},
		{
			icon: "bi bi-person-fill",
			label: playerLabel,
			title: t("kitCard.player"),
		},
	];

	const handleOpenKit = () => {
		if (!item?.id || !onOpenKit) return;
		onOpenKit(item, 0);
	};

	const handleLikeClick = async (event) => {
		event.stopPropagation();

		if (!item?.id) return;

		if (!localStorage.getItem("access_token")) {
			Swal.fire({
				title: t("comments.authTitle"),
				text: t("comments.authText"),
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
			console.error("Failed to toggle feed like", error);
			setIsLiked(previousLiked);
			setLikesCount(previousCount);
			Swal.fire(t("common.error"), t("feed.likeError"), "error");
		} finally {
			setLikeLoading(false);
		}
	};

	const getSafeLink = (url) => {
		if (!url) return null;
		if (url.match(/^(http|https):\/\//)) {
			return url;
		}
		return null;
	};

	const safeOfferLink = canShowSale ? getSafeLink(item.offer_link) : null;

	return (
		<article className="card border-0 shadow-sm rounded-4 overflow-hidden">
			<div className="card-body p-4 position-relative">
				<div className="d-flex align-items-center gap-3 mb-3">
					<Link
						to={`/profile/${item.owner_username}`}
						className="text-decoration-none text-dark d-flex align-items-center gap-3 min-w-0"
					>
						<UserAvatar user={owner} size={48} />
						<div className="min-w-0">
							<div className="fw-bold text-truncate">@{item.owner_username}</div>
							<div className="small text-muted">
								{t("feed.added", { time: addedLabel })}
							</div>
						</div>
					</Link>
				</div>

				{canShowSale ? (
					<div className="ribbon">{t("feed.forSale")}</div>
				) : null}

				<div
					role="button"
					tabIndex={0}
					className="w-100 text-start"
					onClick={handleOpenKit}
					onKeyDown={(event) => {
						if (event.key === "Enter" || event.key === " ") {
							event.preventDefault();
							handleOpenKit();
						}
					}}
					style={{ cursor: "pointer" }}
				>
					<div className="row g-3 align-items-stretch">
						<div className="col-12 col-sm-4">
							{mainImage ? (
								<div className="position-relative">
									<img
										src={mainImage}
										alt={`${item.kit?.team?.name || "Kit"} ${item.kit?.season || ""}`.trim()}
										className="rounded-4 border"
										style={{
											width: "100%",
											aspectRatio: "3 / 4",
											objectFit: "cover",
											display: "block",
										}}
									/>
									{(item.images?.length || 0) > 1 ? (
										<div
											className="position-absolute bottom-0 end-0 m-2 badge bg-dark bg-opacity-75"
											style={{ fontSize: "0.7rem" }}
										>
											<i className="bi bi-images me-1"></i>
											{item.images.length}
										</div>
									) : null}
								</div>
							) : (
								<div
									className="bg-light border rounded-4 d-flex align-items-center justify-content-center text-muted"
									style={{ width: "100%", aspectRatio: "3 / 4" }}
								>
									<small>{t("history.noPhoto")}</small>
								</div>
							)}
						</div>

						<div className="col-12 col-sm-8 d-flex flex-column">
							<div className="mb-3">
								<div className="d-flex justify-content-between align-items-start gap-2 mb-2">
									<div className="min-w-0">
										<div className="h5 fw-bold mb-1 text-truncate">
											{item.kit?.team?.name || t("history.unknownTeam")}
										</div>
										<div className="text-muted">{seasonText}</div>
									</div>
									<div className="d-flex flex-column align-items-end gap-2 flex-shrink-0">
										{valueLabel ? (
											<span
												className="badge border text-dark bg-white"
												title={t("kitCard.estimatedValue")}
											>
												{valueLabel}
											</span>
										) : null}
									</div>
								</div>

								<div className="row row-cols-1 row-cols-sm-2 g-2 small text-muted">
									{metadataItems.map((entry) => (
										<div key={`${entry.title}-${entry.label}`} className="col">
											<div
												className="d-flex align-items-center rounded-3 bg-light px-2 py-2 h-100"
												title={entry.title}
											>
												<i className={`${entry.icon} me-2`}></i>
												<span className="text-truncate">{entry.label}</span>
											</div>
										</div>
									))}
								</div>
							</div>

							<div className="mt-auto d-flex justify-content-between align-items-center gap-3 flex-wrap">
								<div className="feed-card-stats small text-muted">
									<button
										type="button"
										className="feed-card-stat feed-card-like-button btn btn-link p-0 text-decoration-none text-muted"
										onClick={handleLikeClick}
										disabled={likeLoading}
									>
										<i
											className={`feed-card-stat-icon bi ${
												isLiked ? "bi-heart-fill text-danger" : "bi-heart"
											}`}
										></i>
										<span className="feed-card-stat-count">{likesCount}</span>
									</button>
									<span className="feed-card-stat">
										<i className="feed-card-stat-icon bi bi-chat-left-text"></i>
										<span className="feed-card-stat-count">
											{item.comments_count || 0}
										</span>
									</span>
								</div>

								<div className="d-flex align-items-center gap-2">
									{safeOfferLink ? (
										<a
											href={safeOfferLink}
											target="_blank"
											rel="noopener noreferrer"
											className="btn btn-sm btn-outline-secondary rounded-pill"
											onClick={(event) => event.stopPropagation()}
										>
											{t("feed.viewOffer")}
										</a>
									) : null}
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</article>
	);
};

export default FeedItemCard;
