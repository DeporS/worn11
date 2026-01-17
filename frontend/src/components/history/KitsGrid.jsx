import React, { useMemo, useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import KitCard from '../history/KitCardHistory';
import SeasonRow from './SeasonRow';

import '../../styles/history.css';

const KitsGrid = ({ kits, loading, selectedTeamName, user }) => {
    const [showEmpty, setShowEmpty] = useState(true);

    // Generate seasons from current year down to 1940/1941
    const seasons = useMemo(() => {
        const years = [];
        const currentYear = new Date().getFullYear();
        for (let y = currentYear + 1; y >= 1940; y--) {
            years.push(`${y-1}/${y}`);
        }
        return years;
    }, []);

    // Data organization: best kit per season and type
    const organizedKits = useMemo(() => {
        const map = {}; 
        if (!kits) return map;

        kits.forEach(userKit => {
            const season = userKit.kit.season;
            const type = userKit.kit.kit_type;
            const likes = userKit.likes_count || 0;

            if (!map[season]) map[season] = {};
            
            // if new has more likes, replace
            if (!map[season][type] || likes > (map[season][type].likes_count || 0)) {
                map[season][type] = userKit;
            }
        });
        return map;
    }, [kits]);


    if (loading) return <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>;

    return (
        <div>
            {/* --- TOP CONTROL BAR --- */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    {kits.length === 0 && (
                        <span className="text-muted">No kits yet. Start the collection!</span>
                    )}
                </div>
                
                <div className="form-check form-switch">
                    <input 
                        className="form-check-input" 
                        type="checkbox" 
                        id="showEmptySwitch"
                        checked={showEmpty}
                        onChange={(e) => setShowEmpty(e.target.checked)}
                    />
                    <label className="form-check-label small text-muted" htmlFor="showEmptySwitch">
                        Show missing kits
                    </label>
                </div>
            </div>

            {/* --- SEASONS LIST --- */}
            {seasons.map((season) => (
                <SeasonRow 
                    key={season}
                    season={season}
                    organizedKits={organizedKits}
                    showEmpty={showEmpty}
                    selectedTeamName={selectedTeamName}
                    user={user}
                />
            ))}
        </div>
    );
};

export default KitsGrid;

