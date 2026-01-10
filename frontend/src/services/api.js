import axios from 'axios';

// Temporary API URL
const API_URL = 'http://127.0.0.1:8000/api';

const api = axios.create({
    baseURL: API_URL,
    timeout: 5000, // Timeout after 5 seconds
});

// INTERCEPTOR: Before each request, add the token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
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
        const response = await api.post('/my-collection/', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
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

// Search users by username
export const searchUsers = async (query) => {
    // Query example: /users/search/?q=messi
    const response = await api.get(`/users/search/?q=${query}`);
    return response.data;
};

// Update user profile
export const updateUserProfile = async (formData) => {
    try {
        const response = await api.put('/profile/update/', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    } catch (error) {
        throw error;
    }
};

export default api;