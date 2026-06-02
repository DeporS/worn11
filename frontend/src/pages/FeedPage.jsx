import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import CommentsModal from "../components/comments/CommentsModal";
import FeedItemCard from "../components/feed/FeedItemCard";
import { getFollowingFeed } from "../services/api";

const FEED_PAGE_SIZE = 20;

const mergeFeedItems = (existingItems, incomingItems) => {
	const seenIds = new Set(existingItems.map((item) => item.id));
	return [
		...existingItems,
		...incomingItems.filter((item) => !seenIds.has(item.id)),
	];
};

const FeedPage = ({ user }) => {
	const { t } = useTranslation();
	const [items, setItems] = useState([]);
	const [hasMore, setHasMore] = useState(false);
	const [loading, setLoading] = useState(false);
	const [loadingMore, setLoadingMore] = useState(false);
	const [error, setError] = useState("");
	const [selectedKit, setSelectedKit] = useState(null);
	const [selectedImageIndex, setSelectedImageIndex] = useState(0);

	useEffect(() => {
		if (!user) {
			setItems([]);
			setHasMore(false);
			setLoading(false);
			setLoadingMore(false);
			setError("");
			return;
		}

		let cancelled = false;

		const loadFeed = async () => {
			setLoading(true);
			setError("");

			try {
				const data = await getFollowingFeed({ limit: FEED_PAGE_SIZE });
				if (cancelled) return;

				setItems(Array.isArray(data?.results) ? data.results : []);
				setHasMore(Boolean(data?.has_more));
			} catch (loadError) {
				if (cancelled) return;
				console.error("Failed to load following feed", loadError);
				setError(t("feed.loadError"));
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		};

		loadFeed();

		return () => {
			cancelled = true;
		};
	}, [user, t]);

	const handleLoadMore = async () => {
		if (!user || loadingMore || !hasMore || items.length === 0) {
			return;
		}

		const oldestItemId = items[items.length - 1]?.id;
		if (!oldestItemId) return;

		try {
			setLoadingMore(true);
			setError("");

			const data = await getFollowingFeed({
				limit: FEED_PAGE_SIZE,
				before: oldestItemId,
			});

			setItems((previousItems) =>
				mergeFeedItems(
					previousItems,
					Array.isArray(data?.results) ? data.results : [],
				),
			);
			setHasMore(Boolean(data?.has_more));
		} catch (loadError) {
			console.error("Failed to load more feed items", loadError);
			setError(t("feed.loadError"));
		} finally {
			setLoadingMore(false);
		}
	};

	const handleOpenKit = (kitItem, imageIndex = 0) => {
		setSelectedKit(kitItem);
		setSelectedImageIndex(imageIndex);
	};

	const handleCloseKit = () => {
		setSelectedKit(null);
		setSelectedImageIndex(0);
	};

	return (
		<div className="container py-5">
			<div className="mx-auto" style={{ maxWidth: "800px" }}>
				<div className="mb-4">
					<h1 className="display-6 fw-bold mb-2">
						{t("feed.title")}
					</h1>
				</div>

				{!user ? (
					<div className="card border-0 shadow-sm rounded-4">
						<div className="card-body text-center py-5">
							<p className="mb-0 text-muted">
								{t("feed.loginRequired")}
							</p>
						</div>
					</div>
				) : loading ? (
					<div className="text-center py-5">
						<div
							className="spinner-border text-primary mb-3"
							role="status"
						>
							<span className="visually-hidden">
								{t("feed.loading")}
							</span>
						</div>
						<div className="text-muted">{t("feed.loading")}</div>
					</div>
				) : error ? (
					<div className="alert alert-danger">{error}</div>
				) : items.length === 0 ? (
					<div className="card border-0 shadow-sm rounded-4">
						<div className="card-body text-center py-5">
							<p className="mb-0 text-muted">{t("feed.empty")}</p>
						</div>
					</div>
				) : (
					<>
						<div className="d-flex flex-column gap-4">
							{items.map((item) => (
								<FeedItemCard
									key={item.id}
									item={item}
									onOpenKit={handleOpenKit}
								/>
							))}
						</div>

						{hasMore ? (
							<div className="text-center mt-4">
								<button
									type="button"
									className="btn btn-outline-primary rounded-pill px-4"
									onClick={handleLoadMore}
									disabled={loadingMore}
								>
									{loadingMore
										? t("common.loading")
										: t("feed.loadMore")}
								</button>
							</div>
						) : null}
					</>
				)}
			</div>

			{selectedKit ? (
				<CommentsModal
					isOpen={Boolean(selectedKit)}
					onClose={handleCloseKit}
					kitId={selectedKit.id}
					currentUser={user}
					item={selectedKit}
					initialImageIndex={selectedImageIndex}
				/>
			) : null}
		</div>
	);
};

export default FeedPage;
