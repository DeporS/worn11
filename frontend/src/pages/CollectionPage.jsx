import { useState } from 'react';
import { getUserCollection } from '../services/api';
import KitCard from '../components/KitCard';
import SearchBar from '../components/SearchBar';

const CollectionPage = () => {
  const [kits, setKits] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchUser, setSearchUser] = useState('');

  const handleSearch = () => {
    if (!searchUser.trim()) return; // Don't search empty

    setLoading(true);
    setError(null);
    setKits([]);

    getUserCollection(searchUser)
      .then(data => {
        setKits(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        if(!err.response) {
          setError('Error connecting to the server.');
        } else if(err.response.status === 404) {
          setError('User not found.');
        } else {
          setError('An unexpected error occurred.');
        }
        setLoading(false);
      });
  };

  return (
    <div className="container py-5">
      <header className="mb-5 text-center">
        <h1 className="display-5 fw-bold">Search collections 🔍</h1>
        <div className="mt-4">
            <SearchBar 
                value={searchUser} 
                onChange={setSearchUser} 
                onSearch={handleSearch} 
            />
        </div>
      </header>

      {/* Loading/Error Section */}
      {loading && (
          <div className="text-center py-5">
              <div className="spinner-border text-primary"></div>
          </div>
      )}
      
      {error && <div className="alert alert-danger text-center">{error}</div>}

      {/* List Section */}
      <div className="row g-4">
        {kits.map(item => (
          <div key={item.id} className="col-12 col-md-6 col-lg-4">
            <KitCard item={item} />
          </div>
        ))}

        {!loading && kits.length === 0 && !error && searchUser && (
            <div className="col-12 text-center text-muted py-5">
                <h4>No results for this user 🤷‍♂️</h4>
            </div>
        )}
      </div>
    </div>
  );
};

export default CollectionPage;