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

const CommentItem = ({
	comment,
	isReply = false,
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
	const avatar = comment.user?.avatar;
	const username = comment.user?.username || "Unknown";
	const isReplyBoxOpen = activeReplyId === comment.id;

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
								<div className="fw-semibold small">{username}</div>
								<div className="small text-dark">{comment.body}</div>
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

						{!isReply && currentUser && (
							<button
								type="button"
								className="btn btn-link p-0 text-decoration-none small text-muted"
								onClick={() => onReplyStart(comment.id)}
							>
								Reply
							</button>
						)}

						{comment.can_delete && (
							<button
								type="button"
								className="btn btn-link p-0 text-decoration-none small text-danger"
								onClick={() => onDelete(comment.id)}
							>
								Delete
							</button>
						)}
					</div>

					{isReplyBoxOpen && (
						<div className="mt-3">
							<textarea
								className="form-control form-control-sm"
								rows="2"
								placeholder={`Reply to ${username}...`}
								value={replyDraft}
								onChange={(e) => onReplyChange(e.target.value)}
							/>
							<div className="d-flex justify-content-end gap-2 mt-2">
								<button
									type="button"
									className="btn btn-sm btn-outline-secondary rounded-pill"
									onClick={() => onReplyStart(null)}
								>
									Cancel
								</button>
								<button
									type="button"
									className="btn btn-sm btn-primary rounded-pill"
									onClick={() => onReplySubmit(comment.id)}
									disabled={replySubmitting}
								>
									{replySubmitting ? "Replying..." : "Reply"}
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
