import React from 'react';
import { useNavigate } from 'react-router-dom';

const KitCard = ({ item }) => {
    const navigate = useNavigate();

    const handleEditClick = () => {
        navigate(`/edit-kit/${item.id}`); // navigate to /edit-kit/15
    };

    return (
        <div className="card h-100 shadow-sm border-0 kit-card-relative">

            {item.for_sale && (
                <div className="ribbon">
                    For Sale
                </div>
            )}

            {/* Gallery of photos */}
            <div className="d-flex overflow-auto p-2" style={{ gap: '5px' }}>
                {item.images.length > 0 ? (
                    item.images.map(photo => (
                        <img 
                            key={photo.id} 
                            src={photo.image} 
                            alt="Kit"
                            className="rounded"
                            style={{width: '100px', height: '100px', objectFit: 'cover'}}
                        />
                    ))
                ) : (
                  <div className="bg-light d-flex align-items-center justify-content-center rounded" 
                          style={{width: '100px', height: '100px', minWidth: '100px'}}>
                      <small className="text-muted">No photo</small>
                  </div>
            )}
            </div>

            <div className="card-body">
                {/* Team Name */}
                <h5 className="card-title">{item.kit.team.name}</h5>

                {/* Season & Kit Type */}
                <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                    <span>{item.kit.season}</span>
                    <span>{item.kit.kit_type}</span>
                </div>

                {/* Technology & Size */}
                <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                    <span>{item.technology_display}</span>
                    <span>{item.size}</span>
                </div>
                
                {/* Condition */}
                <p className="card-text text-muted small mb-1 mt-1">{item.condition_display}</p>

                {/* Final Value */}
                <span className="badge bg-success fs-6 mt-1">{item.final_value} USD</span>

                {/* Edit and Delete Buttons */}
                <div className="d-flex justify-content-between mt-3">
                    
                    {/* Edit Button */}
                    <button 
                        className="btn btn-outline-primary btn-sm" 
                        onClick={handleEditClick}
                    >
                        <i className="bi bi-pencil-fill me-1"></i> Edit
                    </button>

                    {/* Delete Button
                    <button className="btn btn-outline-danger btn-sm">
                        <i className="bi bi-trash"></i>
                    </button> */}
                </div>
                
            </div>
        </div>
    );
};

export default KitCard;