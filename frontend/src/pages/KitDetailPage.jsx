import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import CommentsModal from "../components/comments/CommentsModal";
import { getKitDetail } from "../services/api";

const KitDetailPage = ({ user }) => {
	const { username, kitId } = useParams();
	const navigate = useNavigate();
	const [kit, setKit] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() => {
		let cancelled = false;

		const loadKit = async () => {
			setLoading(true);
			setError("");

			try {
				const data = await getKitDetail(kitId);
				if (cancelled) return;

				const ownerUsername = data.owner_username;
				if (ownerUsername && ownerUsername !== username) {
					navigate(`/profile/${ownerUsername}/kits/${data.id}`, { replace: true });
					return;
				}

				setKit(data);
			} catch (loadError) {
				if (cancelled) return;
				console.error("Failed to load kit detail", loadError);
				setError("Kit not found.");
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		};

		loadKit();

		return () => {
			cancelled = true;
		};
	}, [kitId, navigate, username]);

	const handleClose = () => {
		const ownerUsername = kit?.owner_username || username;
		navigate(`/profile/${ownerUsername}`);
	};

	return (
		<div className="container py-5">
			{loading ? (
				<div className="text-center py-5">
					<div className="spinner-border text-primary" role="status">
						<span className="visually-hidden">Loading...</span>
					</div>
				</div>
			) : error ? (
				<div className="text-center py-5">
					<h1 className="h4 fw-bold mb-2">Kit not found</h1>
					<p className="text-muted mb-4">
						This kit may have been removed or the link is incorrect.
					</p>
					<Link to={`/profile/${username}`} className="btn btn-outline-secondary rounded-pill">
						Back to profile
					</Link>
				</div>
			) : (
				<CommentsModal
					isOpen={Boolean(kit)}
					onClose={handleClose}
					kitId={kit.id}
					currentUser={user}
					item={kit}
					initialImageIndex={0}
				/>
			)}
		</div>
	);
};

export default KitDetailPage;
