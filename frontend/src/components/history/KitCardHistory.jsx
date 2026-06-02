import React from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { toggleLike } from "../../services/api";
import { useState } from "react";
import Swal from "sweetalert2";
import CommentsModal from "../comments/CommentsModal";
import { formatLocalizedDate } from "../../utils/dateFormat";

import "../../styles/profile.css";

const KitCardHistory = ({
	item,
	onDeleteSuccess,
	user,
	compact = false,
	onCardClick,
}) => {
	const { t, i18n } = useTranslation();
	const [viewerState, setViewerState] = useState({
		isOpen: false,
		initialImageIndex: 0,
	});

	// Like state
	const [isLiked, setIsLiked] = useState(() => {
		return !!item.is_liked;
	});
	const [likesCount, setLikesCount] = useState(item.likes_count || 0);
	const [likeLoading, setLikeLoading] = useState(false);

	const openViewer = (initialImageIndex = 0) => {
		setViewerState({
			isOpen: true,
			initialImageIndex,
		});
	};

	const closeViewer = () => {
		setViewerState({
			isOpen: false,
			initialImageIndex: 0,
		});
	};

	const handleMainClick = (initialImageIndex = 0) => {
		if (compact) {
			if (onCardClick) {
				onCardClick(item);
			}
			return;
		}

		openViewer(initialImageIndex);
	};

	const handleLike = async (e) => {
		e.stopPropagation();

		if (!user) {
			Swal.fire({
				title: t("exploreCard.authLikeTitle"),
				text: t("exploreCard.authLikeText"),
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: t("common.ok"),
			}).then((result) => {
				if (result.isConfirmed) {
				}
			});
			return;
		}

		if (likeLoading) return;

		// Remember previous state
		const prevLiked = isLiked;
		const prevCount = likesCount;

		// Optimistic update - if like, increment count, else decrement
		const newLiked = !prevLiked;
		const newCount = newLiked ? prevCount + 1 : prevCount - 1;

		setIsLiked(newLiked);
		setLikesCount(newCount < 0 ? 0 : newCount); // Prevent negative count

		try {
			setLikeLoading(true);
			const data = await toggleLike(item.id);

			// Synchronize state with backend response
			setIsLiked(data.liked);
			setLikesCount(data.likes_count);

			// Debuging
			// console.log("Odpowiedź serwera:", data);
		} catch (error) {
			console.error("Błąd lajkowania:", error);
			// Revert to previous state on error
			setIsLiked(prevLiked);
			setLikesCount(prevCount);
		} finally {
			setLikeLoading(false);
		}
	};

	const getEbayLink = (e) => {
		e.stopPropagation(); // Prevent card click

		// Construct eBay search URL
		// 1. QUERY
		const rawTeamName = item.kit?.team?.name || "";

		// Special cleaning for team names
		const teamName = rawTeamName
			.replace(/\./g, "")
			.replace(/^(FC|CF|AFC|SC|AC)\s+/i, "") // prefix
			.replace(/\s+(FC|CF|AFC|SC|AC)$/i, "") // suffix
			.trim();

		const season = item.kit?.season || "";
		const type = item.kit?.kit_type || "";

		const searchQuery = `${teamName} ${season} ${type} shirt`;
		const encodedQuery = encodeURIComponent(searchQuery);

		// 2. AFFILIATE LINK

		const affiliateBaseUrl = "https://www.ebay.com/sch/i.html?_nkw="; // <--- CHANGE THIS

		const finalUrl = `${affiliateBaseUrl}${encodedQuery}`;

		window.open(finalUrl, "_blank", "noopener,noreferrer"); // noopener for security
	};

	const mainImage = item.images.length > 0 ? item.images[0].image : null;

		return (
		<>
			<div
				className="card h-100 shadow-sm border-0 kit-card-relative d-flex flex-column"
				style={{
					cursor: compact && onCardClick ? "pointer" : "default",
				}}
				onClick={compact && onCardClick ? () => onCardClick(item) : undefined}
				role={compact && onCardClick ? "button" : undefined}
				tabIndex={compact && onCardClick ? 0 : undefined}
			>
				{/* Main photo */}
				<div
					className="p-2"
					style={{ cursor: "pointer" }}
					onClick={() => {
						if (!compact) {
							handleMainClick(0);
						}
					}}
				>
					{mainImage ? (
						<div className="position-relative">
							<img
								src={mainImage}
								alt="Kit"
								className="rounded"
								style={{
									width: "100%",
									aspectRatio: "3 / 4",
									objectFit: "cover",
									display: "block",
								}}
							/>
							{/* Badge showing number of photos if more than 1 */}
							{item.images.length > 1 && (
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
							<small>{t("history.noPhoto")}</small>
						</div>
					)}
				</div>

				{compact ? (
					<div className="card-body d-flex flex-column mt-auto pt-0 p-3">
						<div className="d-flex justify-content-between align-items-start mb-2 gap-2">
							<div className="min-w-0">
								<div className="fw-bold text-dark text-truncate">
									{item.kit?.team?.name || t("history.unknownTeam")}
								</div>
								<div className="small text-muted text-truncate mt-1">
									{[item.kit?.season, item.kit?.kit_type]
										.filter(Boolean)
										.join(" ")}
								</div>
							</div>
							{item.for_sale ? (
								<span className="badge text-bg-warning text-dark flex-shrink-0">
									{t("history.forSale")}
								</span>
							) : null}
						</div>

						<div className="d-flex justify-content-between align-items-center small text-muted mb-2">
							<Link
								to={`/profile/${item.owner_username}`}
								className="text-muted text-decoration-none text-truncate me-2"
								onClick={(e) => e.stopPropagation()}
							>
								<i className="bi bi-person me-1"></i>
								<span className="username">{item.owner_username}</span>
							</Link>
							<div className="d-flex align-items-center gap-3 flex-shrink-0">
								<span>
									<i className="bi bi-heart me-1"></i>
									{likesCount}
								</span>
								<span>
									<i className="bi bi-chat me-1"></i>
									{item.comments_count || 0}
								</span>
							</div>
						</div>
					</div>
				) : (
					<div className="card-body d-flex flex-column mt-auto pt-0 p-3">
					{/* Likes and Added At */}
					<div className="d-flex justify-content-between align-items-center mb-2">
						{/* Likes */}
						<div className="d-flex flex-column align-items-start">
							<div
								className="d-flex align-items-center"
								style={{ gap: "5px" }}
							>
							<button
								className="btn btn-link p-0 text-decoration-none"
								onClick={handleLike}
								style={{
									border: "none",
									outline: "none",
									boxShadow: "none",
								}}
							>
								{isLiked ? (
									<i className="bi bi-heart-fill text-danger fs-5"></i> // Full heart
								) : (
									<i className="bi bi-heart text-muted fs-5"></i> // Empty heart
								)}
							</button>
							<span className="small text-muted">{likesCount}</span>
							</div>
						</div>

						<div className="d-flex align-items-center">
							{/* Owner */}
							<small
								className="me-2"
								style={{ fontSize: "0.75rem" }}
							>
								<Link
									to={`/profile/${item.owner_username}`}
									className="text-muted text-decoration-none"
									onClick={(e) => e.stopPropagation()}
								>
									<i className="bi bi-person me-1"></i>
									<span className="username">
										{item.owner_username}
									</span>
								</Link>
							</small>
							{/* Added At */}
							<small
								className="text-muted d-none d-md-block"
								style={{ fontSize: "0.75rem" }}
							>
								<i className="bi bi-clock me-1"></i>
								<span className="username">
									{formatLocalizedDate(item.added_at, i18n.language)}
								</span>
							</small>
						</div>
					</div>

					{/* Voting */}
					<div>
						<span className="fw-bold"></span>
					</div>

					{/* EBAY Button */}
						<div className="mt-auto">
							<button
								onClick={getEbayLink}
								className="btn w-100 rounded-pill d-flex align-items-center justify-content-center gap-2 ebay-btn"
								title={t("history.findOnEbayTitle")}
							>
								<span className="fw-bold">{t("history.findOnEbay")}</span>
								<i className="bi bi-search"></i>
							</button>
						</div>
					</div>
				)}
			</div>

			{!compact && (
				<CommentsModal
					isOpen={viewerState.isOpen}
					onClose={closeViewer}
					kitId={item.id}
					currentUser={user}
					item={item}
					initialImageIndex={viewerState.initialImageIndex}
				/>
			)}
		</>
	);
};

export default KitCardHistory;
