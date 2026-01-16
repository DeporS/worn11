import { useState, useEffect } from 'react';
import api from '../services/api';

// Importy nowych komponentów
import LeaguesGrid from '../components/history/LeaguesGrid';
import TeamsGrid from '../components/history/TeamsGrid';
import KitsGrid from '../components/history/KitsGrid';

// Import CSS
import '../styles/history.css';

const HistoryPage = ({ user }) => {
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);

    // --- DATA ---
    const [leagues, setLeagues] = useState([]);
    const [teams, setTeams] = useState([]);
    const [kits, setKits] = useState([]);

    // --- SELECTED ITEMS ---
    const [selectedLeague, setSelectedLeague] = useState(null);
    const [selectedTeam, setSelectedTeam] = useState(null);

    // 1. Fetch Leagues
    useEffect(() => {
        setLoading(true);
        api.get('/leagues/')
            .then(res => {
                setLeagues(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    // 2. Fetch Teams
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

    // 3. Fetch Kits
    useEffect(() => {
        if (selectedTeam && step === 3) {
            setLoading(true);
            api.get(`/kits/team/${selectedTeam.id}/best/`)
                .then(res => {
                    setKits(res.data.results || res.data);
                    setLoading(false);
                })
                .catch(err => setLoading(false));
        }
    }, [selectedTeam, step]);

    // Handlers
    const handleSelectLeague = (league) => {
        setSelectedLeague(league);
        setStep(2);
    };

    const handleSelectTeam = (team) => {
        setSelectedTeam(team);
        setStep(3);
    };

    const handleReset = (targetStep) => {
        setStep(targetStep);
        if (targetStep === 1) { setSelectedLeague(null); setSelectedTeam(null); }
        else if (targetStep === 2) { setSelectedTeam(null); }
    };

    return (
        <div className="container py-5" style={{ maxWidth: '1400px' }}>
            
            {/* HEADER & BREADCRUMBS */}
            <div className="mb-5">
                <nav aria-label="breadcrumb">
                    <ol className="breadcrumb fs-5 align-items-center">
                        <li className={`breadcrumb-item ${step === 1 ? 'active' : ''}`}>
                            <span role="button" className={step > 1 ? "text-primary text-decoration-underline fw-bold" : "fw-bold"} onClick={() => handleReset(1)}>
                                Leagues
                            </span>
                        </li>
                        {step > 1 && selectedLeague && (
                            <li className={`breadcrumb-item ${step === 2 ? 'active' : ''}`}>
                                <span role="button" className={step > 2 ? "text-primary text-decoration-underline" : ""} onClick={() => handleReset(2)}>
                                    {selectedLeague.name}
                                </span>
                            </li>
                        )}
                        {step > 2 && selectedTeam && (
                            <li className="breadcrumb-item active">{selectedTeam.name}</li>
                        )}
                    </ol>
                </nav>
            </div>

            {/* --- VIEW SWITCHER --- */}
            {step === 1 && (
                <LeaguesGrid 
                    leagues={leagues} 
                    loading={loading} 
                    onSelectLeague={handleSelectLeague} 
                />
            )}

            {step === 2 && (
                <TeamsGrid 
                    teams={teams} 
                    loading={loading} 
                    selectedLeagueName={selectedLeague?.name}
                    onSelectTeam={handleSelectTeam}
                />
            )}

            {step === 3 && (
                <KitsGrid 
                    kits={kits} 
                    loading={loading} 
                    selectedTeamName={selectedTeam?.name} 
                    user={user} 
                />
            )}

        </div>
    );
};

export default HistoryPage;