import React from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteKitFromCollection } from '../services/api';
import { useState } from 'react';
import Swal from 'sweetalert2';

import '../styles/profile.css';

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
                            style={{ width: '100px', height: '100px', objectFit: 'cover' }}
                        />
                    ))
                ) : (
                    <div className="bg-light d-flex align-items-center justify-content-center rounded"
                        style={{ width: '100px', height: '100px', minWidth: '100px' }}>
                        <small className="text-muted">No photo</small>
                    </div>
                )}
            </div>

            <div className="card-body">
                {/* Team Name && Estimated Value */}
                <div className="d-flex justify-content-between align-items-center mb-3 mt-0">
                    <div className="d-flex align-items-center" style={{ gap: '8px' }}>
                        {item.kit.team.logo && <img src={item.kit.team.logo} alt="Team Logo" style={{ height: '20px', marginTop: '2px' }} />}
                        <h5 className="card-title mb-0" title="Team">{item.kit.team.name}</h5>
                    </div>
                    <span className="badge-outline" title="Estimated Value">${item.final_value}</span>
                </div>
                
                {/* Season & Kit Type */}
                <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                    <span title="Season">{item.kit.season}</span>
                    <span title="Kit Type">{item.kit.kit_type}</span>
                </div>

                {/* Technology & Size */}
                <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                    <span title="Technology">{item.technology_display}</span>
                    <span title="Size">{item.size}</span>
                </div>

                {/** Condition & FREE SPACE*/}
                <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                    <span title="Condition">{item.condition_display}</span>
                </div>       

                {/* Edit and Delete Buttons */}
                <div className="d-flex justify-content-between mt-1 align-items-center">
                    
                    <div className="gap-2 d-flex">
                        {item.is_owner && (
                            <>
                        {/* Edit Button */}
                        <button
                            className="btn btn-sm edit-button"
                            onClick={handleEditClick}
                            title="Edit Kit"
                        >
                            ✏
                        </button>

                        {/* Delete Button */}
                        <button
                            className="btn btn-sm edit-button"
                            onClick={handleDeleteClick}
                            disabled={isDeleting} // Block button while deleting
                            title="Delete Kit"
                        >
                            {isDeleting ? (
                                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                            ) : (
                                <>
                                    🗑️
                                </>
                            )}
                        </button>
                            </>
                        )}
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