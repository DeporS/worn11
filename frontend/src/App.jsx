import { useState, useEffect } from 'react'
import axios from 'axios'

function App() {
  const [kits, setKits] = useState([])
  const [loading, setLoading] = useState(false) // Change to false initially
  const [error, setError] = useState(null)
  
  // New state: who are we searching for?
  const [searchUser, setSearchUser] = useState('') // Default blank

  // Function to fetch data (triggered by button or Enter key)
  const fetchCollection = () => {
    setLoading(true)
    setError(null)
    setKits([]) // Clear the list before new search
    // Dynamic URL with entered username
    axios.get(`http://127.0.0.1:8000/api/user-collection/${searchUser}/`)
      .then(response => {
        setKits(response.data)
        setLoading(false)
      })
      .catch(err => {
        console.error(err)
        setError("Nie znaleziono użytkownika lub błąd serwera.")
        setLoading(false)
      })
  }

  // // Fetch admin by default on start
  // useEffect(() => {
  //   fetchCollection()
  // }, [])

  return (
    <div className="container py-5">
      <header className="mb-4 text-center">
        <h1 className="display-5 fw-bold">Worn11 🔍</h1>
        
        {/* Search Bar */}
        <div className="d-flex justify-content-center mt-4">
            <div className="input-group" style={{maxWidth: '400px'}}>
                <span className="input-group-text bg-white">@</span>
                <input 
                    type="text" 
                    className="form-control" 
                    placeholder="Username (e.g., messi)"
                    value={searchUser}
                    onChange={(e) => setSearchUser(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && fetchCollection()}
                />
                <button className="btn btn-primary" onClick={fetchCollection}>
                    Search
                </button>
            </div>
        </div>
      </header>

      {/* Loading */}
      {loading && <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>}
      
      {/* Error */}
      {error && <div className="alert alert-danger text-center">{error}</div>}

      {/* List */}
      <div className="row g-4">
        {kits.map(item => (
          <div key={item.id} className="col-12 col-md-6 col-lg-4">
            <div className="card h-100 shadow-sm border-0">
               {/* Gallery of photos for one kit */}
              <div className="d-flex overflow-auto">
                {item.images.map(photo => (
                  <img 
                    key={photo.id} 
                    src={photo.image} // This is the link from the API
                    alt="User photo"
                    style={{width: '100px', height: '100px', objectFit: 'cover', margin: '5px'}}
                  />
                ))}
              </div>
               <div className="card-body">
                  <h5 className="card-title">{item.kit.team.name}</h5>
                  <p className="small text-muted">Owner: {searchUser}</p>
                  <span className="badge bg-success">{item.final_value} USD</span>
               </div>
            </div>
          </div>
        ))}

        {!loading && kits.length === 0 && !error && (
            <div className="col-12 text-center text-muted py-5">
                <h4>This user doesn't have any kits yet</h4>
            </div>
        )}
      </div>
    </div>
  )
}

export default App