import React from 'react';
import { useTranslation } from "react-i18next";

const TeamsGrid = ({ teams, loading, selectedLeagueName, onSelectTeam }) => {
    const { t } = useTranslation();
    if (loading) return <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>;
    if (teams.length === 0) return <div className="text-center text-muted py-5"><h4>{t("history.noTeamsFound", { league: selectedLeagueName })}</h4></div>;

    return (
        <div className="row g-4">
            {teams.map((team) => (
                <div key={team.id} className="col-6 col-sm-4 col-md-3 col-lg-2">
                    <div 
                        className="card h-100 shadow-sm border-0 p-3 align-items-center justify-content-center text-center team-card"
                        onClick={() => onSelectTeam(team)}
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
    );
};

export default TeamsGrid;
