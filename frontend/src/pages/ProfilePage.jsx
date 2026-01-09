import { useState, useEffect } from 'react';
import { getUserCollection, getUserStats } from '../services/api';
import { Link } from 'react-router-dom';
import KitCard from '../components/KitCard';

const ProfilePage = ({ user }) => {
    const [myKits, setMyKits] = useState([]);
    const [stats, setStats] = useState({ total_value: 0, total_kits: 0 });

    const [loading, setLoading] = useState(true);
    
    // Fetch user's collection on mount (Can add pagination later)
    const fetchMyCollection = () => {
        if (user?.username) {
            setLoading(true);
            getUserCollection(user.username)
                .then((data) => {
                    setMyKits(data);
                    setLoading(false);
                })
                .catch((error) => {
                    console.error('Error fetching user collection:', error);
                    setLoading(false);
                });
        }
    };

    // Fetch stats on mount
    const fetchStats = () => {
        if (user?.username) {
            getUserStats(user.username)
                .then(res => setStats(res))
                .catch(err => console.error(err));
        }
    };

    useEffect(() => {
        if (user) {
            setLoading(true);
            // Fetch both collection and stats in parallel
            Promise.all([fetchMyCollection(), fetchStats()])
                .finally(() => setLoading(false));
        }
    }, [user]);

    if (!user) return <div className="text-center mt-5">Please log in to view your profile.</div>;

    // Handle deletion of a kit from the collection
    const handleDeleteSuccess = (deletedKitId) => {
        setMyKits(prevKits => prevKits.filter(item => item.id !== deletedKitId));
        fetchStats(); // Refresh stats after deletion
    };

    return (
        <div className="container py-5">
      {/* Profile headline */}
      <div className="bg-white p-4 rounded shadow-sm mb-5 d-flex justify-content-between align-items-center">
        <div>
            <h2 className="fw-bold mb-0">@{user.username}</h2>
            <p className="text-muted mb-0">{user.email}</p>
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
      <Link to="/add-kit" className="btn btn-success">
        + Add New Kit
      </Link>

      {/* Shirt list */}
      {loading ? (
         <div className="text-center"><div className="spinner-border text-primary"></div></div>
      ) : (
        <div className="row g-4">
            {myKits.map(item => (
            <div key={item.id} className="col-12 col-md-6 col-lg-4">
                <KitCard item={item} onDeleteSuccess={handleDeleteSuccess} />
                {/* EDIT / DELETE WILL BE HERE */}
            </div>
            ))}
            
            {myKits.length === 0 && (
                <div className="text-center text-muted py-5">
                    <p>You don't have any kits yet. Add your first one!</p>
                </div>
            )}
        </div>
      )}
    </div>
  );
};

export default ProfilePage;