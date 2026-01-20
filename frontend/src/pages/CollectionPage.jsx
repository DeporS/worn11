import { useState, useEffect } from 'react';
import { searchUsers } from '../services/api';
import UserCard from '../components/UserCard';
import SearchBar from '../components/SearchBar';

const CollectionPage = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');

    useEffect(() => {
        // if (!searchQuery) return;
        if (!searchQuery.trim() || searchQuery.trim().length < 3) {
            setUsers([]);
            setLoading(false);
            return;
        }

        // Delay so we don't spam the API with requests on every keystroke
        const delayDebounceFn = setTimeout(() => {
            
            setLoading(true);
            setError(null);

            searchUsers(searchQuery)
                .then(data => {
                    setUsers(data);
                    setLoading(false);
                })
                .catch(err => {
                    console.error(err);
                    setError('Failed to fetch users.');
                    setLoading(false);
                });

        }, 500); // 500ms debounce

        // Cleanup function to cancel the timeout if query changes before delay
        return () => clearTimeout(delayDebounceFn);

    }, [searchQuery]); // Run this effect every time searchQuery changes

    return (
        <div className="container py-5">
            <header className="mb-5 text-center">
                <h1 className="display-5 fw-bold">Find Collectors 🔍</h1>
                <p className="text-muted">Start typing to find users</p>
                
                <div className="mt-4 mx-auto" style={{ maxWidth: '600px' }}>
                    {/* We only pass value and onChange */}
                    <SearchBar 
                        value={searchQuery} 
                        onChange={setSearchQuery} 
                    />
                </div>
            </header>

            {/* Loading (Spinner) */}
            {loading && (
                <div className="text-center py-5">
                    <div className="spinner-border text-primary"></div>
                </div>
            )}
            
            {error && <div className="alert alert-danger text-center">{error}</div>}

            {/* List Section */}
            <div className="row g-4">
                {users.map(user => (
                <div key={user.id} className="col-12 col-sm-6 col-md-4 col-lg-3">
                    <UserCard user={user} />
                </div>
                ))}

                {/* No results message */}
                {!loading && users.length === 0 && searchQuery.trim() !== '' && searchQuery.trim().length >= 4 && !error && (
                    <div className="col-12 text-center text-muted py-5">
                        <h4>No users found matching "{searchQuery}" 🤷‍♂️</h4>
                    </div>
                )}
            </div>
        </div>
    );
};

export default CollectionPage;