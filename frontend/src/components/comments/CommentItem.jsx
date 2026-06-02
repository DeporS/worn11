import { useTranslation } from "react-i18next";

const formatCommentDate = (value) => {
	if (!value) return "";

	return new Date(value).toLocaleString("en-GB", {
		day: "numeric",
		month: "short",
		year: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
};

const getReplyMetaLabel = (comment, fallbackReplyToUsername) => {
	const authorUsername = comment.user?.username || "Unknown";
	const replyTarget =
		comment.reply_to_username || fallbackReplyToUsername || "";

	if (!comment.parent_id || !replyTarget) {
		return authorUsername;
	}

	return `${authorUsername} > ${replyTarget}`;
};

const CommentItem = ({
	comment,
	isReply = false,
	parentAuthorUsername = "",
	currentUser,
	activeReplyId,
	replyDraft,
	replySubmitting,
	onReplyStart,
	onReplyChange,
	onReplySubmit,
	onToggleLike,
	onDelete,
}) => {
	const { t } = useTranslation();
	const avatar = comment.user?.avatar;
	const username = comment.user?.username || "Unknown";
	const isReplyBoxOpen = activeReplyId === comment.id;
	const replyMetaLabel = getReplyMetaLabel(comment, parentAuthorUsername);
	const replyTargetLabel =
		comment.user?.username ||
		comment.reply_to_username ||
		parentAuthorUsername ||
		"Unknown";

	return (
		<div className={`${isReply ? "ms-4 mt-3 ps-3 border-start" : ""}`}>
			<div className="d-flex gap-3">
				{avatar ? (
					<img
						src={avatar}
						alt={username}
						className="rounded-circle"
						style={{
							width: "40px",
							height: "40px",
							objectFit: "cover",
							flexShrink: 0,
						}}
					/>
				) : (
					<div
						className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold"
						style={{
							width: "40px",
							height: "40px",
							flexShrink: 0,
						}}
					>
						{username.charAt(0).toUpperCase()}
					</div>
				)}

				<div className="flex-grow-1">
					<div className="bg-light rounded-4 px-3 py-2">
						<div className="d-flex justify-content-between gap-3 align-items-start">
							<div>
								<div className="fw-semibold small">
									{replyMetaLabel}
								</div>
								<div className="small text-dark">
									{comment.body}
								</div>
							</div>
							<small className="text-muted text-nowrap">
								{formatCommentDate(comment.created_at)}
							</small>
						</div>
					</div>

					<div className="d-flex flex-wrap align-items-center gap-3 mt-2 small text-muted">
						<button
							type="button"
							className="btn btn-link p-0 text-decoration-none small text-muted"
							onClick={() => onToggleLike(comment.id)}
						>
							<i
								className={`bi ${comment.is_liked_by_me ? "bi-heart-fill text-danger" : "bi-heart"} me-1`}
							></i>
							{comment.likes_count || 0}
						</button>

						{currentUser && (
							<button
								type="button"
								className="btn btn-link p-0 text-decoration-none small text-muted"
								onClick={() => onReplyStart(comment.id)}
							>
								{t("comments.reply")}
							</button>
						)}

						{comment.can_delete && (
							<button
								type="button"
								className="btn btn-link p-0 text-decoration-none small text-danger"
								onClick={() => onDelete(comment.id)}
							>
								{t("comments.delete")}
							</button>
						)}
					</div>

					{isReplyBoxOpen && (
						<div className="mt-3">
							<div className="small text-muted mb-2">
								{t("comments.replyingTo", { username: replyTargetLabel })}
							</div>
							<textarea
								className="form-control form-control-sm"
								rows="2"
								placeholder={t("comments.writeReply")}
								value={replyDraft}
								onChange={(e) => onReplyChange(e.target.value)}
								style={{ resize: "none" }}
							/>
							<div className="d-flex justify-content-end gap-2 mt-2">
								<button
									type="button"
									className="btn btn-sm btn-outline-secondary rounded-pill"
									onClick={() => onReplyStart(null)}
								>
									{t("comments.cancel")}
								</button>
								<button
									type="button"
									className="btn btn-sm btn-primary rounded-pill"
									onClick={onReplySubmit}
									disabled={replySubmitting}
								>
									{replySubmitting ? t("comments.replying") : t("comments.reply")}
								</button>
							</div>
						</div>
					)}

					{!isReply &&
						comment.replies?.map((reply) => (
							<CommentItem
								key={reply.id}
								comment={reply}
								isReply
								parentAuthorUsername={username}
								currentUser={currentUser}
								activeReplyId={activeReplyId}
								replyDraft={replyDraft}
								replySubmitting={replySubmitting}
								onReplyStart={onReplyStart}
								onReplyChange={onReplyChange}
								onReplySubmit={onReplySubmit}
								onToggleLike={onToggleLike}
								onDelete={onDelete}
							/>
						))}
				</div>
			</div>
		</div>
	);
};

export default CommentItem;
