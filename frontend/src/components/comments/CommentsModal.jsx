import { useEffect, useMemo, useState } from "react";
import Swal from "sweetalert2";

import {
	addKitComment,
	deleteComment,
	getKitComments,
	replyToComment,
	toggleCommentLike,
} from "../../services/api";
import CommentItem from "./CommentItem";
import ReportKitModal from "../reports/ReportKitModal";
import { copyKitShareUrl } from "../utils/kitShare";

const countComments = (items) =>
	items.reduce(
		(total, comment) => total + 1 + (comment.replies?.length || 0),
		0,
	);

const updateCommentTree = (items, commentId, updater) =>
	items.map((comment) => {
		if (comment.id === commentId) {
			return updater(comment);
		}

		if (comment.replies?.length) {
			return {
				...comment,
				replies: comment.replies.map((reply) =>
					reply.id === commentId ? updater(reply) : reply,
				),
			};
		}

		return comment;
	});

const findCommentById = (items, commentId) => {
	for (const comment of items) {
		if (comment.id === commentId) {
			return comment;
		}

		const reply = comment.replies?.find((item) => item.id === commentId);
		if (reply) {
			return reply;
		}
	}

	return null;
};

const appendReplyToThread = (items, reply) =>
	items.map((comment) =>
		comment.id === reply.parent_id
			? {
					...comment,
					replies: [...(comment.replies || []), reply],
					reply_count: (comment.reply_count || 0) + 1,
				}
			: comment,
	);

const removeCommentFromTree = (items, commentId) =>
	items
		.filter((comment) => comment.id !== commentId)
		.map((comment) => {
			if (!comment.replies?.length) {
				return comment;
			}

			const nextReplies = comment.replies.filter(
				(reply) => reply.id !== commentId,
			);

			if (nextReplies.length === comment.replies.length) {
				return comment;
			}

			return {
				...comment,
				replies: nextReplies,
				reply_count: Math.max((comment.reply_count || 0) - 1, 0),
			};
		});

const CommentsModal = ({
	isOpen,
	onClose,
	kitId,
	currentUser,
	item,
	initialImageIndex = 0,
}) => {
	const [comments, setComments] = useState([]);
	const [loading, setLoading] = useState(false);
	const [draft, setDraft] = useState("");
	const [activeReplyTarget, setActiveReplyTarget] = useState(null);
	const [replyDraft, setReplyDraft] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [replySubmitting, setReplySubmitting] = useState(false);
	const [currentImageIndex, setCurrentImageIndex] = useState(0);
	const [reportModalOpen, setReportModalOpen] = useState(false);

	const totalComments = useMemo(() => countComments(comments), [comments]);
	const images = item?.images || [];
	const activeImage = images[currentImageIndex] || null;
	const kitTitle = formatKitTitle(item);
	const ownerLabel = formatOwnerLabel(item);
	const offerUrl = getSafeUrl(item?.offer_link);

	useEffect(() => {
		if (!isOpen) return;

		const maxIndex = Math.max(images.length - 1, 0);
		const safeIndex = Math.min(Math.max(initialImageIndex, 0), maxIndex);
		setCurrentImageIndex(safeIndex);
	}, [images.length, initialImageIndex, isOpen]);

	useEffect(() => {
		if (!isOpen) {
			document.body.style.overflow = "unset";
			return;
		}

		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = "unset";
		};
	}, [isOpen]);

	useEffect(() => {
		if (!isOpen || !kitId) return;

		const loadComments = async () => {
			setLoading(true);
			try {
				const data = await getKitComments(kitId);
				setComments(Array.isArray(data) ? data : []);
			} catch (error) {
				console.error("Failed to load comments", error);
				Swal.fire("Error", "Could not load comments.", "error");
			} finally {
				setLoading(false);
			}
		};

		loadComments();
	}, [isOpen, kitId]);

	useEffect(() => {
		if (!isOpen) return;
		if (reportModalOpen) return;

		const handleKeyDown = (e) => {
			if (e.key === "Escape") {
				onClose();
			}

			if (e.key === "ArrowRight" && currentImageIndex < images.length - 1) {
				setCurrentImageIndex((prev) => prev + 1);
			}

			if (e.key === "ArrowLeft" && currentImageIndex > 0) {
				setCurrentImageIndex((prev) => prev - 1);
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [currentImageIndex, images.length, isOpen, onClose, reportModalOpen]);

	if (!isOpen) return null;

	const ensureAuthenticated = () => {
		if (currentUser) return true;

		Swal.fire({
			title: "You need to log in!",
			text: "Only logged-in users can comment and like comments.",
			icon: "info",
			confirmButtonColor: "#3085d6",
			confirmButtonText: "Ok",
		});
		return false;
	};

	const handleAddComment = async () => {
		const body = draft.trim();
		if (!body) return;
		if (!ensureAuthenticated()) return;

		try {
			setSubmitting(true);
			const created = await addKitComment(kitId, body);
			setComments((prev) => [created, ...prev]);
			setDraft("");
		} catch (error) {
			console.error("Failed to add comment", error);
			Swal.fire("Error", "Could not add your comment.", "error");
		} finally {
			setSubmitting(false);
		}
	};

	const handleReplySubmit = async () => {
		const body = replyDraft.trim();
		if (!body) return;
		if (!ensureAuthenticated()) return;
		if (!activeReplyTarget?.id) return;

		try {
			setReplySubmitting(true);
			const created = await replyToComment(activeReplyTarget.id, body);
			setComments((prev) => appendReplyToThread(prev, created));
			setReplyDraft("");
			setActiveReplyTarget(null);
		} catch (error) {
			console.error("Failed to add reply", error);
			const message =
				error?.response?.data?.parent?.[0] ||
				error?.response?.data?.reply_to?.[0] ||
				"Could not add your reply.";
			Swal.fire("Error", message, "error");
		} finally {
			setReplySubmitting(false);
		}
	};

	const handleToggleLike = async (commentId) => {
		if (!ensureAuthenticated()) return;

		let previousComments = comments;
		setComments((prev) => {
			previousComments = prev;
			return updateCommentTree(prev, commentId, (comment) => {
				const nextLiked = !comment.is_liked_by_me;
				return {
					...comment,
					is_liked_by_me: nextLiked,
					likes_count: Math.max(
						(comment.likes_count || 0) + (nextLiked ? 1 : -1),
						0,
					),
				};
			});
		});

		try {
			const data = await toggleCommentLike(commentId);
			setComments((prev) =>
				updateCommentTree(prev, commentId, (comment) => ({
					...comment,
					is_liked_by_me: data.liked,
					likes_count: data.likes_count,
				})),
			);
		} catch (error) {
			console.error("Failed to like comment", error);
			setComments(previousComments);
			Swal.fire("Error", "Could not update comment like.", "error");
		}
	};

	const handleDelete = async (commentId) => {
		const result = await Swal.fire({
			title: "Delete comment?",
			text: "This comment will be removed permanently.",
			icon: "warning",
			showCancelButton: true,
			confirmButtonColor: "#dc3545",
			cancelButtonColor: "#6c757d",
			confirmButtonText: "Delete",
		});

		if (!result.isConfirmed) return;

		try {
			await deleteComment(commentId);
			setComments((prev) => removeCommentFromTree(prev, commentId));
		} catch (error) {
			console.error("Failed to delete comment", error);
			Swal.fire("Error", "Could not delete comment.", "error");
		}
	};

	const handlePrevImage = (e) => {
		e.stopPropagation();
		setCurrentImageIndex((prev) => Math.max(prev - 1, 0));
	};

	const handleNextImage = (e) => {
		e.stopPropagation();
		setCurrentImageIndex((prev) => Math.min(prev + 1, images.length - 1));
	};

	return (
		<div
			className="d-flex justify-content-center align-items-center"
			style={{
				position: "fixed",
				top: 0,
				left: 0,
				width: "100%",
				height: "100%",
				backgroundColor: "rgba(0, 0, 0, 0.8)",
				zIndex: 1050,
			}}
			onClick={onClose}
		>
			<div
				className="card shadow unified-kit-modal"
				onClick={(e) => e.stopPropagation()}
			>
				<div className="card-header bg-white border-bottom-0 pt-3 pb-2">
					<div className="d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2">
						<div style={{ minWidth: 0 }}>
							<h5 className="fw-bold mb-0 unified-kit-title">{kitTitle}</h5>
							<small className="text-muted d-block">{ownerLabel}</small>
						</div>
						<div className="d-flex align-items-center gap-2 ms-md-auto flex-wrap justify-content-start justify-content-md-end">
							{item?.for_sale && offerUrl && (
								<a
									href={offerUrl}
									target="_blank"
									rel="noopener noreferrer"
									className="btn btn-link btn-sm p-0 text-decoration-none text-muted text-nowrap"
								>
									<i className="bi bi-box-arrow-up-right me-1" aria-hidden="true"></i>
									View offer
								</a>
							)}
							<button
								type="button"
								className="btn btn-link btn-sm p-0 text-decoration-none text-muted text-nowrap"
								onClick={() => copyKitShareUrl(item)}
							>
								<i className="bi bi-link-45deg me-1" aria-hidden="true"></i>
								Share
							</button>
							<button
								type="button"
								className="btn btn-link btn-sm p-0 text-decoration-none text-muted text-nowrap"
								onClick={() => {
									if (!currentUser) {
										ensureAuthenticated();
										return;
									}
									setReportModalOpen(true);
								}}
							>
								<i className="bi bi-flag me-1" aria-hidden="true"></i>
								Report kit
							</button>
							<button className="btn-close" onClick={onClose}></button>
						</div>
					</div>
				</div>

				<div className="card-body p-0 unified-kit-body">
					<div className="d-flex flex-column flex-lg-row h-100">
						<div className="unified-kit-media bg-dark text-white">
							{activeImage ? (
								<>
									<div className="unified-kit-stage">
										{!reportModalOpen &&
											images.length > 1 &&
											currentImageIndex > 0 && (
											<button
												type="button"
												className="lightbox-nav-btn nav-prev"
												onClick={handlePrevImage}
											>
												&#10094;
											</button>
										)}

										<div className="unified-kit-stage-inner">
											<img
												src={activeImage.image}
												alt={`Kit ${currentImageIndex + 1}`}
												className="lightbox-img"
											/>
										</div>

										{!reportModalOpen &&
											images.length > 1 &&
											currentImageIndex < images.length - 1 && (
												<button
													type="button"
													className="lightbox-nav-btn nav-next"
													onClick={handleNextImage}
												>
													&#10095;
												</button>
											)}
									</div>

									<div className="unified-kit-footer px-3 pb-3 pt-2">
										<div className="d-flex justify-content-between align-items-center small text-white-50 mb-2">
											<span>{formatImagesText(currentImageIndex, images.length)}</span>
										</div>

										{images.length > 1 && (
											<div className="unified-kit-thumbs">
												{images.map((image, index) => (
													<button
														key={image.id}
														type="button"
														className={`unified-kit-thumb ${index === currentImageIndex ? "active" : ""}`}
														onClick={(e) => {
															e.stopPropagation();
															setCurrentImageIndex(index);
														}}
													>
														<img
															src={image.image}
															alt={`Preview ${index + 1}`}
															className="w-100 h-100 rounded"
															style={{ objectFit: "cover" }}
														/>
													</button>
												))}
											</div>
										)}
									</div>
								</>
							) : (
								<div className="unified-kit-stage text-center text-white-50">
									<div>No photo available</div>
								</div>
							)}
						</div>

						<div className="unified-kit-comments bg-white">
							<div className="overflow-auto h-100 p-3 p-lg-4">
								<div className="mb-4">
									<textarea
										className="form-control"
										rows="3"
										placeholder={
											currentUser
												? "Add a comment..."
												: "Log in to join the conversation..."
										}
										value={draft}
										onChange={(e) => setDraft(e.target.value)}
										disabled={!currentUser || submitting}
									/>
									<div className="d-flex justify-content-between align-items-center gap-3 mt-2">
										<small className="text-muted fw-semibold text-nowrap">
											{totalComments} {totalComments === 1 ? "comment" : "comments"}
										</small>
										<button
											type="button"
											className="btn btn-primary rounded-pill px-4"
											onClick={handleAddComment}
											disabled={!currentUser || submitting || !draft.trim()}
										>
											{submitting ? "Posting..." : "Post comment"}
										</button>
									</div>
								</div>

								{loading ? (
									<div className="text-center py-4">
										<div className="spinner-border spinner-border-sm text-primary"></div>
									</div>
								) : comments.length === 0 ? (
									<div className="text-center py-4 text-muted">
										No comments yet. Start the conversation.
									</div>
								) : (
									<div className="d-flex flex-column gap-4">
										{comments.map((comment) => (
											<CommentItem
												key={comment.id}
												comment={comment}
												currentUser={currentUser}
												activeReplyId={activeReplyTarget?.id || null}
												replyDraft={replyDraft}
												replySubmitting={replySubmitting}
												onReplyStart={(commentId) => {
													if (commentId === null) {
														setActiveReplyTarget(null);
														setReplyDraft("");
														return;
													}

													const targetComment = findCommentById(comments, commentId);
													setActiveReplyTarget(
														targetComment
															? {
																	id: targetComment.id,
																	username:
																		targetComment.user?.username || "Unknown",
																}
															: { id: commentId, username: "Unknown" },
													);
												}}
												onReplyChange={setReplyDraft}
												onReplySubmit={handleReplySubmit}
												onToggleLike={handleToggleLike}
												onDelete={handleDelete}
											/>
										))}
									</div>
								)}
							</div>
						</div>
					</div>
				</div>
			</div>
			<ReportKitModal
				isOpen={reportModalOpen}
				onClose={() => setReportModalOpen(false)}
				kitId={kitId}
			/>
		</div>
	);
};

function formatImagesText(currentImageIndex, totalImages) {
	if (totalImages <= 1) {
		return totalImages === 1 ? "1 image" : "No images";
	}

	return `Photo ${currentImageIndex + 1} / ${totalImages}`;
}

function formatKitTitle(item) {
	const teamName = item?.kit?.team?.name?.trim();
	const season = item?.kit?.season?.trim();
	const kitType = item?.kit?.kit_type?.trim();

	return [teamName, season, kitType].filter(Boolean).join(" ") || "Kit";
}

function formatOwnerLabel(item) {
	const owner = item?.owner_username?.trim();

	if (!owner) return "";

	return `${owner}'s Kit`;
}

function getSafeUrl(url) {
	if (!url) return "";

	return /^(https?):\/\//i.test(url) ? url : "";
}

export default CommentsModal;
