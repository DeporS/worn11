import React from 'react';
import LoginButton from './LoginButton';

const NavBar = ({user, onLoginSuccess, onLogout}) => {
  return (
    <nav className="navbar navbar-expand-lg navbar-light bg-light">
      <div className="container">
        <a className="navbar-brand" href="/">Worn11</a>
        <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
          <span className="navbar-toggler-icon"></span>
        </button>
        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav ms-auto">
            {user ? (
                // LOGGED IN
                <div className="d-flex align-items-center gap-3">
                    <span className="text-muted small">
                        <strong>{user.username}</strong>
                    </span>
                    <button 
                        className="btn btn-outline-danger btn-sm" 
                        onClick={onLogout}
                    >
                        Logout
                    </button>
                </div>
            ) : (
                // NOT LOGGED IN
                <div>
                    {/* Pass the function to handle successful login */}
                    <LoginButton onLoginSuccess={onLoginSuccess} />
                </div>
            )}
          </ul>
        </div>
      </div>
    </nav>
  );
}

export default NavBar;