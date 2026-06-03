import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import Swal from "sweetalert2";

import {
	getNotifications,
	markNotificationsRead,
} from "../../services/api";
import { formatLocalizedDate } from "../../utils/dateFormat";

const NOTIFICATIONS_PAGE_SIZE = 20;

const NotificationsDropdown = ({
	unreadCount = 0,
	refreshUnreadNotificationsCount,
	onCloseMobileMenu,
}) => {
	const { t, i18n } = useTranslation();
	const navigate = useNavigate();
	const containerRef = useRef(null);
	const [isOpen, setIsOpen] = useState(false);
	const [notifications, setNotifications] = useState([]);
	const [loading, setLoading] = useState(false);
	const [markingRead, setMarkingRead] = useState(false);

	const hasUnreadNotifications = (items = notifications) =>
		items.some((notification) => !notification.is_read);

	const syncReadState = async () => {
		if (unreadCount <= 0 && !hasUnreadNotifications()) return;

		try {
			await markNotificationsRead();
			setNotifications((prev) =>
				prev.map((notification) => ({
					...notification,
					read_at: notification.read_at || new Date().toISOString(),
					is_read: true,
				})),
			);
			if (refreshUnreadNotificationsCount) {
				await refreshUnreadNotificationsCount();
			}
		} catch (error) {
			console.error("Failed to mark notifications as read on close", error);
		}
	};

	const closeDropdown = async ({ markAsRead = true } = {}) => {
		setIsOpen(false);

		if (markAsRead) {
			await syncReadState();
		}
	};

	useEffect(() => {
		if (!isOpen) return undefined;

		const handleClickOutside = (event) => {
			if (containerRef.current && !containerRef.current.contains(event.target)) {
				closeDropdown();
			}
		};

		const handleEscape = (event) => {
			if (event.key === "Escape") {
				closeDropdown();
			}
		};

		document.addEventListener("mousedown", handleClickOutside);
		window.addEventListener("keydown", handleEscape);

		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
			window.removeEventListener("keydown", handleEscape);
		};
	}, [isOpen, notifications, refreshUnreadNotificationsCount]);

	const loadNotifications = async () => {
		try {
			setLoading(true);
			const data = await getNotifications({ limit: NOTIFICATIONS_PAGE_SIZE });
			setNotifications(Array.isArray(data?.results) ? data.results : []);
		} catch (error) {
			console.error("Failed to load notifications", error);
			Swal.fire(t("common.error"), t("notifications.loadError"), "error");
		} finally {
			setLoading(false);
		}
	};

	const handleToggle = async () => {
		const nextOpen = !isOpen;
		setIsOpen(nextOpen);

		if (nextOpen) {
			await loadNotifications();
		}
	};

	const handleMarkAllRead = async () => {
		if (markingRead) return;

		try {
			setMarkingRead(true);
			await markNotificationsRead();
			setNotifications((prev) =>
				prev.map((notification) => ({
					...notification,
					read_at: notification.read_at || new Date().toISOString(),
					is_read: true,
				})),
			);
			if (refreshUnreadNotificationsCount) {
				await refreshUnreadNotificationsCount();
			}
		} catch (error) {
			console.error("Failed to mark notifications as read", error);
			Swal.fire(t("common.error"), t("notifications.markReadError"), "error");
		} finally {
			setMarkingRead(false);
		}
	};

	const handleNotificationClick = (notification) => {
		if (
			["kit_like", "kit_comment", "comment_like", "comment_reply"].includes(notification.type) &&
			notification.kit?.owner_username &&
			notification.kit?.id
		) {
			navigate(`/profile/${notification.kit.owner_username}/kits/${notification.kit.id}`);
		} else if (notification.type === "follow" && notification.actor?.username) {
			navigate(`/profile/${notification.actor.username}`);
		}

		closeDropdown();
		if (onCloseMobileMenu) {
			onCloseMobileMenu();
		}
	};

	const getMessage = (notification) => {
		if (notification.type === "kit_like") {
			return t("notifications.likedYourKit", {
				username: notification.actor?.username || "",
			});
		}

		if (notification.type === "follow") {
			return t("notifications.startedFollowingYou", {
				username: notification.actor?.username || "",
			});
		}

		if (notification.type === "kit_comment") {
			return t("notifications.commentedOnYourKit", {
				username: notification.actor?.username || "",
			});
		}

		if (notification.type === "comment_like") {
			return t("notifications.likedYourComment", {
				username: notification.actor?.username || "",
			});
		}

		if (notification.type === "comment_reply") {
			return t("notifications.repliedToYourComment", {
				username: notification.actor?.username || "",
			});
		}

		return notification.actor?.username || "";
	};

	return (
		<div className="position-relative" ref={containerRef}>
			<button
				type="button"
				className="btn btn-link text-decoration-none text-dark position-relative p-2 rounded hover-bg-light border-0"
				onClick={handleToggle}
				title={t("notifications.open")}
				aria-label={t("notifications.open")}
				aria-expanded={isOpen}
			>
				<i className="bi bi-bell fs-4"></i>
				{unreadCount > 0 && (
					<span
						className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
						style={{ fontSize: "0.65rem" }}
					>
						{unreadCount > 99 ? "99+" : unreadCount}
						<span className="visually-hidden">
							{t("notifications.unreadLabel")}
						</span>
					</span>
				)}
			</button>

			{isOpen ? (
				<div
					className="dropdown-menu dropdown-menu-end show p-0 shadow border-0 overflow-hidden"
					style={{
						width: "min(380px, calc(100vw - 2rem))",
						maxHeight: "70vh",
					}}
				>
					<div className="d-flex align-items-center justify-content-between px-3 py-3 border-bottom bg-white">
						<h6 className="mb-0 fw-bold">{t("notifications.title")}</h6>
						<button
							type="button"
							className="btn btn-link btn-sm text-decoration-none px-0"
							onClick={handleMarkAllRead}
							disabled={markingRead || unreadCount === 0}
						>
							{t("notifications.markAllRead")}
						</button>
					</div>

					<div className="bg-white overflow-auto" style={{ maxHeight: "calc(70vh - 64px)" }}>
						{loading ? (
							<div className="px-3 py-4 text-center text-muted">
								{t("notifications.loading")}
							</div>
						) : notifications.length === 0 ? (
							<div className="px-3 py-4 text-center text-muted">
								{t("notifications.empty")}
							</div>
						) : (
							notifications.map((notification) => (
								<button
									key={notification.id}
									type="button"
									className={`dropdown-item px-3 py-3 border-bottom text-wrap ${notification.is_read ? "bg-white" : "bg-light"}`}
									onClick={() => handleNotificationClick(notification)}
								>
									<div className="d-flex align-items-start gap-3">
										<div
											className="rounded overflow-hidden bg-light border flex-shrink-0 d-flex align-items-center justify-content-center"
											style={{ width: "48px", height: "48px" }}
										>
											{notification.kit?.preview_image ? (
												<img
													src={notification.kit.preview_image}
													alt={notification.kit.team_name || "Kit preview"}
													style={{
														width: "100%",
														height: "100%",
														objectFit: "cover",
													}}
												/>
											) : notification.actor?.avatar ? (
												<img
													src={notification.actor.avatar}
													alt={notification.actor.username || "User avatar"}
													style={{
														width: "100%",
														height: "100%",
														objectFit: "cover",
													}}
												/>
											) : (
												<i className="bi bi-bell text-muted"></i>
											)}
										</div>
										<div className="min-w-0 flex-grow-1 text-start">
											<div className="fw-medium text-dark">
												{getMessage(notification)}
											</div>
											{notification.kit ? (
												<div className="small text-muted text-truncate">
													{[
														notification.kit.team_name,
														notification.kit.season,
														notification.kit.kit_type,
													]
														.filter(Boolean)
														.join(" ")}
												</div>
											) : null}
											{notification.comment?.body_preview ? (
												<div className="small text-muted text-truncate mt-1">
													{notification.comment.body_preview}
												</div>
											) : null}
											<div className="small text-muted mt-1">
												{formatLocalizedDate(notification.created_at, i18n.language, {
													hour: "2-digit",
													minute: "2-digit",
												})}
											</div>
										</div>
										{!notification.is_read ? (
											<span
												className="bg-primary rounded-circle flex-shrink-0 mt-2"
												style={{ width: "8px", height: "8px" }}
												aria-hidden="true"
											/>
										) : null}
									</div>
								</button>
							))
						)}
					</div>
				</div>
			) : null}
		</div>
	);
};

export default NotificationsDropdown;
