export function formatLikedByText({ count, isLiked, username }, t) {
	const safeCount = Number.isFinite(Number(count))
		? Math.max(0, Number(count))
		: 0;

	if (safeCount === 0) {
		return t("likes.beFirst");
	}

	if (isLiked) {
		if (safeCount === 1) {
			return t("likes.youLiked");
		}

		const others = safeCount - 1;
		return t(
			others === 1 ? "likes.youAndOthers_one" : "likes.youAndOthers_other",
			{ count: others },
		);
	}

	if (username) {
		if (safeCount === 1) {
			return t("likes.userLiked", { username });
		}

		const others = safeCount - 1;
		return t(
			others === 1 ? "likes.userAndOthers_one" : "likes.userAndOthers_other",
			{ username, count: others },
		);
	}

	return t(
		safeCount === 1 ? "likes.peopleLiked_one" : "likes.peopleLiked_other",
		{ count: safeCount },
	);
}
