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

// Function to add a kit to the user's collection
export const addKitToCollection = async (fromData) => {
    try {
        const response = await api.post('/my-collection/', fromData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    } catch (error) {
        throw error;
    }
}

export default api;