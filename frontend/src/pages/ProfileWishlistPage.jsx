import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import WishlistSection from "../components/profile/WishlistSection";
import { getUserStats, getUserWishlist } from "../services/api";

const ProfileWishlistPage = ({ user }) => {
	const { t } = useTranslation();
	const { username } = useParams();
	const isOwner = user?.username === username;
	const pageTitle = t("wishlist.pageTitle", { username });

	const [profileData, setProfileData] = useState(null);
	const [wishlistItems, setWishlistItems] = useState([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() => {
		if (!username) {
			return;
		}

		let cancelled = false;
		setLoading(true);
		setError("");

		Promise.all([getUserStats(username), getUserWishlist(username)])
			.then(([statsData, wishlistData]) => {
				if (cancelled) {
					return;
				}
				setProfileData(statsData);
				setWishlistItems(Array.isArray(wishlistData) ? wishlistData : []);
			})
			.catch((loadError) => {
				if (cancelled) {
					return;
				}
				console.error("Failed to load wishlist page", loadError);
				setError(t("wishlist.loadError"));
			})
			.finally(() => {
				if (!cancelled) {
					setLoading(false);
				}
			});

		return () => {
			cancelled = true;
		};
	}, [t, username]);

	const handleRemoveSuccess = (removedItemId) => {
		setWishlistItems((previousItems) =>
			previousItems.filter((item) => item.id !== removedItemId),
		);
	};

	if (loading) {
		return (
			<div className="container py-5">
				<div className="text-center py-5">
					<div className="spinner-border text-primary" role="status" />
				</div>
			</div>
		);
	}

	if (error) {
		return (
			<div className="container py-5">
				<div className="alert alert-danger text-center mb-0">{error}</div>
			</div>
		);
	}

	return (
		<div className="container py-5 px-3 px-md-1">
			<div className="container bg-white p-4 rounded shadow-sm profile-header-card">
				<Link
					to={`/profile/${username}`}
					className="btn btn-link px-0 text-decoration-none text-muted mb-2"
				>
					<i className="bi bi-arrow-left me-2"></i>
					{t("wishlist.backToProfile")}
				</Link>

				<WishlistSection
					items={wishlistItems}
					isOwner={isOwner}
					isPro={Boolean(profileData?.is_pro)}
					heading={pageTitle}
					onRemoveSuccess={handleRemoveSuccess}
				/>
			</div>
		</div>
	);
};

export default ProfileWishlistPage;
