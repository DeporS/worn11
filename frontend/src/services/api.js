import axios from "axios";

// Temporary API URL
const API_URL = "http://127.0.0.1:8000/api";

const api = axios.create({
	baseURL: API_URL,
	timeout: 5000, // Timeout after 5 seconds
});

const buildMultipartPayload = (payload) => {
	const formData = new FormData();
	Object.entries(payload || {}).forEach(([key, value]) => {
		if (value === undefined) return;
		if (value === null) {
			formData.append(key, "");
			return;
		}
		if (value instanceof File) {
			formData.append(key, value);
			return;
		}
		if (typeof value === "boolean") {
			formData.append(key, value ? "true" : "false");
			return;
		}
		formData.append(key, value);
	});
	return formData;
};

// INTERCEPTOR: Before each request, add the token
api.interceptors.request.use(
	(config) => {
		const token = localStorage.getItem("access_token");
		if (token) {
			config.headers.Authorization = `Bearer ${token}`;
		}
		return config;
	},
	(error) => Promise.reject(error),
);

// Helper function
export const getUserCollection = async (username) => {
	try {
		const response = await api.get(`/user-collection/${username}/`);
		return response.data;
	} catch (error) {
		// Rethrow the error so the component can handle it
		throw error;
	}
};

// Add a kit to the user's collection
export const addKitToCollection = async (formData) => {
	try {
		const response = await api.post("/my-collection/", formData, {
			headers: {
				"Content-Type": "multipart/form-data",
			},
		});
		return response.data;
	} catch (error) {
		throw error;
	}
};

// Delete a kit from the user's collection
export const deleteKitFromCollection = async (kitId) => {
	try {
		const response = await api.delete(`/my-collection/${kitId}/`);
		return response.data;
	} catch (error) {
		throw error;
	}
};

// Function to get user collection stats
export const getUserStats = async (username) => {
	try {
		const response = await api.get(`/user-stats/${username}/`);
		return response.data;
	} catch (error) {
		throw error;
	}
};

export const getMyCollectionValueHistory = async () => {
	const response = await api.get("/me/collection-value-history/");
	return response.data;
};

export const getMyWishlist = async () => {
	const response = await api.get("/me/wishlist/");
	return response.data;
};

export const getUserWishlist = async (username) => {
	const response = await api.get(`/users/${username}/wishlist/`);
	return response.data;
};

export const toggleWishlistItem = async ({
	teamId,
	season,
	kitType,
	sourceUserKitId,
}) => {
	const response = await api.post("/wishlist/toggle/", {
		team_id: teamId,
		season,
		kit_type: kitType,
		...(sourceUserKitId ? { source_userkit_id: sourceUserKitId } : {}),
	});
	return response.data;
};

export const removeWishlistItem = async (id) => {
	const response = await api.delete(`/wishlist/${id}/`);
	return response.data;
};

// Toggle follow/unfollow a user
export const toggleFollowUser = async (username) => {
	const response = await api.post(`/users/${username}/follow/`);
	return response.data;
};

// Search users by username
export const searchUsers = async (query) => {
	// Query example: /users/search/?q=messi
	const response = await api.get(`/users/search/?q=${query}`);
	return response.data;
};

export const searchKitSuggestions = async (query, limit = 8) => {
	const response = await api.get("/search/kits/", {
		params: {
			q: query,
			limit,
		},
	});
	return response.data;
};

export const getExploreKits = async (sort = "trending", limit = 24) => {
	const response = await api.get("/explore/kits/", {
		params: {
			sort,
			limit,
		},
	});
	return response.data;
};

export const getFollowingFeed = async ({ limit = 20, before } = {}) => {
	const response = await api.get("/feed/following/", {
		params: {
			limit,
			...(before ? { before } : {}),
		},
	});
	return response.data;
};

export const getConversations = async () => {
	const response = await api.get("/conversations/");
	return response.data;
};

export const startConversation = async (payload) => {
	const response = await api.post("/conversations/start/", payload);
	return response.data;
};

export const getConversation = async (conversationId) => {
	const response = await api.get(`/conversations/${conversationId}/`);
	return response.data;
};

export const getConversationMessages = async (
	conversationId,
	{ limit, before } = {},
) => {
	const response = await api.get(`/conversations/${conversationId}/messages/`, {
		params: {
			...(limit ? { limit } : {}),
			...(before ? { before } : {}),
		},
	});
	return response.data;
};

export const getUnreadMessagesCount = async () => {
	const response = await api.get("/conversations/unread-count/");
	return response.data;
};

export const getNotifications = async ({ limit = 20, before } = {}) => {
	const response = await api.get("/notifications/", {
		params: {
			limit,
			...(before ? { before } : {}),
		},
	});
	return response.data;
};

export const getNotificationsUnreadCount = async () => {
	const response = await api.get("/notifications/unread-count/");
	return response.data;
};

export const markNotificationsRead = async () => {
	const response = await api.post("/notifications/mark-read/");
	return response.data;
};

export const sendConversationMessage = async (conversationId, body) => {
	const response = await api.post(`/conversations/${conversationId}/messages/`, {
		body,
	});
	return response.data;
};

// Update user profile
export const updateUserProfile = async (formData) => {
	try {
		const response = await api.put("/profile/update/", formData, {
			headers: {
				"Content-Type": "multipart/form-data",
			},
		});
		return response.data;
	} catch (error) {
		throw error;
	}
};

// Toggle like on a kit
export const toggleLike = async (id) => {
	try {
		const response = await api.post(`/kits/${id}/like/`);
		return response.data;
	} catch (error) {
		throw error;
	}
};

// Get kit variants for a team and season
export const getKitVariants = async (teamIdentifier, season, type) => {
	const response = await api.get(
		`/kits/team/${teamIdentifier}/variants/?season=${encodeURIComponent(season)}&type=${encodeURIComponent(type)}`,
	);
	return response.data;
};

export const getApprovedTeamSeasonKitTypes = async (teamId) => {
	const response = await api.get(`/teams/${teamId}/approved-kit-types/`);
	return response.data;
};

export const resolveTeam = async (teamIdentifier) => {
	const response = await api.get(`/teams/${teamIdentifier}/resolve/`);
	return response.data;
};

// Get followers list for a user
export const getFollowersList = async (username) => {
	const response = await api.get(`/users/${username}/followers/`);
	return response.data.results || response.data;
};

// Get following list for a user
export const getFollowingList = async (username) => {
	const response = await api.get(`/users/${username}/following/`);
	return response.data.results || response.data;
};

// Get likers of a kit
export const getKitLikers = async (kitId) => {
	const response = await api.get(`/kits/${kitId}/likers/`);
	return response.data.results || response.data;
};

export const getKitDetail = async (kitId) => {
	const response = await api.get(`/kits/${kitId}/`);
	return response.data;
};

export const getRemovedKitDetail = async (kitId) => {
	const response = await api.get(`/my/removed-kits/${kitId}/`);
	return response.data;
};

export const getKitComments = async (kitId) => {
	const response = await api.get(`/kits/${kitId}/comments/`);
	return response.data;
};

export const addKitComment = async (kitId, body) => {
	const response = await api.post(`/kits/${kitId}/comments/`, { body });
	return response.data;
};

export const replyToComment = async (commentId, body) => {
	const response = await api.post(`/comments/${commentId}/reply/`, { body });
	return response.data;
};

export const toggleCommentLike = async (commentId) => {
	const response = await api.post(`/comments/${commentId}/like/`);
	return response.data;
};

export const deleteComment = async (commentId) => {
	const response = await api.delete(`/comments/${commentId}/`);
	return response.data;
};

export const reportKit = async (kitId, payload) => {
	const response = await api.post(`/kits/${kitId}/report/`, payload);
	return response.data;
};

export const getAdminKitTypeSuggestions = async () => {
	const response = await api.get("/admin/kit-type-suggestions/");
	return response.data;
};

export const getAdminKitTypeModerationActions = async (limit = 20) => {
	const response = await api.get("/admin/kit-type-moderation-actions/", {
		params: { limit },
	});
	return response.data;
};

export const approveAdminTeamSeasonKitType = async (id) => {
	const response = await api.post(`/admin/team-season-kit-types/${id}/approve/`);
	return response.data;
};

export const rejectAdminTeamSeasonKitType = async (id) => {
	const response = await api.post(`/admin/team-season-kit-types/${id}/reject/`);
	return response.data;
};

export const mergeAdminTeamSeasonKitType = async (id, targetKitTypeId) => {
	const response = await api.post(`/admin/team-season-kit-types/${id}/merge/`, {
		target_kit_type_id: targetKitTypeId,
	});
	return response.data;
};

export const undoAdminKitTypeModerationAction = async (id) => {
	const response = await api.post(`/admin/kit-type-moderation-actions/${id}/undo/`);
	return response.data;
};

export const getAdminKitReports = async ({
	status = "pending",
	reason,
	query,
} = {}) => {
	const response = await api.get("/admin/reports/", {
		params: {
			status,
			...(reason ? { reason } : {}),
			...(query ? { q: query } : {}),
		},
	});
	return response.data;
};

export const getAdminKitReportDetail = async (id) => {
	const response = await api.get(`/admin/reports/${id}/`);
	return response.data;
};

export const dismissAdminKitReport = async (id, payload) => {
	const response = await api.post(`/admin/reports/${id}/dismiss/`, payload);
	return response.data;
};

export const removeAdminReportedKit = async (id, payload) => {
	const response = await api.post(`/admin/reports/${id}/remove-kit/`, payload);
	return response.data;
};

export const getUnverifiedTeams = async () => {
	const response = await api.get("/admin/teams/unverified/");
	return response.data;
};

export const approveTeam = async (teamId, payload) => {
	const response = await api.post(`/admin/teams/${teamId}/approve/`, payload);
	return response.data;
};

export const mergeTeam = async (teamId, targetTeamId) => {
	const response = await api.post(`/admin/teams/${teamId}/merge/`, {
		target_team_id: targetTeamId,
	});
	return response.data;
};

export const rejectTeam = async (teamId) => {
	const response = await api.post(`/admin/teams/${teamId}/reject/`);
	return response.data;
};

export const deleteTeamContent = async (teamId, payload) => {
	const response = await api.post(`/admin/teams/${teamId}/delete-content/`, payload);
	return response.data;
};

export const getAdminCountries = async () => {
	const response = await api.get("/admin/countries/");
	return response.data;
};

export const createAdminCountry = async (payload) => {
	const response = await api.post("/admin/countries/", payload);
	return response.data;
};

export const getAdminLeagues = async (countryId) => {
	const response = await api.get("/admin/leagues/", {
		params: countryId ? { country_id: countryId } : {},
	});
	return response.data;
};

export const createAdminLeague = async (payload) => {
	const response = await api.post("/admin/leagues/", payload);
	return response.data;
};

export const getAdminCatalogCountries = async (params = {}) => {
	const response = await api.get("/admin/catalog/countries/", { params });
	return response.data;
};

export const createAdminCatalogCountry = async (payload) => {
	const response = await api.post(
		"/admin/catalog/countries/",
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const updateAdminCatalogCountry = async (id, payload) => {
	const response = await api.patch(
		`/admin/catalog/countries/${id}/`,
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const getAdminCatalogLeagues = async (params = {}) => {
	const response = await api.get("/admin/catalog/leagues/", { params });
	return response.data;
};

export const createAdminCatalogLeague = async (payload) => {
	const response = await api.post(
		"/admin/catalog/leagues/",
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const updateAdminCatalogLeague = async (id, payload) => {
	const response = await api.patch(
		`/admin/catalog/leagues/${id}/`,
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const getAdminCatalogTeams = async (params = {}) => {
	const response = await api.get("/admin/catalog/teams/", { params });
	return response.data;
};

export const createAdminCatalogTeam = async (payload) => {
	const response = await api.post(
		"/admin/catalog/teams/",
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const updateAdminCatalogTeam = async (id, payload) => {
	const response = await api.patch(
		`/admin/catalog/teams/${id}/`,
		buildMultipartPayload(payload),
		{ headers: { "Content-Type": "multipart/form-data" } },
	);
	return response.data;
};

export const searchVerifiedTeams = async (query) => {
	const response = await api.get("/teams/search/", {
		params: { q: query },
	});
	return response.data;
};

export default api;
