import React from 'react';
import { Link } from 'react-router-dom';

const UserCard = ({ user }) => {
    return (
        <div className="card h-100 shadow-sm border-0 text-center p-3">
            <div className="card-body">
                {/* Avatar Placeholder - circle with the first letter */}
                <div className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center mx-auto mb-3" 
                     style={{ width: '60px', height: '60px', fontSize: '24px', fontWeight: 'bold' }}>
                    {user.username.charAt(0).toUpperCase()}
                </div>

                <h5 className="card-title fw-bold">@{user.username}</h5>
                
                <p className="text-muted small">
                    Collection size: <span className="fw-bold text-dark">{user.kits_count} kits</span>
                </p>

                {/* Link to this user's profile */}
                <Link to={`/profile/${user.username}`} className="btn btn-outline-primary btn-sm w-100 stretched-link">
                    View Profile
                </Link>
            </div>
        </div>
    );
};

export default UserCard;