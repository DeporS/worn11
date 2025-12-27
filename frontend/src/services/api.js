import axios from 'axios';

// Temporary API URL
const API_URL = 'http://127.0.0.1:8000/api';

const api = axios.create({
    baseURL: API_URL,
    timeout: 5000, // Timeout after 5 seconds
});

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

export default api;