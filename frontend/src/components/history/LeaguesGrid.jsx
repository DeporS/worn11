import React from 'react';

const LeaguesGrid = ({ leagues, loading, onSelectLeague }) => {
    if (loading) return <div className="text-center w-100 py-5"><div className="spinner-border text-primary"></div></div>;
    if (leagues.length === 0) return <div className="text-center text-muted">No leagues found.</div>;

    // Grouping logic (moved here to keep the main file clean)
    const groupedLeagues = leagues.reduce((acc, league) => {
        const countryName = league.country?.name || "International / Other";
        if (!acc[countryName]) {
            acc[countryName] = { leagues: [], flag: league.country?.flag };
        }
        acc[countryName].leagues.push(league);
        return acc;
    }, {});

    const sortedCountries = Object.keys(groupedLeagues).sort();

    return (
        <div>
            {sortedCountries.map((countryName) => {
                const group = groupedLeagues[countryName];
                return (
                    <div key={countryName} className="mb-5">
                        {/* Country Header */}
                        <div className="d-flex align-items-center gap-3 mb-3 border-bottom pb-2">
                            {group.flag ? (
                                <img src={group.flag} alt={countryName} className="rounded-circle shadow-sm border country-flag-icon" />
                            ) : (
                                <div className="bg-light rounded-circle d-flex align-items-center justify-content-center border country-flag-placeholder">🌍</div>
                            )}
                            <h2 className="fw-bold m-0 text-dark">{countryName}</h2>
                        </div>

                        {/* Leagues Grid */}
                        <div className="row g-4">
                            {group.leagues.map((league) => (
                                <div key={league.id} className="col-12 col-md-6 col-lg-4 col-xl-3">
                                    <div 
                                        className="card h-100 shadow-sm border-0 text-white p-4 league-card position-relative overflow-hidden"
                                        style={{ backgroundColor: league.hex_color || '#6c757d' , willChange: 'transform' }}
                                        onClick={() => onSelectLeague(league)}
                                    >
                                        {/* Watermark */}
                                        {(league.logo || league.country?.flag) && (
                                            <img src={league.logo || league.country.flag} alt="" className="league-watermark" />
                                        )}
                                        <div className="d-flex flex-column h-100 justify-content-center position-relative z-1 text-center">
                                            <h3 className="fw-bold m-0 league-title">{league.name}</h3>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
};

export default LeaguesGrid;