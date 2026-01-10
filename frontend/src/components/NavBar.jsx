import React from 'react';
import LoginButton from './LoginButton';
import { Link } from 'react-router-dom';

const API_URL = 'http://127.0.0.1:8000';

const NavBar = ({user, onLoginSuccess, onLogout}) => {

    // Helper to get full avatar URL
    const getAvatarUrl = (avatarPath) => {
        if (!avatarPath) return null;
        if (avatarPath.startsWith('http')) return avatarPath;
        return `${API_URL}${avatarPath}`;
    };

    return (
        <nav className="navbar navbar-expand-lg navbar-light bg-light">
            <div className="container">
                <a className="navbar-brand" href="/">Worn11</a>
                <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
                    <span className="navbar-toggler-icon"></span>
                </button>
                <div className="collapse navbar-collapse" id="navbarNav">
                    <ul className="navbar-nav ms-auto">
                        {user ? (
                            // LOGGED IN
                            <div className="d-flex align-items-center gap-3">
                                <Link 
                                    to="/my-collection" 
                                    className="text-decoration-none text-dark fw-bold d-flex align-items-center gap-2"
                                >
                                    {user.profile?.avatar ? (
                                        <img 
                                            src={getAvatarUrl(user.profile.avatar)}
                                            alt="Avatar" 
                                            className="rounded-circle border" 
                                            style={{width: '35px', height: '35px', objectFit: 'cover'}}
                                        />
                                    ) : (
                                        <div 
                                            className="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center fw-bold" 
                                            style={{width: '35px', height: '35px', fontSize: '14px'}}
                                        >
                                            {user.username.charAt(0).toUpperCase()}
                                        </div>
                                    )}
                                    {user.username}
                                </Link>
                                <button 
                                    className="btn btn-outline-danger btn-sm" 
                                    onClick={onLogout}
                                >
                                    Logout
                                </button>
                            </div>
                        ) : (
                            // NOT LOGGED IN
                            <div>
                                {/* Pass the function to handle successful login */}
                                <LoginButton onLoginSuccess={onLoginSuccess} />
                            </div>
                        )}
                    </ul>
                </div>
            </div>
        </nav>
    );
}

export default NavBar;