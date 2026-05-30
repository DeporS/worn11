export function formatLikedByText({ count, isLiked, username }) {
	const safeCount = Number.isFinite(Number(count))
		? Math.max(0, Number(count))
		: 0;

	if (safeCount === 0) {
		return "Be the first to like this kit";
	}

	if (isLiked) {
		if (safeCount === 1) {
			return "You liked this kit";
		}

		const others = safeCount - 1;
		return `You and ${others} ${others === 1 ? "other" : "others"} liked this kit`;
	}

	if (username) {
		if (safeCount === 1) {
			return `${username} liked this kit`;
		}

		const others = safeCount - 1;
		return `${username} and ${others} ${others === 1 ? "other" : "others"} liked this kit`;
	}

	return safeCount === 1
		? "1 person liked this kit"
		: `${safeCount} people liked this kit`;
}
