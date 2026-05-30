import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Swal from "sweetalert2";

import UserAvatar from "../components/UserAvatar";
import {
	getConversation,
	getConversationMessages,
	getConversations,
	sendConversationMessage,
} from "../services/api";

const MessagesPage = ({ user, refreshUnreadMessagesCount }) => {
	const { conversationId } = useParams();
	const navigate = useNavigate();
	const [conversations, setConversations] = useState([]);
	const [loadingConversations, setLoadingConversations] = useState(true);
	const [selectedConversation, setSelectedConversation] = useState(null);
	const [messages, setMessages] = useState([]);
	const [loadingMessages, setLoadingMessages] = useState(false);
	const [draft, setDraft] = useState("");
	const [sending, setSending] = useState(false);
	const [pageError, setPageError] = useState("");

	useEffect(() => {
		const loadConversations = async () => {
			setLoadingConversations(true);
			setPageError("");

			try {
				const data = await getConversations();
				setConversations(Array.isArray(data) ? data : []);
			} catch (error) {
				console.error("Failed to load conversations", error);
				setPageError("Could not load conversations.");
			} finally {
				setLoadingConversations(false);
			}
		};

		loadConversations();
	}, []);

	useEffect(() => {
		if (!conversationId) {
			setSelectedConversation(null);
			setMessages([]);
			return;
		}

		const markConversationAsReadLocally = (id) => {
			setConversations((prev) =>
				prev.map((conversation) =>
					String(conversation.id) === String(id)
						? {
								...conversation,
								unread_count: 0,
							}
						: conversation
				)
			);
		};

		const loadConversation = async () => {
			setLoadingMessages(true);
			setPageError("");

			try {
				const [conversationData, messagesData] = await Promise.all([
					getConversation(conversationId),
					getConversationMessages(conversationId),
				]);
				setSelectedConversation(conversationData);
				setMessages(Array.isArray(messagesData) ? messagesData : []);
				markConversationAsReadLocally(conversationId);
				if (refreshUnreadMessagesCount) {
					await refreshUnreadMessagesCount();
				}
			} catch (error) {
				console.error("Failed to load conversation", error);
				setPageError("Could not load this conversation.");
			} finally {
				setLoadingMessages(false);
			}
		};

		loadConversation();
	}, [conversationId]);

	const refreshConversations = async () => {
		try {
			const data = await getConversations();
			setConversations(Array.isArray(data) ? data : []);
		} catch (error) {
			console.error("Failed to refresh conversations", error);
		}
	};

	const handleOpenConversation = (id) => {
		navigate(`/messages/${id}`);
	};

	const handleSendMessage = async () => {
		const body = draft.trim();
		if (!body || !conversationId || sending) return;

		try {
			setSending(true);
			const created = await sendConversationMessage(conversationId, body);
			setMessages((prev) => [...prev, created]);
			setDraft("");
			await refreshConversations();
			if (refreshUnreadMessagesCount) {
				await refreshUnreadMessagesCount();
			}
		} catch (error) {
			console.error("Failed to send message", error);
			const message =
				error?.response?.data?.body?.[0] || "Could not send your message.";
			Swal.fire("Error", message, "error");
		} finally {
			setSending(false);
		}
	};

	const handleComposerKeyDown = (event) => {
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			handleSendMessage();
		}
	};

	return (
		<div className="container py-4 py-lg-5">
			<div className="row g-4">
				<div className="col-12 col-lg-4">
					<div className="card shadow-sm border-0 h-100">
						<div className="card-body p-0">
							<div className="p-3 border-bottom">
								<h1 className="h4 fw-bold mb-0">Messages</h1>
							</div>

							{loadingConversations ? (
								<div className="text-center py-5">
									<div className="spinner-border text-primary" role="status"></div>
								</div>
							) : conversations.length === 0 ? (
								<div className="text-center text-muted py-5 px-4">
									No conversations yet.
								</div>
							) : (
								<div className="list-group list-group-flush">
									{conversations.map((conversation) => {
										const isActive =
											String(conversation.id) === String(conversationId);
										const unreadCount = conversation.unread_count ?? 0;
										const isUnread = unreadCount > 0;
										return (
											<button
												key={conversation.id}
												type="button"
												className={`list-group-item list-group-item-action border-0 text-start px-3 py-3 ${isActive ? "bg-light" : ""}`}
												onClick={() => handleOpenConversation(conversation.id)}
											>
												<div className="d-flex align-items-center gap-3">
													<UserAvatar
														user={conversation.other_user}
														size={42}
													/>
													<div className="min-w-0 flex-grow-1">
														<div className={`${isUnread ? "fw-bold" : "fw-semibold"} text-dark`}>
															{conversation.other_user?.username}
														</div>
														<div className={`small text-truncate ${isUnread ? "fw-semibold text-dark" : "text-muted"}`}>
															{conversation.last_message_preview ||
																"Start the conversation"}
														</div>
													</div>
													{isUnread && (
														<span className="badge rounded-pill bg-primary-subtle text-primary-emphasis">
															{unreadCount > 99 ? "99+" : unreadCount}
														</span>
													)}
												</div>
											</button>
										);
									})}
								</div>
							)}
						</div>
					</div>
				</div>

				<div className="col-12 col-lg-8">
					<div className="card shadow-sm border-0 h-100">
						<div className="card-body d-flex flex-column p-0" style={{ minHeight: "70vh" }}>
							{pageError ? (
								<div className="text-center text-danger py-5 px-4">
									{pageError}
								</div>
							) : !conversationId ? (
								<div className="text-center text-muted py-5 px-4 my-auto">
									Select a conversation to view messages.
								</div>
							) : loadingMessages ? (
								<div className="text-center py-5 my-auto">
									<div className="spinner-border text-primary" role="status"></div>
								</div>
							) : selectedConversation ? (
								<>
									<div className="d-flex align-items-center gap-3 p-3 border-bottom">
										<UserAvatar
											user={selectedConversation.other_user}
											size={48}
										/>
										<div>
											<div className="fw-bold">
												{selectedConversation.other_user?.username}
											</div>
											<Link
												to={`/profile/${selectedConversation.other_user?.username}`}
												className="small text-muted text-decoration-none"
											>
												View profile
											</Link>
										</div>
									</div>

									<div className="flex-grow-1 overflow-auto p-3 bg-light-subtle">
										{messages.length === 0 ? (
											<div className="text-center text-muted py-5">
												No messages yet. Say hello.
											</div>
										) : (
											<div className="d-flex flex-column gap-3">
												{messages.map((message) => (
													<div
														key={message.id}
														className={`d-flex ${message.is_mine ? "justify-content-end" : "justify-content-start"}`}
													>
														<div
															className={`px-3 py-2 rounded-3 shadow-sm ${message.is_mine ? "bg-primary text-white" : "bg-white"}`}
															style={{ maxWidth: "75%" }}
														>
															<div className="small">{message.body}</div>
															<div
																className={`small mt-1 ${message.is_mine ? "text-white-50" : "text-muted"}`}
															>
																{new Date(message.created_at).toLocaleString("en-GB", {
																	day: "numeric",
																	month: "short",
																	hour: "2-digit",
																	minute: "2-digit",
																})}
															</div>
														</div>
													</div>
												))}
											</div>
										)}
									</div>

									<div className="border-top p-3">
										<div className="d-flex gap-2">
												<textarea
												className="form-control"
												rows="2"
												style={{ resize: "none" }}
												placeholder="Write a message..."
												value={draft}
												onChange={(e) => setDraft(e.target.value)}
												onKeyDown={handleComposerKeyDown}
												disabled={sending}
											/>
											<button
												type="button"
												className="btn btn-primary px-4"
												onClick={handleSendMessage}
												disabled={sending || !draft.trim()}
											>
												{sending ? "Sending..." : "Send"}
											</button>
										</div>
									</div>
								</>
							) : null}
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default MessagesPage;
