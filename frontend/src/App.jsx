import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import CollectionPage from './pages/CollectionPage';
import ProfilePage from './pages/ProfilePage';
import AddShirtFormPage from './pages/AddShirtFormPage';
import EditShirtFormPage from './pages/EditShirtFormPage';
import EditProfilePage from './pages/EditProfilePage';
import NavBar from './components/NavBar';
import api from './services/api';
import './index.css';

function App() {
  const [user, setUser] = useState(null); // User state
  
  const fetchUserData = async () => {
    try {
        const response = await api.get('/auth/user/');
        setUser(response.data);
    } catch (error) {
        console.error("Błąd pobierania profilu:", error);
        handleLogout();
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
        fetchUserData();
    }
  }, []);

  const handleLoginSuccess = () => {
    fetchUserData();
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  return (
    <Router>
      <div>
        <NavBar 
          user={user} 
          onLoginSuccess={handleLoginSuccess} 
          onLogout={handleLogout} 
          refreshUser={fetchUserData} 
        />

        <Routes>
          {/* Landing Page */}
          <Route path="/" element={<CollectionPage user={user} />} />
    
          {/* My Collection Page */}  
          <Route path="/my-collection"
            element={user ? <ProfilePage user={user} /> : <Navigate to="/" />} 
          />

          {/* User Profile Page */}
          <Route path="/profile/:username" 
            element={<ProfilePage user={user} />} 
          />

          {/* Edit Profile Page */}
          <Route 
                path="/profile/edit" 
                element={
                    <EditProfilePage 
                        user={user} // User logged in
                        setUser={setUser} // Function to update user state
                    />
                } 
            />

          {/* Add Shirt Form Page */}
          <Route path="/add-kit"
            element={user ? <AddShirtFormPage /> : <Navigate to="/" />} 
          />

          {/* Edit Shirt Form Page */}
          <Route path="/edit-kit/:id"
            element={user ? <EditShirtFormPage user={user} /> : <Navigate to="/" />} 
          />
        </Routes>
      </div>
    </Router>
  )
}

export default App;