import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import KitCardHistory from './KitCardHistory';

import '../../styles/history.css';

const SHIRT_TYPES = [
    { value: 'Home', label: 'Home' },
    { value: 'Away', label: 'Away' },
    { value: 'GK', label: 'Goalkeeper' },
    { value: 'Third', label: 'Third' },
    { value: 'Fourth', label: 'Fourth' },
    { value: 'Cup', label: 'Cup' },
    { value: 'Training', label: 'Training' },
    { value: 'Special', label: 'Special' },
];

const SeasonRow = ({ season, organizedKits, showEmpty, selectedTeamName, user }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    // Default items per row
    const [itemsPerRow, setItemsPerRow] = useState(5);

    // Responsiveness
    useEffect(() => {
        const handleResize = () => {
            const width = window.innerWidth;

            if (width < 576) {
                setItemsPerRow(2); // Mobile
            } else if (width < 768) {
                setItemsPerRow(2); // Small devices
            } else if (width < 992) {
                setItemsPerRow(3); // Tablet
            } else if (width < 1200) {
                setItemsPerRow(4); // Laptop
            } else {
                setItemsPerRow(5); // Desktop
            }
        };

        // Run on load
        handleResize();

        // Listen for window resize
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);


    // DISPLAY LOGIC 
    const hasAnyKit = SHIRT_TYPES.some(t => organizedKits[season]?.[t.value]);
    if (!showEmpty && !hasAnyKit) return null;

    // Slice the array depending on the screen size
    const visibleTypes = isExpanded ? SHIRT_TYPES : SHIRT_TYPES.slice(0, itemsPerRow);

    // Show the button only if there are more types than fit in one row
    const hasMore = SHIRT_TYPES.length > itemsPerRow;

    return (
        <div className="mb-5">
            {/* Season headline */}
            <div className="d-flex align-items-center gap-3 mb-3">
                <h3 className="m-0 fw-bold text-dark" style={{ fontFamily: 'monospace', letterSpacing: '-1px' }}>
                    {season}
                </h3>
                <div className="flex-grow-1 border-bottom"></div>
            </div>

            {/* Kits Grid */}
            <div className="row g-2 g-md-3 row-cols-2 row-cols-md-3 row-cols-lg-4 row-cols-xl-5">
                {visibleTypes.map((typeObj) => {
                    const bestKit = organizedKits[season]?.[typeObj.value];

                    // If we hide empty and this specific kit is missing -> skip slot
                    if (!showEmpty && !bestKit) return null;

                    return (
                        <div key={`${season}-${typeObj.value}`} className="col d-flex justify-content-center">
                            <div
                                key={`${season}-${typeObj.value}`}
                                className="d-flex flex-column h-100 w-100"
                                style={{ minHeight: '240px' }}
                            >
                                <div className="text-center mb-2">
                                    <span className={`badge rounded-pill ${bestKit ? 'bg-primary' : 'bg-light text-muted border'}`}>
                                        {typeObj.label}
                                    </span>
                                </div>

                                {bestKit ? (
                                    <div className="">
                                        <KitCardHistory item={bestKit} user={user} />
                                    </div>
                                ) : (
                                    <div className="d-flex flex-grow-1 align-items-center justify-content-center p-3">
                                        <Link
                                            to="/add-kit"
                                            className="add-missing-card"
                                            title={`Add ${season} ${typeObj.label}`}
                                            state={{ prefill: { season, type: typeObj.value, team: selectedTeamName } }}
                                            style={{ minHeight: '100%' }}
                                        >
                                            <span className="add-missing-text">
                                                + Add missing kit
                                            </span>
                                        </Link>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Show More / Less */}
            {hasMore && showEmpty && (
                <div className="text-center mt-3">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="btn btn-sm btn-outline-secondary rounded-pill px-4"
                    >
                        {isExpanded ? (
                            <>
                                Hide <i className="bi bi-chevron-up ms-1"></i>
                            </>
                        ) : (
                            <>
                                Show More ({SHIRT_TYPES.length - itemsPerRow} types) <i className="bi bi-chevron-down ms-1"></i>
                            </>
                        )}
                    </button>
                </div>
            )}
        </div>
    );
};

export default SeasonRow;