import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Swal from "sweetalert2";

import UserAvatar from "../components/UserAvatar";
import {
	getConversation,
	getConversationMessages,
	getConversations,
	sendConversationMessage,
} from "../services/api";
import "../styles/messages.css";

const MessagesPage = ({ user, refreshUnreadMessagesCount }) => {
	const MESSAGES_PAGE_SIZE = 30;
	const { conversationId } = useParams();
	const navigate = useNavigate();
	const [conversations, setConversations] = useState([]);
	const [loadingConversations, setLoadingConversations] = useState(true);
	const [selectedConversation, setSelectedConversation] = useState(null);
	const [messages, setMessages] = useState([]);
	const [hasMoreMessages, setHasMoreMessages] = useState(false);
	const [loadingMessages, setLoadingMessages] = useState(false);
	const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
	const [draft, setDraft] = useState("");
	const [sending, setSending] = useState(false);
	const [pageError, setPageError] = useState("");
	const [navbarHeight, setNavbarHeight] = useState(0);
	const messageListRef = useRef(null);
	const scrollTimeoutRef = useRef(null);
	const scrollRafRef = useRef(null);
	const shouldScrollToBottomRef = useRef(false);
	const prependScrollStateRef = useRef(null);
	const hasInitialScrolledToBottomRef = useRef(false);

	useEffect(() => {
		const navbar = document.querySelector(".navbar");
		if (!navbar) return undefined;

		const updateNavbarHeight = () => {
			setNavbarHeight(navbar.getBoundingClientRect().height);
		};

		updateNavbarHeight();

		const resizeObserver =
			typeof ResizeObserver !== "undefined"
				? new ResizeObserver(updateNavbarHeight)
				: null;

		if (resizeObserver) {
			resizeObserver.observe(navbar);
		}

		window.addEventListener("resize", updateNavbarHeight);

		return () => {
			window.removeEventListener("resize", updateNavbarHeight);
			if (resizeObserver) {
				resizeObserver.disconnect();
			}
		};
	}, []);

	useEffect(() => {
		if (!selectedConversation || loadingMessages) return undefined;

		const scrollMessagesToBottom = () => {
			const container = messageListRef.current;
			if (!container) return;

			container.scrollTop = container.scrollHeight;
		};

		const restorePrependedScrollPosition = () => {
			const container = messageListRef.current;
			const scrollState = prependScrollStateRef.current;
			if (!container || !scrollState) return;

			container.scrollTop =
				container.scrollHeight -
				scrollState.previousScrollHeight +
				scrollState.previousScrollTop;
			prependScrollStateRef.current = null;
		};

		const scheduleBottomScroll = () => {
			if (scrollRafRef.current) {
				window.cancelAnimationFrame(scrollRafRef.current);
			}

			scrollRafRef.current = window.requestAnimationFrame(() => {
				scrollMessagesToBottom();

				scrollRafRef.current = window.requestAnimationFrame(() => {
					scrollMessagesToBottom();
				});
			});
		};

		if (scrollTimeoutRef.current) {
			window.clearTimeout(scrollTimeoutRef.current);
		}

		scrollTimeoutRef.current = window.setTimeout(() => {
			if (prependScrollStateRef.current) {
				restorePrependedScrollPosition();
				return;
			}

			if (shouldScrollToBottomRef.current) {
				shouldScrollToBottomRef.current = false;
				hasInitialScrolledToBottomRef.current = true;
				scheduleBottomScroll();
			}
		}, 0);

		return () => {
			if (scrollTimeoutRef.current) {
				window.clearTimeout(scrollTimeoutRef.current);
			}

			if (scrollRafRef.current) {
				window.cancelAnimationFrame(scrollRafRef.current);
			}
		};
	}, [messages, selectedConversation, conversationId, loadingMessages]);

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
			setHasMoreMessages(false);
			hasInitialScrolledToBottomRef.current = false;
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
			setMessages([]);
			setHasMoreMessages(false);
			hasInitialScrolledToBottomRef.current = false;

			try {
				const [conversationData, messagesData] = await Promise.all([
					getConversation(conversationId),
					getConversationMessages(conversationId, {
						limit: MESSAGES_PAGE_SIZE,
					}),
				]);
				shouldScrollToBottomRef.current = true;
				setSelectedConversation(conversationData);
				setMessages(Array.isArray(messagesData?.results) ? messagesData.results : []);
				setHasMoreMessages(Boolean(messagesData?.has_more));
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
			shouldScrollToBottomRef.current = true;
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

	const handleLoadOlderMessages = async () => {
		if (!conversationId || loadingOlderMessages || !hasMoreMessages || messages.length === 0) {
			return;
		}

		const container = messageListRef.current;
		const oldestMessageId = messages[0]?.id;
		if (!oldestMessageId) return;

		prependScrollStateRef.current = {
			previousScrollHeight: container?.scrollHeight ?? 0,
			previousScrollTop: container?.scrollTop ?? 0,
		};

		try {
			setLoadingOlderMessages(true);
			const data = await getConversationMessages(conversationId, {
				limit: MESSAGES_PAGE_SIZE,
				before: oldestMessageId,
			});
			const olderMessages = Array.isArray(data?.results) ? data.results : [];

			if (olderMessages.length === 0) {
				prependScrollStateRef.current = null;
				setHasMoreMessages(Boolean(data?.has_more));
				return;
			}

			setMessages((prev) => [...olderMessages, ...prev]);
			setHasMoreMessages(Boolean(data?.has_more));
		} catch (error) {
			prependScrollStateRef.current = null;
			console.error("Failed to load older messages", error);
			Swal.fire("Error", "Could not load older messages.", "error");
		} finally {
			setLoadingOlderMessages(false);
		}
	};

	const handleMessagesScroll = () => {
		if (
			!selectedConversation ||
			!hasInitialScrolledToBottomRef.current ||
			loadingMessages ||
			loadingOlderMessages ||
			!hasMoreMessages
		) {
			return;
		}

		const container = messageListRef.current;
		if (!container) return;

		if (container.scrollTop <= 80) {
			handleLoadOlderMessages();
		}
	};

	const handleComposerKeyDown = (event) => {
		if (event.key === "Enter" && !event.shiftKey) {
			event.preventDefault();
			handleSendMessage();
		}
	};

	const formatMessageTime = (value) => {
		if (!value) return "";

		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return "";

		const now = new Date();
		const diffMs = now - date;
		if (diffMs < 0) {
			return date.toLocaleString("en-GB", {
				day: "numeric",
				month: "short",
				hour: "2-digit",
				minute: "2-digit",
			});
		}

		const diffMinutes = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMinutes / 60);

		if (diffMinutes < 1) return "just now";
		if (diffMinutes < 60) {
			return `${diffMinutes} ${diffMinutes === 1 ? "min" : "mins"} ago`;
		}
		if (diffHours < 24) {
			return `${diffHours} ${diffHours === 1 ? "hour" : "hours"} ago`;
		}

		return date.toLocaleString("en-GB", {
			day: "numeric",
			month: "short",
			hour: "2-digit",
			minute: "2-digit",
		});
	};

	return (
		<div
			className="messages-page py-3 py-lg-4"
			style={{
				"--messages-navbar-height": `${navbarHeight}px`,
			}}
		>
			<div className="messages-shell row g-4">
				<div className="col-12 col-lg-4 messages-sidebar">
					<div className="card shadow-sm border-0 messages-panel messages-sidebar-panel">
						<div className="p-3 border-bottom">
							<h1 className="h4 fw-bold mb-0">Messages</h1>
						</div>

						<div className="messages-sidebar-scroll">
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

				<div className="col-12 col-lg-8 messages-thread">
					<div className="card shadow-sm border-0 messages-panel messages-thread-panel">
						<div className="card-body d-flex flex-column p-0 messages-thread-content">
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
									<div className="messages-thread-header d-flex align-items-center gap-3 p-3 border-bottom">
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

										<div
											ref={messageListRef}
										className="messages-thread-body p-3 bg-light-subtle"
											onScroll={handleMessagesScroll}
									>
										{loadingOlderMessages && (
											<div className="d-flex justify-content-center mb-3 small text-muted">
												Loading older messages...
											</div>
										)}

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
																{formatMessageTime(message.created_at)}
															</div>
														</div>
													</div>
												))}
											</div>
										)}
									</div>

									<div className="messages-thread-composer border-top p-3">
										<div className="d-flex gap-2 align-items-end">
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
