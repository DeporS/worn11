import { useState, useEffect } from 'react';
import api from '../services/api';
import KitCard from '../components/KitCard';

const HistoryPage = ({ user }) => {
    const [step, setStep] = useState(1); // 1: Leagues, 2: Teams, 3: Kits
    const [loading, setLoading] = useState(false);

    // --- DATA ---
    const [leagues, setLeagues] = useState([]);
    const [teams, setTeams] = useState([]);
    const [kits, setKits] = useState([]);

    // --- SELECTED ITEMS ---
    const [selectedLeague, setSelectedLeague] = useState(null);
    const [selectedTeam, setSelectedTeam] = useState(null);

    // Fetch Leagues on start
    useEffect(() => {
        setLoading(true);
        api.get('/leagues/')
            .then(res => {
                setLeagues(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Error loading leagues:", err);
                setLoading(false);
            });
    }, []);

    // Fetch Teams after selecting a League
    useEffect(() => {
        if (selectedLeague && step === 2) {
            setLoading(true);
            api.get(`/teams/league/${selectedLeague.id}/`)
                .then(res => {
                    setTeams(res.data);
                    setLoading(false);
                })
                .catch(err => setLoading(false));
        }
    }, [selectedLeague, step]);

    // Fetch Kits after selecting a Team
    useEffect(() => {
        if (selectedTeam && step === 3) {
            setLoading(true);
            api.get(`/kits/team/${selectedTeam.id}/best/`)
                .then(res => {
                    // Handling pagination: backend returns { results: [...] } or just a list [...]
                    setKits(res.data.results || res.data);
                    setLoading(false);
                })
                .catch(err => setLoading(false));
        }
    }, [selectedTeam, step]);

    // Function to reset view (clicking on Breadcrumbs)
    const handleReset = (targetStep) => {
        setStep(targetStep);
        if (targetStep === 1) {
            setSelectedLeague(null);
            setSelectedTeam(null);
        } else if (targetStep === 2) {
            setSelectedTeam(null);
        }
    };

    return (
        <div className="container py-5" style={{ maxWidth: '1400px' }}>
            
            {/* HEADER & BREADCRUMBS */}
            <div className="mb-5">
                <h1 className="fw-bold display-5 mb-3">Football Shirts History 🏆</h1>
                
                <nav aria-label="breadcrumb">
                    <ol className="breadcrumb fs-5 align-items-center">
                        {/* Leagues */}
                        <li className={`breadcrumb-item ${step === 1 ? 'active' : ''}`}>
                            <span 
                                role="button" 
                                className={step > 1 ? "text-primary text-decoration-underline fw-bold" : "fw-bold"}
                                onClick={() => handleReset(1)}
                            >
                                Leagues
                            </span>
                        </li>

                        {/* Selected League Name */}
                        {step > 1 && selectedLeague && (
                            <li className={`breadcrumb-item ${step === 2 ? 'active' : ''}`}>
                                <span 
                                    role="button"
                                    className={step > 2 ? "text-primary text-decoration-underline" : ""}
                                    onClick={() => handleReset(2)}
                                >
                                    {selectedLeague.name}
                                </span>
                            </li>
                        )}

                        {/* Selected Team Name */}
                        {step > 2 && selectedTeam && (
                            <li className="breadcrumb-item active" aria-current="page">
                                {selectedTeam.name}
                            </li>
                        )}
                    </ol>
                </nav>
            </div>

            {/* --- LEAGUES GRID --- */}
            {step === 1 && (
                <div>
                    {loading && <div className="text-center w-100 py-5"><div className="spinner-border text-primary"></div></div>}
                    
                    {!loading && (() => {
                        // Grouping leagues by country
                        const groupedLeagues = leagues.reduce((acc, league) => {
                            // If a league doesn't have a country, group it under "International / Other"
                            const countryName = league.country?.name || "International / Other";
                            
                            if (!acc[countryName]) {
                                acc[countryName] = {
                                    leagues: [],
                                    flag: league.country?.flag // Remember country flag for header
                                };
                            }
                            acc[countryName].leagues.push(league);
                            return acc;
                        }, {});

                        // SORTING COUNTRIES ALPHABETICALLY
                        const sortedCountries = Object.keys(groupedLeagues).sort();

                        // RENDERING GROUPS
                        return sortedCountries.map((countryName) => {
                            const group = groupedLeagues[countryName];

                            return (
                                <div key={countryName} className="mb-5">
                                    {/* --- COUNTRY HEADER --- */}
                                    <div className="d-flex align-items-center gap-3 mb-3 border-bottom pb-2">
                                        {group.flag ? (
                                            <img 
                                                src={group.flag} 
                                                alt={countryName} 
                                                className="rounded-circle shadow-sm border"
                                                style={{ width: '40px', height: '40px', objectFit: 'cover' }}
                                            />
                                        ) : (
                                            <div className="bg-light rounded-circle d-flex align-items-center justify-content-center border" style={{ width: '40px', height: '40px' }}>
                                                🌍
                                            </div>
                                        )}
                                        <h2 className="fw-bold m-0 text-dark">{countryName}</h2>
                                    </div>

                                    {/* --- LEAGUES GRID FOR THIS COUNTRY --- */}
                                    <div className="row g-4">
                                        {group.leagues.map((league) => (
                                            <div key={league.id} className="col-12 col-md-6 col-lg-4 col-xl-3">
                                                <div 
                                                    className="card h-100 shadow-sm border-0 text-white p-4 league-card position-relative overflow-hidden"
                                                    style={{ 
                                                        backgroundColor: league.hex_color || '#6c757d', 
                                                        cursor: 'pointer', 
                                                        transition: 'transform 0.2s',
                                                        minHeight: '140px'
                                                    }}
                                                    onClick={() => {
                                                        setSelectedLeague(league);
                                                        setStep(2);
                                                    }}
                                                    onMouseEnter={(e) => e.currentTarget.style.transform = "scale(1.03)"}
                                                    onMouseLeave={(e) => e.currentTarget.style.transform = "scale(1)"}
                                                >
                                                    {/* Watermark Logo */}
                                                    {league.logo && (
                                                        <img 
                                                            src={league.logo} 
                                                            alt="" 
                                                            style={{
                                                                position: 'absolute',
                                                                right: '-20px',
                                                                bottom: '-20px',
                                                                width: '120px',
                                                                opacity: 0.15,
                                                                transform: 'rotate(-15deg)',
                                                                pointerEvents: 'none'
                                                            }} 
                                                        />
                                                    )}

                                                    <div className="d-flex flex-column h-100 justify-content-center position-relative z-1 text-center">
                                                        <h3 className="fw-bold m-0 text-shadow">{league.name}</h3>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        });
                    })()}
                    
                    {!loading && leagues.length === 0 && (
                        <div className="text-center text-muted">No leagues found.</div>
                    )}
                </div>
            )}

            {/* --- TEAMS GRID --- */}
            {step === 2 && (
                <div>
                    {loading ? (
                        <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>
                    ) : teams.length === 0 ? (
                        <div className="text-center text-muted py-5">
                            <h4>No teams found in {selectedLeague?.name} yet.</h4>
                        </div>
                    ) : (
                        <div className="row g-4">
                            {teams.map((team) => (
                                <div key={team.id} className="col-6 col-sm-4 col-md-3 col-lg-2">
                                    <div 
                                        className="card h-100 shadow-sm border-0 p-3 align-items-center justify-content-center text-center bg-white"
                                        style={{ cursor: 'pointer', transition: 'all 0.2s' }}
                                        onClick={() => {
                                            setSelectedTeam(team);
                                            setStep(3);
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.transform = "translateY(-5px)";
                                            e.currentTarget.classList.add("shadow");
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.transform = "translateY(0)";
                                            e.currentTarget.classList.remove("shadow");
                                        }}
                                    >
                                        {team.logo ? (
                                            <img src={team.logo} alt={team.name} style={{ width: '70px', height: '70px', objectFit: 'contain' }} className="mb-3" />
                                        ) : (
                                            <div className="bg-light rounded-circle d-flex align-items-center justify-content-center mb-3" style={{ width: '70px', height: '70px', fontSize: '30px' }}>⚽</div>
                                        )}
                                        <span className="fw-bold small text-dark">{team.name}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* --- KITS GRID --- */}
            {step === 3 && (
                <div>
                    {loading ? (
                        <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>
                    ) : kits.length === 0 ? (
                        <div className="text-center py-5 text-muted">
                            <h4>No kits added for {selectedTeam?.name} yet.</h4>
                            <p>Be the first to add one!</p>
                        </div>
                    ) : (
                        <div className="row g-4">
                            {kits.map((item) => (
                                <div key={item.id} className="col-12 col-sm-6 col-lg-4 col-xl-3 col-xxl-2">
                                    <KitCard 
                                        item={item} 
                                        user={user}
                                        // Optionally: delete function if admin should do it
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

        </div>
    );
};

export default HistoryPage;