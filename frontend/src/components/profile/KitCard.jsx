import React from "react";
import { useNavigate, Link } from "react-router-dom";
import {
	deleteKitFromCollection,
	toggleLike,
	getKitLikers,
	startConversation,
} from "../../services/api";
import { useState } from "react";
import Swal from "sweetalert2";

import UserListModal from "./UserListModal";
import { formatLikedByText } from "../utils/likeText";
import CommentsModal from "../comments/CommentsModal";
import { copyKitShareUrl } from "../utils/kitShare";

import "../../styles/profile.css";

const KitCard = ({ item, onDeleteSuccess, user }) => {
	const navigate = useNavigate();
	const [isDeleting, setIsDeleting] = useState(false);
	const [viewerState, setViewerState] = useState({
		isOpen: false,
		initialImageIndex: 0,
	});

	const mainImage = item.images.length > 0 ? item.images[0].image : null;

	// Like state
	const [isLiked, setIsLiked] = useState(() => {
		return !!item.is_liked;
	});
	const [likesCount, setLikesCount] = useState(item.likes_count || 0);
	const [likeLoading, setLikeLoading] = useState(false);

	// Modal states for likers list
	const [modalType, setModalType] = useState(null); // 'likers' or null
	const [modalUsers, setModalUsers] = useState([]); // Users list for modal
	const [modalLoading, setModalLoading] = useState(false);
	const likedByText = formatLikedByText({
		count: likesCount,
		isLiked,
	});

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

	// Function to open likers modal and load data
	const openLikersModal = async () => {
		setModalType("likers");
		setModalLoading(true);
		setModalUsers([]); // Clear previous data

		try {
			const data = await getKitLikers(item.id);
			setModalUsers(data);
		} catch (err) {
			console.error("Failed to load list", err);
		} finally {
			setModalLoading(false);
		}
	};

	const closeLikersModal = () => {
		setModalType(null);
	};

	const handleLike = async (e) => {
		e.stopPropagation();

		if (!user) {
			Swal.fire({
				title: "You need to log in!",
				text: "Only logged-in users can like kits.",
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: "Ok",
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

	const handleDeleteClick = async () => {
		Swal.fire({
			title: "Are you sure?",
			text: "You won't be able to revert this!",
			icon: "warning",
			showCancelButton: true,
			confirmButtonColor: "#dc3545",
			cancelButtonColor: "#6c757d",
			confirmButtonText: "Yes, delete it",
		}).then(async (result) => {
			if (result.isConfirmed) {
				try {
					setIsDeleting(true);
					await deleteKitFromCollection(item.id);

					Swal.fire(
						"Deleted!",
						"Your kit has been removed.",
						"success",
					);

					if (onDeleteSuccess) onDeleteSuccess(item.id);
				} catch (error) {
					setIsDeleting(false);
					Swal.fire("Error!", "Something went wrong.", "error");
				}
			}
		});
	};

	const handleEditClick = () => {
		navigate(`/edit-kit/${item.id}`); // navigate to /edit-kit/15
	};

	const handleShareClick = async (e) => {
		e.stopPropagation();
		await copyKitShareUrl(item);
	};

	const handleContactOwnerClick = async (e) => {
		e.stopPropagation();

		if (!user) {
			Swal.fire({
				title: "You need to log in!",
				text: "Only logged-in users can send messages.",
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: "Ok",
			});
			return;
		}

		try {
			const conversation = await startConversation({ kit_id: item.id });
			navigate(`/messages/${conversation.id}`);
		} catch (error) {
			console.error("Failed to start conversation", error);
			const message =
				error?.response?.data?.non_field_errors?.[0] ||
				error?.response?.data?.kit_id?.[0] ||
				"Could not start a conversation.";
			Swal.fire("Error", message, "error");
		}
	};

	// Helper function to sanitize link (Cybsersecurity)
	const getSafeLink = (url) => {
		if (!url) return null;

		// Basic check for http or https
		if (url.match(/^(http|https):\/\//)) {
			return url;
		}

		return null;
	};

	return (
		<>
			<div className="card h-100 shadow-sm border-0 kit-card-relative">
				{item.for_sale && item.in_the_collection && (
					<div className="ribbon">For Sale</div>
				)}

				{/* ========================================== */}
				{/* PC VERSION - Click to view more images */}
				{/* VISIBLE ON LARGE SCREENS (md and above) */}
				{/* ========================================== */}
				<div
					className="p-2 d-none d-md-block"
					style={{ cursor: "pointer" }}
					onClick={() => {
						openViewer(0);
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
							{/* Stary badge z samą liczbą */}
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
							<small>No photo</small>
						</div>
					)}
				</div>

				{/* ========================================== */}
				{/* MOBILE VERSION - swipe through images */}
				{/* Visible only on small screens (below md) */}
				{/* ========================================== */}
				<div
					className="p-2 d-flex d-md-none kit-swipe-gallery"
					style={{
						overflowX: "auto",
						scrollSnapType: "x mandatory",
						WebkitOverflowScrolling: "touch",
					}}
				>
					{item.images.length > 0 ? (
						item.images.map((img, index) => (
							<div
								key={img.id}
								className="position-relative"
								onClick={() => openViewer(index)}
								style={{
									flex: "0 0 100%",
									scrollSnapAlign: "center",
									cursor: "pointer",
								}}
							>
								<img
									src={img.image}
									alt={`Kit ${index + 1}`}
									className="rounded"
									style={{
										width: "100%",
										aspectRatio: "3 / 4",
										objectFit: "cover",
										display: "block",
									}}
								/>
								{/* Nowy badge z numerem aktualnego zdjęcia */}
								{item.images.length > 1 && (
									<div
										className="position-absolute bottom-0 end-0 m-2 badge bg-dark bg-opacity-75"
										style={{ fontSize: "0.7rem" }}
									>
										<i className="bi bi-images me-1"></i>
										{index + 1} / {item.images.length}
									</div>
								)}
							</div>
						))
					) : (
						<div
							className="bg-light d-flex align-items-center justify-content-center rounded text-muted"
							style={{
								width: "100%",
								aspectRatio: "3 / 4",
								flex: "0 0 100%",
							}}
						>
							<small>No photo</small>
						</div>
					)}
				</div>

				<div className="card-body">
					{/* Team Name && Estimated Value */}
					<div className="d-flex justify-content-between align-items-center mb-3 mt-0">
						<div
							className="d-flex align-items-center"
							style={{ gap: "8px" }}
						>
							{item.kit.team.logo && (
								<img
									src={item.kit.team.logo}
									alt="Team Logo"
									style={{ height: "20px", marginTop: "2px" }}
								/>
							)}
							<h5 className="card-title mb-0" title="Team">
								{item.kit.team.name}
							</h5>
						</div>
						<span
							className={`badge-outline ${!item.in_the_collection ? "text-muted border-secondary" : ""}`}
							title={
								item.in_the_collection
									? "Estimated Value"
									: "No longer in collection"
							}
						>
							{item.in_the_collection
								? `$${Number(item.final_value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
								: "SOLD"}
						</span>
					</div>

					{/* Kit Details */}
					<div className="kit-info p-2">
						{/* Season & Kit Type */}
						<div className="justify-content-between text-muted small">
							<span
								title="Season"
								className="d-flex align-items-center"
							>
								<i className="bi bi-calendar3 me-2"></i>
								{item.kit.season}
							</span>
							<span
								title="Kit Type"
								className="d-flex align-items-center"
							>
								<i className="bi bi-palette2 me-2"></i>
								<span className="">{item.kit.kit_type}</span>
							</span>
						</div>

						{/* Technology & Size */}
						<div className="justify-content-between text-muted small">
							<span
								title="Technology"
								className="d-flex align-items-center"
							>
								<i className="bi-layers me-2"></i>
								{item.technology_display}
							</span>
							<span
								title="Size"
								className="d-flex align-items-center"
							>
								<i className="bi bi-arrows-angle-expand me-2"></i>
								<span className="">{item.size}</span>
							</span>
						</div>

						{/* Condition & Player */}
						<div className="justify-content-between text-muted small">
							<span
								title="Condition"
								className="d-flex align-items-center"
							>
								<i className="bi bi-gem me-2"></i>
								{item.condition_display}
							</span>
							<span
								title="Player"
								className="d-flex align-items-center"
							>
								{item.player_name || item.player_number ? (
									<>
										<i className="bi bi-person-fill me-2"></i>
										<span className="">
											{item.player_name}{" "}
											{item.player_number}
										</span>
									</>
								) : (
									<>
										<i className="bi bi-person-fill me-2"></i>
										<span className="opacity-50">-</span>
									</>
								)}
							</span>
						</div>
					</div>

					{/* Contact Owner & View Offer + Edit/Delete Buttons */}
					<div className="d-flex justify-content-between mt-1 align-items-center">
						{/*Contact Owner & View Offer Links*/}
						<div className="d-flex flex-column">
							{item.is_owner ? (
								<a className="minimal-not-for-sale-link">
									<span>You are the owner</span>
									<span className="arrow-icon">ツ</span>
								</a>
							) : (
								<button
									type="button"
									className="minimal-offer-link"
									onClick={handleContactOwnerClick}
								>
									<span>Contact Owner</span>
									<span className="arrow-icon">✉︎</span>
								</button>
							)}

							{/* View Offer Link */}
							{item.for_sale ? (
								item.offer_link &&
								getSafeLink(item.offer_link) ? (
									<a
										href={getSafeLink(item.offer_link)}
										target="_blank"
										rel="noopener noreferrer"
										className="minimal-offer-link"
									>
										<span>View offer</span>
										<span className="arrow-icon">➚</span>
									</a>
								) : (
									<a className="minimal-not-for-sale-link">
										<span>No link provided</span>
										<span className="arrow-icon">⨂</span>
									</a>
								)
							) : (
								<a className="minimal-not-for-sale-link">
									<span>Not for sale</span>
									<span className="arrow-icon">⨂</span>
								</a>
							)}
						</div>

						{/* Edit and Delete Buttons */}
						<div className="gap-2 d-flex">
							{item.is_owner && (
								<>
									{/* Edit Button */}
									<button
										className="btn btn-sm edit-button"
										onClick={handleEditClick}
										title="Edit"
									>
										✏
									</button>

									{/* Delete Button */}
									<button
										className="btn btn-sm edit-button"
										onClick={handleDeleteClick}
										disabled={isDeleting} // Block button while deleting
										title="Delete"
									>
										{isDeleting ? (
											<span
												className="spinner-border spinner-border-sm"
												role="status"
												aria-hidden="true"
											></span>
										) : (
											<>🗑️</>
										)}
									</button>
								</>
							)}

							{/* Share Button */}
							<button
								className="btn btn-sm edit-button"
								onClick={handleShareClick}
								title="Share"
							>
								🔗
							</button>
						</div>
					</div>

					{/* Likes and Added At */}
					<div className="d-flex justify-content-between mt-1 align-items-center">
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
							<button
								type="button"
								className="p-0 bg-transparent border-0 small text-muted text-start"
								title="See who liked this"
								onClick={(e) => {
									e.stopPropagation();
									openLikersModal();
								}}
								style={{
									cursor: "pointer",
									lineHeight: 1.2,
								}}
							>
								{likedByText}
							</button>
							</div>
						</div>

						<div>
							{/* Owner */}
							<small
								className="me-3"
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
								className="text-muted"
								style={{ fontSize: "0.75rem" }}
							>
								<i className="bi bi-clock me-1"></i>
								<span className="username">
									{new Date(item.added_at).toLocaleDateString(
										"en-GB",
										{
											day: "numeric",
											month: "short",
											year: "numeric",
										},
									)}
								</span>
							</small>
						</div>
					</div>
				</div>
			</div>

			{/* Likers Modal */}
			<UserListModal
				isOpen={modalType !== null}
				onClose={closeLikersModal}
				title={"Liked this kit"}
				users={modalUsers}
				loading={modalLoading}
			/>
			<CommentsModal
				isOpen={viewerState.isOpen}
				onClose={closeViewer}
				kitId={item.id}
				currentUser={user}
				item={item}
				initialImageIndex={viewerState.initialImageIndex}
			/>
		</>
	);
};

export default KitCard;
