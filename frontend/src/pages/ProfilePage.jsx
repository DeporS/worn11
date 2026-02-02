import { useState, useEffect } from "react";
import { getUserCollection, getUserStats } from "../services/api";
import { Link, useParams } from "react-router-dom";
import KitCard from "../components/profile/KitCard";
import SocialLink from "../components/profile/SocialLink";
import MarketBadge from "../components/profile/MarketBadge";
import UserAvatar from "../components/UserAvatar";

import "../styles/profile.css";

import EyeCloseIcon from "../assets/icons/eye-close.svg?react";
import EyeOpenIcon from "../assets/icons/eye-open.svg?react";
import DiamondIcon from "../assets/icons/diamond-blue.svg?react";
import ShieldIcon from "../assets/icons/shield-2.svg?react";
import ShirtIcon from "../assets/icons/shirt.svg?react";
import MoneyBagIcon from "../assets/icons/money-bag.svg?react";

const ProfilePage = ({ user }) => {
	const { username } = useParams(); // Get username from URL params
	const profileUsername = username || user?.username;
	const isOwner = user?.username === profileUsername; // Check if viewing own profile

	const [myKits, setMyKits] = useState([]);
	const [stats, setStats] = useState({ total_value: 0, total_kits: 0 });
	const [profileData, setProfileData] = useState(null);

	const [showEmail, setShowEmail] = useState(false); // For toggling email visibility
	const [isExpanded, setIsExpanded] = useState(false); // For bio expansion

	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

	const [hover, setHover] = useState(false);

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
			})
			.catch((err) => {
				console.error("Failed to load profile", err);
				setError("User not found or error loading data.");
			})
			.finally(() => setLoading(false));
	}, [profileUsername, user?.username]);

	if (!profileUsername)
		return <div className="text-center mt-5">Please log in.</div>;
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

	return (
		<div className="container py-5 px-3 px-md-1">
			{/* Profile headline */}
			<div className="container bg-white p-4 rounded shadow-sm mb-5">
				<div className="d-flex justify-content-between align-items-center">
					<div className="d-flex align-items-center gap-4">
						{/* Profile avatar */}
						<UserAvatar user={profileData} size={80} />
						<div
							className="d-flex flex-column justify-content-center"
							style={{ minHeight: "80px" }}
						>
							<div className="d-flex align-items-center gap-1">
								{/* Username and edit button */}
								<h2 className="fw-bold mb-0">
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

								{isOwner && (
									<Link
										to="/profile/edit"
										className="edit-button"
										title="Edit Profile"
									>
										✏️
									</Link>
								)}
							</div>

							<div className="d-flex align-items-center gap-1">
								{/* Country */}
								{profileData?.country_info && (
									<div
										className="d-flex align-items-center gap-1 ms-1"
										title={profileData.country_info.name}
									>
										<img
											className="rounded"
											src={profileData.country_info.flag}
											alt="flag"
											style={{
												height: "16px",
											}}
										/>
									</div>
								)}
								{/* Name & Surname */}
								{(profileData?.name ||
									profileData?.surname) && (
									<>
										<p className="text-muted mb-0 small">
											{profileData.name}{" "}
											{profileData.surname}
										</p>
									</>
								)}
							</div>

							<div className="d-flex align-items-center gap-3 mt-2 small text-secondary"></div>
						</div>
					</div>
					<div className="text-end">
						{/* Row 1*/}
						<div className="d-flex justify-content-end gap-4">
							<div
								className="text-center"
								title="Kits in collection"
							>
								<div className="d-flex justify-content-center align-items-center gap-2">
									<ShirtIcon className="shirt-icon" />
									<h4 className="text-primary fw-bold mb-0">
										{stats.total_kits}
									</h4>
								</div>
								<span className="small text-muted d-block">
									Kits in collection
								</span>
							</div>

							<div className="text-center" title="Total Value">
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
									Total Value
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
										About
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
											No bio provided.
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
												Contact
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
															title="Website"
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
																	Email hidden
																</span>

																<span
																	className="ms-2 eye-clickable"
																	onClick={() =>
																		setShowEmail(
																			true,
																		)
																	}
																	title="Show Email"
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
												My Shops
											</h6>
											<div className="d-flex flex-wrap">
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
												Find me
											</h6>
											<div className="d-flex gap-3 flex-wrap">
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

				{/* Expanding button */}
				<div className="d-flex justify-content-center mt-3">
					<button
						className="btn btn-sm btn-light border rounded-pill px-4 py-1 text-muted d-flex align-items-center gap-2 shadow-sm"
						onClick={() => setIsExpanded(!isExpanded)}
						style={{ fontSize: "0.85rem" }}
					>
						{isExpanded ? (
							<>
								<span>Show Less</span>
								<i className="bi bi-chevron-up"></i>{" "}
							</>
						) : (
							<>
								<span>Show Details</span>
								<i className="bi bi-chevron-down"></i>{" "}
							</>
						)}
					</button>
				</div>
			</div>

			{/* Add Kit Button */}
			{isOwner && (
				<div className="d-flex justify-content-center my-5">
					<Link to="/add-kit" className="add-ghost">
						+ Add kit
					</Link>
				</div>
			)}

			{/* Shirt list */}
			{loading ? (
				<div className="text-center">
					<div className="spinner-border text-primary"></div>
				</div>
			) : (
				<div className="row g-4">
					{myKits.map((item) => (
						<div
							key={item.id}
							className="col-12 col-sm-12 col-md-12 col-lg-6 col-xl-6 col-xxl-4 col-xxl-4"
						>
							<KitCard
								item={item}
								onDeleteSuccess={handleDeleteSuccess}
								user={user}
							/>
						</div>
					))}

					{myKits.length === 0 && (
						<div className="text-center text-muted py-5 w-100">
							<p>
								{isOwner ? "You don't" : "This user doesn't"}{" "}
								have any kits yet.
							</p>
						</div>
					)}
				</div>
			)}
		</div>
	);
};

export default ProfilePage;
