import React from 'react';
import KitCard from '../../components/KitCard';

const KitsGrid = ({ kits, loading, selectedTeamName, user }) => {
    if (loading) return <div className="text-center py-5"><div className="spinner-border text-primary"></div></div>;
    if (kits.length === 0) return (
        <div className="text-center py-5 text-muted">
            <h4>No kits added for {selectedTeamName} yet.</h4>
            <p>Be the first to add one!</p>
        </div>
    );

    return (
        <div className="row g-4">
            {kits.map((item) => (
                <div key={item.id} className="col-12 col-sm-12 col-md-12 col-lg-6 col-xl-6 col-xxl-4 col-xxl-4">
                    <KitCard item={item} user={user} />
                </div>
            ))}
        </div>
    );
};

export default KitsGrid;