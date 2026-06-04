import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
	getUserCollection,
	getUserStats,
	toggleFollowUser,
	getFollowersList,
	getFollowingList,
	startConversation,
} from "../services/api";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import Swal from "sweetalert2";
import KitCard from "../components/profile/KitCard";
import SocialLink from "../components/profile/SocialLink";
import MarketBadge from "../components/profile/MarketBadge";
import UserAvatar from "../components/UserAvatar";
import UserListModal from "../components/profile/UserListModal";
import CollectionValueChartModal from "../components/profile/CollectionValueChartModal";

import "../styles/profile.css";

import EyeCloseIcon from "../assets/icons/eye-close.svg?react";
import EyeOpenIcon from "../assets/icons/eye-open.svg?react";
import DiamondIcon from "../assets/icons/diamond-blue.svg?react";
import ShieldIcon from "../assets/icons/shield-2.svg?react";
import ShirtIcon from "../assets/icons/shirt.svg?react";
import MoneyBagIcon from "../assets/icons/money-bag.svg?react";
import FollowersIcon from "../assets/icons/followers.svg?react";
import FollowingIcon from "../assets/icons/following.svg?react";
import { localizeCountryName } from "../utils/localizedCountries";

const ProfilePage = ({ user }) => {
	const { t } = useTranslation();
	const { username } = useParams(); // Get username from URL params
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();
	const profileUsername = username || user?.username;
	const highlightedKitId = searchParams.get("highlightKit");
	const isOwner = user?.username === profileUsername; // Check if viewing own profile

	const [myKits, setMyKits] = useState([]);
	const [stats, setStats] = useState({ total_value: 0, total_kits: 0 });
	const [profileData, setProfileData] = useState(null);

	const [showEmail, setShowEmail] = useState(false); // For toggling email visibility
	const [isExpanded, setIsExpanded] = useState(true); // For bio expansion

	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	const [hover, setHover] = useState(false);

	// Following states
	const [isFollowing, setIsFollowing] = useState(false);
	const [followersCount, setFollowersCount] = useState(0);
	const [followingCount, setFollowingCount] = useState(0);
	const [followLoading, setFollowLoading] = useState(false);

	// Modal states for followers/following lists
	const [modalType, setModalType] = useState(null); // 'followers' or 'following' or null
	const [modalUsers, setModalUsers] = useState([]); // Users list for modal
	const [modalLoading, setModalLoading] = useState(false);
	const [activeHighlightedKitId, setActiveHighlightedKitId] = useState(null);
	const [isValueHistoryOpen, setIsValueHistoryOpen] = useState(false);
	const hasScrolledToHighlightedKitRef = useRef(false);
	const highlightTimeoutRef = useRef(null);

	useEffect(() => {
		if (!profileUsername) return;

		setLoading(true);
		setError(null);

		Promise.all([
			getUserCollection(profileUsername),
			getUserStats(profileUsername),
		])
			.then(([kitsData, statsData]) => {
				setMyKits(kitsData);
				setStats(statsData);
				setProfileData(statsData);

				// Set following states
				setIsFollowing(statsData.is_followed_by_me);
				setFollowersCount(statsData.followers_count || 0);
				setFollowingCount(statsData.following_count || 0);
			})
			.catch((err) => {
				console.error("Failed to load profile", err);
				setError(t("profile.loadError"));
			})
			.finally(() => setLoading(false));
	}, [profileUsername, user?.username, t]);

	useEffect(() => {
		hasScrolledToHighlightedKitRef.current = false;
		setActiveHighlightedKitId(null);

		if (highlightTimeoutRef.current) {
			window.clearTimeout(highlightTimeoutRef.current);
			highlightTimeoutRef.current = null;
		}
	}, [profileUsername, highlightedKitId]);

	useEffect(() => {
		if (!highlightedKitId || loading || myKits.length === 0) {
			return undefined;
		}

		const matchingKit = myKits.find(
			(item) => String(item.id) === String(highlightedKitId),
		);
		if (!matchingKit || hasScrolledToHighlightedKitRef.current) {
			return undefined;
		}

		let frameId = window.requestAnimationFrame(() => {
			const element = document.getElementById(`profile-kit-${matchingKit.id}`);
			if (!element) return;

			hasScrolledToHighlightedKitRef.current = true;
			setActiveHighlightedKitId(String(matchingKit.id));
			element.scrollIntoView({
				behavior: "smooth",
				block: "center",
			});

			highlightTimeoutRef.current = window.setTimeout(() => {
				setActiveHighlightedKitId((currentId) =>
					currentId === String(matchingKit.id) ? null : currentId,
				);
				highlightTimeoutRef.current = null;
			}, 2800);
		});

		return () => {
			window.cancelAnimationFrame(frameId);
		};
	}, [highlightedKitId, loading, myKits]);

	useEffect(() => {
		return () => {
			if (highlightTimeoutRef.current) {
				window.clearTimeout(highlightTimeoutRef.current);
			}
		};
	}, []);

	if (!profileUsername)
		return <div className="text-center mt-5">{t("profile.loginRequired")}</div>;
	if (loading)
		return (
			<div className="text-center mt-5">
				<div className="spinner-border text-primary"></div>
			</div>
		);
	if (error)
		return <div className="text-center mt-5 text-danger">{error}</div>;

	const handleDeleteSuccess = (deletedKitId) => {
		setMyKits((prev) => prev.filter((item) => item.id !== deletedKitId));
		getUserStats(profileUsername).then(setStats);
	};

	const handleFollowToggle = async () => {
		if (!user) {
			alert(t("profile.authTitle"));
			return;
		}

		// Prevent multiple clicks while loading
		if (followLoading) return;
		setFollowLoading(true);

		// Optimistic UI Update (change UI before server response for better UX)
		const previousIsFollowing = isFollowing;
		const previousFollowersCount = followersCount;
		setIsFollowing(!isFollowing);
		setFollowersCount((prev) => (isFollowing ? prev - 1 : prev + 1));

		try {
			const data = await toggleFollowUser(profileUsername);
			// Server response will confirm the new state, but we already updated the UI optimistically
			setIsFollowing(data.is_following);
		} catch (err) {
			console.error("Error while following", err);
			// Rollback, if the server returns an error
			setIsFollowing(previousIsFollowing);
			setFollowersCount(previousFollowersCount);
		} finally {
			setFollowLoading(false);
		}
	};

	// Function to open followers/following modal and load data
	const openFollowModal = async (type) => {
		setModalType(type);
		setModalLoading(true);
		setModalUsers([]); // Clear previous data

		try {
			if (type === "followers") {
				const data = await getFollowersList(profileUsername);
				setModalUsers(data);
			} else if (type === "following") {
				const data = await getFollowingList(profileUsername);
				setModalUsers(data);
			}
		} catch (err) {
			console.error("Failed to load list", err);
		} finally {
			setModalLoading(false);
		}
	};

	const closeFollowModal = () => {
		setModalType(null);
	};

	const modalTitle =
		modalType === "followers"
			? t("profile.followers")
			: modalType === "following"
				? t("profile.following")
				: "";

	const handleMessageClick = async () => {
		if (!user) {
			Swal.fire({
				title: t("profile.authTitle"),
				text: t("profile.authText"),
				icon: "info",
				confirmButtonColor: "#3085d6",
				confirmButtonText: t("common.ok"),
			});
			return;
		}

		try {
			const conversation = await startConversation({
				username: profileUsername,
			});
			navigate(`/messages/${conversation.id}`);
		} catch (error) {
			console.error("Failed to start conversation", error);
			const message =
				error?.response?.data?.non_field_errors?.[0] ||
				error?.response?.data?.username?.[0] ||
				t("profile.messageError");
			Swal.fire(t("common.error"), message, "error");
		}
	};

	return (
		<div className="container py-5 px-3 px-md-1">
			{/* Profile headline */}
			<div className="container bg-white p-4 rounded shadow-sm mb-5 profile-header-card">
				<div className="d-flex flex-column flex-lg-row justify-content-between align-items-center gap-4 profile-header-layout">
					<div className="d-flex align-items-center gap-4 profile-identity-block">
						{/* Profile avatar */}
						<UserAvatar user={profileData} size={80} />
						<div
							className="d-flex flex-column justify-content-center profile-name-block"
							style={{ minHeight: "80px" }}
						>
							<div className="d-flex align-items-center gap-1 flex-wrap profile-name-row">
								{/* Username and edit button */}
								<h2 className="fw-bold mb-0 profile-username">
									{profileUsername}
								</h2>

								{/* Badges for Pro/Mod */}
								{profileData?.is_moderator && (
									<span
										className="justify-content-center align-items-center d-flex ms-1"
										title="Moderator"
									>
										<ShieldIcon className="shield-icon" />
									</span>
								)}

								{profileData?.is_pro && (
									<a
										className="justify-content-center align-items-center d-flex ms-1"
										title="Pro Member"
										href="/get-pro"
										target="_blank"
										rel="noopener noreferrer"
									>
										<DiamondIcon className="diamond-icon" />
									</a>
								)}

								{/* Favorite Team */}
								{/* {profileData?.favorite_team_info && (
									<div
										className="d-flex align-items-center gap-1 ms-2"
										title={`${profileData.favorite_team_info.name} Fan`}
									>
										<img
											src={
												profileData.favorite_team_info
													.logo
											}
											alt="logo"
											style={{ height: "32px" }}
										/>
									</div>
								)} */}

								{/* Edit Button OR Follow Button */}
								{isOwner ? (
									<Link
										to="/profile/edit"
										className="edit-button profile-edit-button"
										title={t("profile.editProfile")}
									>
										✏️
									</Link>
								) : null}
							</div>

							<div className="d-flex align-items-center gap-1 flex-wrap profile-meta-row">
								{/* Name & Surname */}
								{(profileData?.name ||
									profileData?.surname) && (
									<>
										{/* Country */}
										{profileData?.country_info && (
											<div
												className="d-flex align-items-center gap-1 ms-1"
												title={
													localizeCountryName(
														profileData.country_info.name,
														t,
													)
												}
											>
												<img
													className="rounded"
													src={
														profileData.country_info
															.flag
													}
													alt="flag"
													style={{
														height: "16px",
													}}
												/>
											</div>
										)}
										<p className="text-muted mb-0 small">
											{profileData.name}{" "}
											{profileData.surname}
										</p>
									</>
								)}
							</div>

							{!isOwner ? (
								<div className="d-flex align-items-center gap-2 profile-actions">
									<button
										onClick={handleFollowToggle}
										disabled={followLoading}
										className={`btn btn-sm rounded-pill px-3 fw-bold profile-action-button ${
											isFollowing
												? "btn-outline-secondary"
												: "btn-primary"
										}`}
									>
										{isFollowing ? (
											<>
												<i className="bi bi-person-dash-fill me-1"></i>{" "}
												{t("profile.unfollow")}
											</>
										) : (
											<>
												<i className="bi bi-person-plus-fill me-1"></i>{" "}
												{t("profile.follow")}
											</>
										)}
									</button>
									<button
										type="button"
										onClick={handleMessageClick}
										className="btn btn-sm btn-outline-dark rounded-pill px-3 fw-semibold profile-action-button"
									>
										<i className="bi bi-chat-dots me-1"></i>
										{t("profile.message")}
									</button>
								</div>
							) : null}

							<div className="d-flex align-items-center gap-3 mt-2 small text-secondary profile-secondary-row"></div>
						</div>
					</div>
					<div className="text-end profile-stats-panel">
						{/* Row 1*/}
						<div className="d-flex justify-content-end gap-4 profile-stats-grid">
							{/* Followers */}
							<div
								className="text-center cursor-pointer profile-stat-card"
								title={t("profile.seeFollowers")}
								onClick={() => openFollowModal("followers")}
								style={{
									cursor: "pointer",
									transition: "opacity 0.2s",
								}}
								onMouseEnter={(e) =>
									(e.currentTarget.style.opacity = "0.7")
								}
								onMouseLeave={(e) =>
									(e.currentTarget.style.opacity = "1")
								}
							>
								<div className="d-flex justify-content-center align-items-center gap-2">
									<FollowersIcon className="followers-icon" />
									<h4 className="text-dark fw-bold mb-0">
										{followersCount}
									</h4>
								</div>
								<span className="small text-muted d-block">
									{t("profile.followers")}
								</span>
							</div>

							{/* Following */}
							<div
								className="text-center cursor-pointer profile-stat-card"
								title={t("profile.seeFollowing")}
								onClick={() => openFollowModal("following")}
								style={{
									cursor: "pointer",
									transition: "opacity 0.2s",
								}}
								onMouseEnter={(e) =>
									(e.currentTarget.style.opacity = "0.7")
								}
								onMouseLeave={(e) =>
									(e.currentTarget.style.opacity = "1")
								}
							>
								<div className="d-flex justify-content-center align-items-center gap-2">
									<FollowingIcon className="following-icon" />
									<h4 className="text-dark fw-bold mb-0">
										{followingCount}
									</h4>
								</div>
								<span className="small text-muted d-block">
									{t("profile.following")}
								</span>
							</div>

							{/* Kits */}
							<div
								className="text-center profile-stat-card"
								title={t("profile.kitsTitle")}
							>
								<div className="d-flex justify-content-center align-items-center gap-2">
									<ShirtIcon className="shirt-icon" />
									<h4 className="text-primary fw-bold mb-0">
										{stats.total_kits}
									</h4>
								</div>
								<span className="small text-muted d-block">
									{t("profile.kitsInCollection")}
								</span>
							</div>
							{/* Total Value */}
							<div
								className={`text-center profile-stat-card ${isOwner ? "profile-stat-card-clickable" : ""}`}
								title={t("profile.totalValueTitle")}
								onClick={isOwner ? () => setIsValueHistoryOpen(true) : undefined}
							>
								<div className="d-flex justify-content-center align-items-center gap-2">
									<MoneyBagIcon className="money-bag-icon" />
									<h4 className="text-success fw-bold mb-0">
										$
										{Number(
											stats.total_value,
										).toLocaleString(undefined, {
											maximumFractionDigits: 0,
										})}
									</h4>
								</div>
								<span className="small text-muted d-block">
									{t("profile.totalValue")}
								</span>
							</div>
						</div>

						{/* Row 2 */}
						<div className="mt-2"></div>
					</div>
				</div>

				<div className={`details-wrapper ${isExpanded ? "open" : ""}`}>
					<div className="mt-4 fade-in-animation">
						<hr className="my-4 text-muted opacity-25" />

						{/* --- MIDDLE SECTION: 2 Rows Layout --- */}
						<div className="d-flex flex-column gap-5">
							{" "}
							{/* --- ROW 1: Bio (Left) and Contact (Right) --- */}
							<div className="row gx-5">
								{/* LEFT: BIO */}
								<div className="col-lg-7">
									<h6
										className="fw-bold text-uppercase small text-muted mb-3"
										style={{ letterSpacing: "0.5px" }}
									>
										{t("profile.about")}
									</h6>
									{profileData?.bio ? (
										<p
											className="text-secondary lh-lg mb-0"
											style={{ whiteSpace: "pre-line" }}
										>
											{profileData.bio}
										</p>
									) : (
										<p className="text-muted fst-italic small">
											{t("profile.noBioProvided")}
										</p>
									)}
								</div>

								{/* RIGHT: CONTACT */}
								<div className="col-lg-5 mt-4 mt-lg-0">
									{" "}
									{profileData?.contact_email ||
									profileData?.website_link ? (
										<>
											<h6
												className="fw-bold text-uppercase small text-muted mb-3"
												style={{
													letterSpacing: "0.5px",
												}}
											>
												{t("profile.contact")}
											</h6>
											<div className="d-flex flex-column gap-3">
												{profileData.website_link && (
													<div className="d-flex align-items-center gap-2">
														<div
															className="bg-light rounded-circle d-flex align-items-center justify-content-center"
															style={{
																width: "32px",
																height: "32px",
															}}
														>
															<i className="bi bi-globe text-muted"></i>
														</div>
														<a
															href={
																profileData.website_link
															}
															target="_blank"
															rel="noopener noreferrer"
															className="breadcrumb-link text-muted"
															title={t("profile.website")}
														>
															{profileData.website_link.replace(
																/^https?:\/\//,
																"",
															)}
														</a>
													</div>
												)}

												{profileData.contact_email && (
													<div className="d-flex align-items-center gap-2">
														<div
															className="bg-light rounded-circle d-flex align-items-center justify-content-center"
															style={{
																width: "32px",
																height: "32px",
															}}
														>
															<i className="bi bi-envelope text-muted"></i>
														</div>
														{showEmail ? (
															<span className="text-muted">
																{
																	profileData.contact_email
																}
															</span>
														) : (
															<span
																className="email-hidden d-flex align-items-center cursor-pointer"
																onMouseEnter={() =>
																	setHover(
																		true,
																	)
																}
																onMouseLeave={() =>
																	setHover(
																		false,
																	)
																}
															>
																<span className="text-muted">
																	{t("profile.emailHidden")}
																</span>

																<span
																	className="ms-2 eye-clickable"
																	onClick={() =>
																		setShowEmail(
																			true,
																		)
																	}
																	title={t("profile.showEmail")}
																>
																	{hover ? (
																		<EyeOpenIcon className="eye-icon" />
																	) : (
																		<EyeCloseIcon className="eye-icon" />
																	)}
																</span>
															</span>
														)}
													</div>
												)}
											</div>
										</>
									) : (
										<div className="d-none d-lg-block"></div>
									)}
								</div>
							</div>
							<div className="row gx-5">
								{/* LEFT SHOPS */}
								<div className="col-lg-7">
									{(profileData?.vinted_link ||
										profileData?.ebay_link ||
										profileData?.depop_link) && (
										<>
											<h6
												className="fw-bold text-uppercase small text-muted mb-3"
												style={{
													letterSpacing: "0.5px",
												}}
											>
												{t("profile.myShops")}
											</h6>
											<div className="d-flex flex-wrap profile-market-links">
												<MarketBadge
													url={
														profileData.vinted_link
													}
													icon="bi-tag-fill"
													label="Vinted"
													hoverColor="#09B1BA"
												/>
												<MarketBadge
													url={profileData.depop_link}
													icon="bi-bag-fill"
													label="Depop"
													hoverColor="#FF0000"
												/>
												<MarketBadge
													url={profileData.ebay_link}
													icon="bi-shop"
													label="eBay"
													hoverColor="#0064D2"
												/>
											</div>
										</>
									)}
								</div>

								{/* RIGHT: SOCIALS */}
								<div className="col-lg-5 mt-4 mt-lg-0">
									{(profileData?.instagram_link ||
										profileData?.twitter_link ||
										profileData?.tiktok_link ||
										profileData?.youTube_link ||
										profileData?.facebook_link) && (
										<>
											<h6
												className="fw-bold text-uppercase small text-muted mb-3"
												style={{
													letterSpacing: "0.5px",
												}}
											>
												{t("profile.findMe")}
											</h6>
											<div className="d-flex gap-3 flex-wrap profile-social-links">
												<SocialLink
													url={
														profileData.instagram_link
													}
													icon="bi-instagram"
													color="#E1306C"
													title="Instagram"
												/>
												<SocialLink
													url={
														profileData.twitter_link
													}
													icon="bi-twitter-x"
													color="#000"
													title="X"
												/>
												<SocialLink
													url={
														profileData.tiktok_link
													}
													icon="bi-tiktok"
													color="#000"
													title="TikTok"
												/>
												<SocialLink
													url={
														profileData.youTube_link
													}
													icon="bi-youtube"
													color="#FF0000"
													title="YouTube"
												/>
												<SocialLink
													url={
														profileData.facebook_link
													}
													icon="bi-facebook"
													color="#1877F2"
													title="Facebook"
												/>
											</div>
										</>
									)}
								</div>
							</div>
						</div>
					</div>
				</div>

				{/* Expanding button  - Turned off right now*/}
				<div className="d-flex justify-content-center mt-3 d-none">
					<button
						className="btn btn-sm btn-light border rounded-pill px-4 py-1 text-muted d-flex align-items-center gap-2 shadow-sm"
						onClick={() => setIsExpanded(!isExpanded)}
						style={{ fontSize: "0.85rem" }}
					>
						{isExpanded ? (
							<>
								<span>{t("profile.showLess")}</span>
								<i className="bi bi-chevron-up"></i>
							</>
						) : (
							<>
								<span>{t("profile.showDetails")}</span>
								<i className="bi bi-chevron-down"></i>
							</>
						)}
					</button>
				</div>
			</div>

			{/* Add Kit Button */}
			{isOwner && (
				<div className="d-flex justify-content-center my-5">
					<Link to="/add-kit" className="add-ghost">
						{t("profile.addKit")}
					</Link>
				</div>
			)}

			{/* Shirt list */}
			{loading ? (
				<div className="text-center">
					<div className="spinner-border text-primary"></div>
				</div>
			) : (
				<div className="row g-4 profile-kits-grid">
					{myKits.map((item) => (
						<div
							key={item.id}
							id={`profile-kit-${item.id}`}
							className={`col-12 col-sm-12 col-md-12 col-lg-6 col-xl-4 col-xxl-3 profile-kit-cell ${String(item.id) === activeHighlightedKitId ? "profile-kit-highlight" : ""}`}
						>
								<KitCard
									item={item}
									onDeleteSuccess={handleDeleteSuccess}
									user={user}
									hideViewOnProfile
								/>
						</div>
					))}

					{myKits.length === 0 && (
						<div className="text-center text-muted py-5 w-100">
							<p>
								{isOwner ? t("profile.noKitsOwner") : t("profile.noKitsOther")}
							</p>
						</div>
					)}
				</div>
			)}

			{/* Followers/Following Modal */}
			<UserListModal
				isOpen={modalType !== null}
				onClose={closeFollowModal}
				title={modalTitle}
				kind={modalType || ""}
				users={modalUsers}
				loading={modalLoading}
			/>
			{isOwner ? (
				<CollectionValueChartModal
					isOpen={isValueHistoryOpen}
					onClose={() => setIsValueHistoryOpen(false)}
				/>
			) : null}
		</div>
	);
};

export default ProfilePage;
