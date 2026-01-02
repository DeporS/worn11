import { useState, useEffect } from 'react';
import { getUserCollection } from '../services/api';
import { Link } from 'react-router-dom';
import KitCard from '../components/KitCard';

const ProfilePage = ({ user }) => {
    const [myKits, setMyKits] = useState([]);
    const [loading, setLoading] = useState(true);
    
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

    useEffect(() => {
        fetchMyCollection();
    }, [user]); // Do when user loads

    if (!user) return <div className="text-center mt-5">Please log in to view your profile.</div>;

    return (
        <div className="container py-5">
      {/* Profile headline */}
      <div className="bg-white p-4 rounded shadow-sm mb-5 d-flex justify-content-between align-items-center">
        <div>
            <h2 className="fw-bold mb-0">@{user.username}</h2>
            <p className="text-muted mb-0">{user.email}</p>
        </div>
        <div className="text-end">
            <h3 className="text-primary fw-bold mb-0">{myKits.length}</h3>
            <span className="small text-muted">Kits in collection</span>
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
                <KitCard item={item} />
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