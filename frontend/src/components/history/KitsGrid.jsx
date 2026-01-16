import React, { useMemo, useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import KitCard from '../../components/KitCard';

const SHIRT_TYPES = [
    { value: 'Home', label: 'Home' },
    { value: 'Away', label: 'Away' },
    { value: 'Third', label: 'Third' },
    { value: 'Fourth', label: 'Fourth' },
    { value: 'Cup', label: 'Cup' },
    { value: 'Training', label: 'Training' },
    { value: 'GK', label: 'Goalkeeper' },
];

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
            if (!map[season][type] || likes > (map[season][type].likes_count || 0)) {
                map[season][type] = userKit;
            }
        });
        return map;
    }, [kits]);

    const HorizontalScroll = ({ children, className, style }) => {
        const elRef = useRef(null);

        useEffect(() => {
            const el = elRef.current;
            if (el) {
                const onWheel = (e) => {
                    if (e.deltaY === 0) return;
                    
                    // To jest klucz - działa tylko z native event listener
                    e.preventDefault();
                    
                    // Przesuwamy w bok o tyle, ile użytkownik przewinął w pionie
                    el.scrollLeft += e.deltaY;
                };

                // { passive: false } pozwala zadziałać preventDefault()
                el.addEventListener('wheel', onWheel, { passive: false });

                return () => {
                    el.removeEventListener('wheel', onWheel);
                };
            }
        }, []);

        return (
            <div ref={elRef} className={className} style={style}>
                {children}
            </div>
        );
    };

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
            {seasons.map((season) => {
                const hasAnyKit = SHIRT_TYPES.some(t => organizedKits[season]?.[t.value]);
                if (!showEmpty && !hasAnyKit) return null;

                return (
                    <div key={season} className="mb-5">
                        {/* Season Header */}
                        <div className="d-flex align-items-center gap-3 mb-3">
                            <h3 className="m-0 fw-bold text-secondary" style={{ fontFamily: 'monospace', letterSpacing: '-1px' }}>
                                {season}
                            </h3>
                            <div className="flex-grow-1 border-bottom"></div>
                        </div>

                        {/* --- HORIZONTAL SCROLL (FIXED) --- */}
                        {/* d-flex: horizontal layout */}
                        {/* flex-nowrap: prevents wrapping to new line */}
                        {/* overflow-auto: adds scrollbar */}
                        <HorizontalScroll
                            className="d-flex flex-nowrap overflow-x-auto overflow-y-hidden gap-3 pb-5"
                            style={{ scrollbarWidth: 'thin', scrollBehavior: 'auto' }}
                        >
                            {SHIRT_TYPES.map((typeObj) => {
                                const bestKit = organizedKits[season]?.[typeObj.value];

                                if (!showEmpty && !bestKit) return null;

                                return (
                                    <div 
                                        key={`${season}-${typeObj.value}`} 
                                        style={{ minWidth: '240px', width: '240px', flex: '0 0 auto' }}
                                    >
                                        <div className="text-center mb-2">
                                            <span className={`badge rounded-pill ${bestKit ? 'bg-primary' : 'bg-light text-muted border'}`}>
                                                {typeObj.label}
                                            </span>
                                        </div>

                                        {bestKit ? (
                                            <div className="h-100">
                                                <KitCard item={bestKit} user={user} />
                                            </div>
                                        ) : (
                                            <Link 
                                                to="/add-kit" 
                                                className="d-block text-decoration-none bg-light border border-2 rounded p-4 text-center d-flex flex-column align-items-center justify-content-center h-100"
                                                style={{ 
                                                    borderStyle: 'dashed !important',
                                                    borderColor: '#dee2e6',
                                                    color: '#adb5bd',
                                                    minHeight: '280px',
                                                    transition: 'all 0.2s'
                                                }}
                                                title={`Add ${season} ${typeObj.label}`}
                                                state={{ prefill: { season, type: typeObj.value, team: selectedTeamName } }}
                                            >
                                                <div className="mb-2 fs-3 opacity-50">➕</div>
                                                <span className="fw-bold small">Missing</span>
                                                <span className="text-uppercase small opacity-75">
                                                    {typeObj.label}
                                                </span>
                                            </Link>
                                        )}
                                    </div>
                                );
                            })}
                        </HorizontalScroll>
                    </div>
                );
            })}
        </div>
    );
};

export default KitsGrid;