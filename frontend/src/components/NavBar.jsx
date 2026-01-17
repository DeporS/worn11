import React from 'react';
import LoginButton from './LoginButton';
import UserAvatar from './UserAvatar';
import { Link, NavLink } from 'react-router-dom';

const API_URL = 'http://127.0.0.1:8000';

const NavBar = ({ user, onLoginSuccess, onLogout }) => {
    return (
        <nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm py-3 sticky-top">
            <div className="container">
                
                {/* 1. BRAND */}
                <Link className="navbar-brand fw-black fs-3" to="/" style={{ letterSpacing: '-1px' }}>
                    Worn<span className="text-primary">11</span>
                </Link>

                {/* 2. TOGGLER (Mobile) */}
                <button 
                    className="navbar-toggler border-0" 
                    type="button" 
                    data-bs-toggle="collapse" 
                    data-bs-target="#navbarNav" 
                    aria-controls="navbarNav" 
                    aria-expanded="false" 
                    aria-label="Toggle navigation"
                >
                    <span className="navbar-toggler-icon"></span>
                </button>

                {/* 3. COLLAPSIBLE CONTENT */}
                <div className="collapse navbar-collapse" id="navbarNav">
                    
                    {/* Navigation Links (Left side) */}
                    <ul className="navbar-nav me-auto mb-2 mb-lg-0">
                        <li className="nav-item">
                            <NavLink 
                                to="/history" 
                                className={({ isActive }) => 
                                    `nav-link px-3 fw-bold ${isActive ? 'text-primary' : 'text-dark'}`
                                }
                            >
                                Kit Museum
                            </NavLink>
                        </li>
                    </ul>

                    {/* User actions (Right side) */}
                    <div className="d-flex align-items-center">
                        {user ? (
                            // --- LOGGED IN ---
                            <div className="d-flex align-items-center gap-3">
                                {/* Profile Link */}
                                <Link
                                    to="/my-collection"
                                    className="text-decoration-none text-dark d-flex align-items-center gap-2 user-nav-link p-1 rounded pe-3"
                                    style={{ transition: 'background 0.2s' }}
                                >
                                    <UserAvatar user={user} size={35} />
                                    <span className="fw-bold small">{user.username}</span>
                                </Link>

                                {/* Divider (vertical line) */}
                                <div className="vr d-none d-lg-block mx-2 text-muted"></div>

                                {/* Logout Button */}
                                <button 
                                    className="btn btn-link text-muted text-decoration-none p-0" 
                                    onClick={onLogout}
                                    title="Logout"
                                >
                                    <i className="bi bi-box-arrow-right fs-5"></i>
                                </button>
                            </div>
                        ) : (
                            // --- NOT LOGGED IN ---
                            <div>
                                <LoginButton onLoginSuccess={onLoginSuccess} />
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
}

export default NavBar;