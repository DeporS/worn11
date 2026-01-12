import { useState, useEffect } from 'react';
import { getUserCollection, getUserStats } from '../services/api';
import { Link, useParams } from 'react-router-dom';
import KitCard from '../components/KitCard';

import '../styles/profile.css';

const ProfilePage = ({ user }) => {
    const { username } = useParams(); // Get username from URL params

    const profileUsername = username || user?.username;

    const isOwner = user?.username === profileUsername; // Check if viewing own profile

    const [myKits, setMyKits] = useState([]);
    const [stats, setStats] = useState({ total_value: 0, total_kits: 0 });

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    
    useEffect(() => {
        if (!profileUsername) return;

        setLoading(true);
        setError(null);

        Promise.all([
            getUserCollection(profileUsername),
            getUserStats(profileUsername)
        ])
        .then(([kitsData, statsData]) => {
            setMyKits(kitsData);
            setStats(statsData);
        })
        .catch(err => {
            console.error("Failed to load profile", err);
            setError("User not found or error loading data.");
        })
        .finally(() => setLoading(false));

    }, [profileUsername, user?.username]);

    if (!profileUsername) return <div className="text-center mt-5">Please log in.</div>;
    if (loading) return <div className="text-center mt-5"><div className="spinner-border text-primary"></div></div>;
    if (error) return <div className="text-center mt-5 text-danger">{error}</div>;

    const handleDeleteSuccess = (deletedKitId) => {
        setMyKits(prev => prev.filter(item => item.id !== deletedKitId));
        getUserStats(profileUsername).then(setStats);
    };

    return (
        <div className="container-fluid py-5 px-3 px-md-5">
            {/* Profile headline */}
            <div className="container py-4 bg-white p-4 rounded shadow-sm mb-5 d-flex justify-content-between align-items-center">
                <div>
                    <div className="d-flex align-items-center gap-1">
                        <h2 className="fw-bold mb-0">@{profileUsername}</h2>
                        {isOwner && (
                            <Link to="/profile/edit" className="btn edit-button" title="Edit Profile">
                                ✏️
                            </Link>
                        )}
                    </div>
                    
                    {isOwner && user?.email && (
                        <p className="text-muted mb-0">{user.email}</p>
                    )}
                </div>
                <div className="text-end">
                    <h3 className="text-primary fw-bold mb-0">{stats.total_kits}</h3>
                    <span className="small text-muted d-block">Kits in collection</span>

                    <h4 className="text-success fw-bold mb-0 mt-2">
                        ${stats.total_value.toLocaleString()} 
                    </h4>
                    <span className="small text-muted">Total Value</span>
                </div>
            </div>

            {/* Add Kit Button */}
            {isOwner && (
                <div className="d-flex justify-content-center my-5">
                    <Link to="/add-kit" className="add-ghost">
                        + Add kit
                    </Link>
                </div>
            )}

            {/* Shirt list */}
            {loading ? (
                <div className="text-center"><div className="spinner-border text-primary"></div></div>
            ) : (
                <div className="row g-4">
                    {myKits.map(item => (
                        <div key={item.id} className="col-12 col-sm-12 col-md-12 col-lg-6 col-xl-6 col-xxl-4 col-xxl-4">
                            <KitCard 
                                item={item} 
                                onDeleteSuccess={handleDeleteSuccess} 
                                user={user}
                            />
                        </div>
                    ))}
                    
                    {myKits.length === 0 && (
                        <div className="text-center text-muted py-5 w-100">
                            <p>{isOwner ? "You don't" : "This user doesn't"} have any kits yet.</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default ProfilePage;