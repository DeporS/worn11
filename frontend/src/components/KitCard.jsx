import React from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteKitFromCollection, toggleLike } from '../services/api';
import { useState, useEffect } from 'react';
import Swal from 'sweetalert2';

import '../styles/profile.css';

const KitCard = ({ item, onDeleteSuccess, user }) => {
    const navigate = useNavigate();
    const [isDeleting, setIsDeleting] = useState(false);
    const [selectedImageIndex, setSelectedImageIndex] = useState(null);

    // Like state
    const [isLiked, setIsLiked] = useState(() => {
        return !!item.is_liked;
    });
    const [likesCount, setLikesCount] = useState((item.likes_count) || 0);
    const [likeLoading, setLikeLoading] = useState(false);

    const handleLike = async (e) => {
        e.stopPropagation();

        if (!user) {
            Swal.fire({
                title: 'You need to log in!',
                text: 'Only logged-in users can like kits.',
                icon: 'info',
                confirmButtonColor: '#3085d6',
                confirmButtonText: 'Ok'
            }).then((result) => {
                if (result.isConfirmed) {

                }
            });
            return;
        }

        if (likeLoading) return;

        // Remember previous state
        const prevLiked = isLiked;
        const prevCount = likesCount;

        // Optimistic update - if like, increment count, else decrement
        const newLiked = !prevLiked;
        const newCount = newLiked ? prevCount + 1 : prevCount - 1;

        setIsLiked(newLiked);
        setLikesCount(newCount < 0 ? 0 : newCount); // Prevent negative count

        try {
            setLikeLoading(true);
            const data = await toggleLike(item.id);
            
            // Synchronize state with backend response
            setIsLiked(data.liked);
            setLikesCount(data.likes_count);
            
            // Debuging
            // console.log("Odpowiedź serwera:", data);

        } catch (error) {
            console.error("Błąd lajkowania:", error);
            // Revert to previous state on error
            setIsLiked(prevLiked);
            setLikesCount(prevCount);
        } finally {
            setLikeLoading(false);
        }
    };

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

    const handleNext = (e) => {
        e.stopPropagation(); // Dont close the modal when clicking next
        setSelectedImageIndex((prevIndex) => {
            return prevIndex + 1;
        });
    };

    const handlePrev = (e) => {
        e.stopPropagation();
        setSelectedImageIndex((prevIndex) => {
            return prevIndex - 1;
        });
    };

    // Keyboard handling (arrows)
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (selectedImageIndex === null) return; // if modal is closed, do nothing

            if (e.key === 'ArrowRight') handleNext(e);
            if (e.key === 'ArrowLeft') handlePrev(e);
            if (e.key === 'Escape') setSelectedImageIndex(null);
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedImageIndex]); // Start listening when modal state changes

    // Get the current image based on the index
    const activeImage = selectedImageIndex !== null ? item.images[selectedImageIndex] : null;

    return (
        <>
            <div className="card h-100 shadow-sm border-0 kit-card-relative">

                {item.for_sale && (
                    <div className="ribbon">
                        For Sale
                    </div>
                )}

                {/* Gallery of photos */}
                <div
                    className="p-2 d-flex custom-scrollbar"
                    style={{
                        gap: '2px',
                        scrollSnapType: 'x mandatory',
                        scrollPaddingLeft: '8px',
                        maxWidth: '100%',
                        scrollBehavior: 'smooth',
                        overflowX: 'scroll',
                    }}
                    onWheel={(e) => {
                        const el = e.currentTarget;
                        const canScrollHorizontally = el.scrollWidth > el.clientWidth;

                        if (canScrollHorizontally) {
                            e.preventDefault();
                            el.scrollLeft += e.deltaY;
                        }
                    }}
                >
                    {item.images.length > 0 ? (
                        item.images.map((photo, index) => (
                            <img
                                key={photo.id}
                                src={photo.image}
                                alt="Kit"
                                className="rounded gallery-img"
                                onClick={() => setSelectedImageIndex(index)}
                                style={{
                                    width: 'calc(25% - 2px)',
                                    minWidth: 'calc(25% - 2px)',
                                    maxWidth: 'calc(25% - 2px)',
                                    aspectRatio: '3 / 4',
                                    objectFit: 'cover',
                                    scrollSnapAlign: 'start',
                                }}
                            />
                        ))
                    ) : (
                        <div className="bg-light d-flex align-items-center justify-content-center rounded"
                            style={{
                                width: 'calc(25% - 2px)',
                                minWidth: 'calc(25% - 2px)',
                                maxWidth: 'calc(25% - 2px)',
                                aspectRatio: '3 / 4',
                                objectFit: 'cover',
                                scrollSnapAlign: 'start'
                            }}
                        >
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

                    {/* Kit Details */}
                    <div className="kit-info p-2">
                        {/* Season & Kit Type */}
                        <div className="d-flex justify-content-between text-muted small mb-1">
                            <span title="Season">{item.kit.season}</span>
                            <span title="Kit Type">{item.kit.kit_type}</span>
                        </div>

                        {/* Technology & Size */}
                        <div className="d-flex justify-content-between text-muted small mb-1 mt-1">
                            <span title="Technology">{item.technology_display}</span>
                            <span title="Size">{item.size}</span>
                        </div>

                        {/* Condition & Player */}
                        <div className="d-flex justify-content-between text-muted small mt-1">
                            <span title="Condition">{item.condition_display}</span>
                            <span title="Player">{item.player_name} {item.player_number}</span>
                        </div>
                    </div>
                    
                    {/* Contact Owner & View Offer + Edit/Delete Buttons */}
                    <div className="d-flex justify-content-between mt-1 align-items-center">
                        {/*Contact Owner & View Offer Links*/}
                        <div className="d-flex flex-column">
                            {/* Contact Owner Link */}
                            <a
                                href={item.externalUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="minimal-offer-link"
                            >
                                <span>Contact Owner</span>
                                <span className="arrow-icon">✉︎</span>
                            </a>
                            {/* View Offer Link */}
                            {item.for_sale ? (
                                <a
                                    href={item.externalUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="minimal-offer-link"
                                >
                                    <span>View offer</span>
                                    <span className="arrow-icon">➚</span>
                                </a>
                            ) : (
                                <a className="minimal-not-for-sale-link">
                                    <span>Not for sale</span>
                                    <span className="arrow-icon">⨂</span>
                                </a>
                            )}
                        </div>
                        
                        {/* Edit and Delete Buttons */}
                        <div className="gap-2 d-flex">
                            {item.is_owner && (
                                <>
                                    {/* Edit Button */}
                                    <button
                                        className="btn btn-sm edit-button"
                                        onClick={handleEditClick}
                                        title="Edit"
                                    >
                                        ✏
                                    </button>

                                    {/* Delete Button */}
                                    <button
                                        className="btn btn-sm edit-button"
                                        onClick={handleDeleteClick}
                                        disabled={isDeleting} // Block button while deleting
                                        title="Delete"
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

                            {/* Share Button */}
                            <button
                                className="btn btn-sm edit-button"
                                // onClick={handleShareClick}
                                title="Share"
                            >
                                🔗
                            </button>
                        </div>
                        
                    </div>

                    {/* Likes and Added At */}
                    <div className="d-flex justify-content-between mt-1 align-items-center">

                        {/* Likes */}
                        <div className="d-flex align-items-center" style={{ gap: '5px' }}>
                            <button 
                                className="btn btn-link p-0 text-decoration-none" 
                                onClick={handleLike}
                                style={{ border: 'none', outline: 'none', boxShadow: 'none' }}
                            >
                                {isLiked ? (
                                    <i className="bi bi-heart-fill text-danger fs-5"></i> // Full heart
                                ) : (
                                    <i className="bi bi-heart text-muted fs-5"></i> // Empty heart
                                )}
                            </button>
                            <span className="small text-muted">
                                {/* If likesCount is NaN or null, show 0 */}
                                {Number.isNaN(likesCount) || likesCount === null ? 0 : likesCount}
                            </span>
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

            {/* Modal for selected image */}
            {activeImage && (
                <div
                    className="lightbox-backdrop"
                    onClick={() => setSelectedImageIndex(null)}
                >
                    <button className="lightbox-close-btn">&times;</button>

                    {/* ARROW LEFT IF MORE THAN ONE IMAGE, AND NOT FIRST IMAGE */}
                    {item.images.length > 1 && selectedImageIndex > 0 && (
                        <button className="lightbox-nav-btn nav-prev" onClick={handlePrev}>
                            &#10094; {/* sign id < */}
                        </button>
                    )}

                    <div class="lightbox-frame">
                        <img
                            src={activeImage.image}
                            alt="Enlarged view"
                            className="lightbox-img"
                            onClick={(e) => e.stopPropagation()}
                        />
                    </div>


                    {/* ARROW RIGHT IF MORE THAN ONE IMAGE, AND NOT LAST IMAGE */}
                    {item.images.length > 1 && selectedImageIndex !== item.images.length - 1 && (
                        <button className="lightbox-nav-btn nav-next" onClick={handleNext}>
                            &#10095; {/* sign id > */}
                        </button>
                    )}
                </div>

            )}
        </>
    );
};

export default KitCard;