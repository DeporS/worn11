import axios from "axios";

// Temporary API URL
const API_URL = "http://127.0.0.1:8000/api";

const api = axios.create({
	baseURL: API_URL,
	timeout: 5000, // Timeout after 5 seconds
});

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

export const getConversationMessages = async (conversationId) => {
	const response = await api.get(`/conversations/${conversationId}/messages/`);
	return response.data;
};

export const getUnreadMessagesCount = async () => {
	const response = await api.get("/conversations/unread-count/");
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
export const getKitVariants = async (teamId, season, type) => {
	const response = await api.get(
		`/kits/team/${teamId}/variants/?season=${encodeURIComponent(season)}&type=${encodeURIComponent(type)}`,
	);
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

export default api;
