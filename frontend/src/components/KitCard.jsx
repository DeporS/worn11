import React from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteKitFromCollection } from '../services/api';
import { useState } from 'react';
import Swal from 'sweetalert2';

const KitCard = ({ item, onDeleteSuccess }) => {
    const navigate = useNavigate();
    const [isDeleting, setIsDeleting] = useState(false);

    const handleDeleteClick = async () => {
        Swal.fire({
            title: 'Are you sure?',
            text: "You won't be able to revert this!",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc3545', 
            cancelButtonColor: '#6c757d',
            confirmButtonText: 'Yes, delete it'
        }).then(async (result) => {
            if (result.isConfirmed) {
                try {
                    setIsDeleting(true);
                    await deleteKitFromCollection(item.id);
                    
                    Swal.fire(
                        'Deleted!',
                        'Your kit has been removed.',
                        'success'
                    );

                    if (onDeleteSuccess) onDeleteSuccess(item.id);
                } catch (error) {
                    setIsDeleting(false);
                    Swal.fire('Error!', 'Something went wrong.', 'error');
                }
            }
        });
};

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
                <div className="d-flex justify-content-between mt-3 align-items-center">
                    <div>
                        {/* Edit Button */}
                        <button 
                            className="btn btn-outline-primary btn-sm" 
                            onClick={handleEditClick}
                        >
                            <i className="bi bi-pencil-fill me-1"></i> Edit
                        </button>

                        {/* Delete Button */}
                        <button 
                            className="btn btn-outline-danger btn-sm"
                            onClick={handleDeleteClick}
                            disabled={isDeleting} // Block button while deleting
                        >
                            {isDeleting ? (
                                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                            ) : (
                                <>
                                    <i className="bi bi-trash-fill me-1"></i> Delete
                                </>
                            )}
                        </button>
                    </div>
                        
                    {/* Added At */}
                    <small className="text-muted" style={{ fontSize: '0.75rem' }}>
                        <i className="bi bi-clock me-1"></i>
                        {new Date(item.added_at).toLocaleDateString('en-GB', {
                            day: 'numeric',
                            month: 'short',
                            year: 'numeric',
                        })}
                    </small>
                </div>
                
            </div>
        </div>
    );
};

export default KitCard;