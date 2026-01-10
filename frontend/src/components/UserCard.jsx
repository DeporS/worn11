import React from 'react';
import { Link } from 'react-router-dom';

import '../styles/user_cards.css';

const UserCard = ({ user }) => {

    return (
        <div className="card h-100 shadow-sm border-0 text-center p-3 user-card-link">
            {/* Link to this user's profile */}
            <Link 
                to={`/profile/${user.username}`} 
                className="btn btn-sm w-100 stretched-link"
            >
                <div className="card-body d-flex flex-column align-items-center gap-1">
                    {user.avatar ? (
                        // If avatar URL exists, show the image
                        <img 
                            src={user.avatar} 
                            alt={user.username}
                            className="rounded-circle border"
                            style={{ 
                                width: '80px', 
                                height: '80px', 
                                objectFit: 'cover'
                            }}
                        />
                    ) : (
                        // If no avatar, show placeholder with initial
                        <div 
                            className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center shadow-sm" 
                            style={{ 
                                width: '80px', 
                                height: '80px', 
                                fontSize: '32px', 
                                fontWeight: 'bold' 
                            }}
                        >
                            {user.username.charAt(0).toUpperCase()}
                        </div>
                    )}

                    <h5 className="card-title fw-bold">@{user.username}</h5>
                    
                    <p className="text-muted small">
                        Collection size: <span className="fw-bold text-dark">{user.kits_count} kits</span>
                    </p>
                </div>
            </Link>
        </div>
    );
};

export default UserCard;