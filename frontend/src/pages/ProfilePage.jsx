import { useState, useEffect } from "react";
import { getUserCollection, getUserStats } from "../services/api";
import { Link, useParams } from "react-router-dom";
import KitCard from "../components/KitCard";
import UserAvatar from "../components/UserAvatar";

import "../styles/profile.css";

const ProfilePage = ({ user }) => {
	const { username } = useParams(); // Get username from URL params
	const profileUsername = username || user?.username;
	const isOwner = user?.username === profileUsername; // Check if viewing own profile

	const [myKits, setMyKits] = useState([]);
	const [stats, setStats] = useState({ total_value: 0, total_kits: 0 });
	const [profileData, setProfileData] = useState(null);

	const [showEmail, setShowEmail] = useState(false); // For toggling email visibility

	const [loading, setLoading] = useState(true);
	const [error, setError] = useState(null);

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

	// Pomocniczy komponent do ikonek social media
	const SocialLink = ({ url, icon, color, title }) => {
		if (!url) return null;
		return (
			<a
				href={url}
				target="_blank"
				rel="noopener noreferrer"
				className="text-decoration-none me-3"
				style={{
					fontSize: "1.5rem",
					color: color || "#333",
					transition: "transform 0.2s",
				}}
				onMouseOver={(e) =>
					(e.currentTarget.style.transform = "scale(1.2)")
				}
				onMouseOut={(e) =>
					(e.currentTarget.style.transform = "scale(1)")
				}
				title={title}
			>
				<i className={`bi ${icon}`}></i>
			</a>
		);
	};

	// Pomocniczy komponent do Marketplace (Vinted, eBay) - wyglądają jak przyciski
	const MarketBadge = ({ url, icon, label, colorClass }) => {
		if (!url) return null;
		return (
			<a
				href={url}
				target="_blank"
				rel="noopener noreferrer"
				className={`btn btn-sm ${colorClass} me-2 mb-2 d-inline-flex align-items-center gap-1`}
				style={{ borderRadius: "20px", padding: "5px 15px" }}
			>
				<i className={`bi ${icon}`}></i> {label}
			</a>
		);
	};

	return (
		<div className="container py-5 px-3 px-md-1">
			{/* Profile headline */}
			<div className="container bg-white p-4 rounded shadow-sm mb-5">
				<div className="d-flex justify-content-between align-items-center">
					<div className="d-flex align-items-center gap-4">
						{/* Profile avatar */}
						<UserAvatar user={profileData} size={80} />
						<div>
							<div className="d-flex align-items-center gap-1">
								{/* Username and edit button */}
								<h2 className="fw-bold mb-0">
									{profileUsername}
								</h2>
								{isOwner && (
									<Link
										to="/profile/edit"
										className="btn edit-button"
										title="Edit Profile"
									>
										✏️
									</Link>
								)}
								{/* Badges for Pro/Mod */}
								{profileData?.is_pro && (
									<span className="badge bg-warning text-dark">
										PRO
									</span>
								)}
								{profileData?.is_moderator && (
									<span className="badge bg-info text-white">
										MOD
									</span>
								)}
							</div>

							{/* Name & Surname */}
							{(profileData?.name || profileData?.surname) && (
								<p className="text-muted mb-0 small">
									{profileData.name} {profileData.surname}
								</p>
							)}

							{/* Location & Team & Size EDITTTTTTTTTTTTTTTTTTT */}
							<div className="d-flex align-items-center gap-3 mt-2 small text-secondary">
								{profileData?.country_info ? (
									<div
										className="d-flex align-items-center gap-1"
										title="Country"
									>
										<img
											src={profileData.country_info.flag}
											alt="flag"
											style={{ width: "20px" }}
										/>
										{profileData.country_info.name}
									</div>
								) : profileData?.country ? (
									<span>
										🌍 Country: {profileData.country}
									</span>
								) : null}

								{profileData?.favorite_team_info && (
									<div
										className="d-flex align-items-center gap-1"
										title="Favorite Team"
									>
										⚽ {profileData.favorite_team_info.name}
									</div>
								)}

								{profileData?.preferred_size && (
									<span className="badge bg-light text-dark border">
										Size: {profileData.preferred_size}
									</span>
								)}
							</div>
						</div>
					</div>
					<div className="text-end">
						<h3 className="text-primary fw-bold mb-0">
							{stats.total_kits}
						</h3>
						<span className="small text-muted d-block">
							Kits in collection
						</span>

						<h4 className="text-success fw-bold mb-0 mt-2">
							${stats.total_value.toLocaleString()}
						</h4>
						<span className="small text-muted">Total Value</span>
					</div>
				</div>
				<hr className="my-4 text-muted opacity-25" />

				{/* Middle Row: Bio & Socials & Contact */}
				<div className="row">
					<div className="col-lg-7">
						{/* BIO */}
						{profileData?.bio && (
							<div className="mb-4">
								<h6 className="fw-bold text-uppercase small text-muted">
									About
								</h6>
								<p
									className="text-secondary"
									style={{ whiteSpace: "pre-line" }}
								>
									{profileData.bio}
								</p>
							</div>
						)}

						{/* MARKETPLACES (Vinted, eBay, Depop) */}
						{(profileData?.vinted_link ||
							profileData?.ebay_link ||
							profileData?.depop_link) && (
							<div className="mb-4">
								<h6 className="fw-bold text-uppercase small text-muted mb-2">
									My Shops
								</h6>
								<div className="d-flex flex-wrap">
									<MarketBadge
										url={profileData.vinted_link}
										icon="bi-tag-fill"
										label="Vinted"
										colorClass="btn-info text-white"
									/>
									<MarketBadge
										url={profileData.depop_link}
										icon="bi-bag-fill"
										label="Depop"
										colorClass="btn-danger"
									/>
									<MarketBadge
										url={profileData.ebay_link}
										icon="bi-shop"
										label="eBay"
										colorClass="btn-outline-dark"
									/>
								</div>
							</div>
						)}
					</div>

					<div className="col-lg-5">
						{/* SOCIAL MEDIA */}
						{(profileData?.instagram_link ||
							profileData?.twitter_link ||
							profileData?.youTube_link ||
							profileData?.tiktok_link ||
							profileData?.facebook_link) && (
							<div className="mb-4">
								<h6 className="fw-bold text-uppercase small text-muted mb-2">
									Follow me
								</h6>
								<div className="d-flex align-items-center">
									<SocialLink
										url={profileData.instagram_link}
										icon="bi-instagram"
										color="#E1306C"
										title="Instagram"
									/>
									<SocialLink
										url={profileData.twitter_link}
										icon="bi-twitter-x"
										color="#000"
										title="X / Twitter"
									/>
									<SocialLink
										url={profileData.tiktok_link}
										icon="bi-tiktok"
										color="#000"
										title="TikTok"
									/>
									<SocialLink
										url={profileData.youTube_link}
										icon="bi-youtube"
										color="#FF0000"
										title="YouTube"
									/>
									<SocialLink
										url={profileData.facebook_link}
										icon="bi-facebook"
										color="#1877F2"
										title="Facebook"
									/>
								</div>
							</div>
						)}

						{/* CONTACT INFO (Email + Website) */}
						{(profileData?.contact_email ||
							profileData?.website_link) && (
							<div className="p-3 bg-light rounded small">
								<h6 className="fw-bold text-uppercase small text-muted mb-2">
									Contact
								</h6>

								{profileData.website_link && (
									<div className="mb-2">
										<i className="bi bi-globe me-2"></i>
										<a
											href={profileData.website_link}
											target="_blank"
											rel="noopener noreferrer"
											className="text-decoration-none fw-bold"
										>
											Visit Website
										</a>
									</div>
								)}

								{profileData.contact_email && (
									<div>
										<i className="bi bi-envelope me-2"></i>
										{showEmail ? (
											<a
												href={`mailto:${profileData.contact_email}`}
												className="fw-bold text-dark"
											>
												{profileData.contact_email}
											</a>
										) : (
											<span
												className="text-primary text-decoration-underline"
												style={{ cursor: "pointer" }}
												onClick={() =>
													setShowEmail(true)
												}
											>
												Show Email Address
											</span>
										)}
									</div>
								)}
							</div>
						)}
					</div>
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
