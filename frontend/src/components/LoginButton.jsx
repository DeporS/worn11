import { useGoogleLogin } from '@react-oauth/google';
import api from '../services/api';

const LoginButton = ({ onLoginSuccess }) => {
    
    const login = useGoogleLogin({
    
        flow: 'auth-code', 
        
        onSuccess: async (codeResponse) => {
            try {
                
                const res = await api.post('/auth/google/', {
                    code: codeResponse.code, 
                });

                const { access, refresh } = res.data;
                localStorage.setItem('access_token', access);
                localStorage.setItem('refresh_token', refresh);
                onLoginSuccess();
                
            } catch (err) {
                
                console.error("Login Error:", err.response?.data || err.message);
                alert("Logowanie nieudane");
            }
        },
        onError: () => console.log('Login Failed'),
    });

    return (
        <button onClick={() => login()} className="btn btn-outline-dark">
            Sign in with Google
        </button>
    );
};

export default LoginButton;