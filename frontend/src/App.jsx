import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import CollectionPage from './pages/CollectionPage';
import ProfilePage from './pages/ProfilePage';
import NavBar from './components/NavBar';
import api from './services/api';

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
    
          {/* Profile Page */}  
          <Route path="/profile"
            element={user ? <ProfilePage user={user} /> : <Navigate to="/" />} 
          />
        </Routes>
      </div>
    </Router>
  )
}

export default App;