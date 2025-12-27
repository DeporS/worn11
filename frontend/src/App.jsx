import { useState, useEffect } from 'react';
import { jwtDecode } from "jwt-decode";
import CollectionPage from './pages/CollectionPage';
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
    <div>
      <NavBar 
        user={user} 
        onLoginSuccess={handleLoginSuccess} 
        onLogout={handleLogout} 
        refreshUser={fetchUserData} 
      />

      {/* Pass user */}
      <CollectionPage user={user} />
      
      {/* <Footer /> */}
    </div>
  )
}

export default App;