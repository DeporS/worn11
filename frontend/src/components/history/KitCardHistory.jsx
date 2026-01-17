import React from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { deleteKitFromCollection, toggleLike } from '../../services/api';
import { useState, useEffect, useRef } from 'react';
import Swal from 'sweetalert2';

import '../../styles/profile.css';

const KitCardHistory = ({ item, onDeleteSuccess, user }) => {
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

    const getEbayLink = (e) => {
        e.stopPropagation(); // Prevent card click

        // Construct eBay search URL
        // 1. QUERY
        const rawTeamName = item.kit?.team?.name || "";
        
        // Special cleaning for team names
        const teamName = rawTeamName
            .replace(/\./g, "")
            .replace(/^(FC|CF|AFC|SC|AC)\s+/i, "") // prefix
            .replace(/\s+(FC|CF|AFC|SC|AC)$/i, "") // suffix
            .trim();

        const season = item.kit?.season || "";
        const type = item.kit?.kit_type || "";
        
        const searchQuery = `${teamName} ${season} ${type} shirt`;
        const encodedQuery = encodeURIComponent(searchQuery);

        // 2. AFFILIATE LINK
       
        const affiliateBaseUrl = "https://www.ebay.com/sch/i.html?_nkw="; // <--- CHANGE THIS
        
        const finalUrl = `${affiliateBaseUrl}${encodedQuery}`;

        window.open(finalUrl, '_blank');
    };

    // Get the current image based on the index
    const activeImage = selectedImageIndex !== null ? item.images[selectedImageIndex] : null;

    const mainImage = item.images.length > 0 ? item.images[0].image : null;

    return (
        <>
            <div className="card h-100 shadow-sm border-0 kit-card-relative d-flex flex-column">

                {/* Main photo */}
                <div 
                    className="p-2" 
                    style={{ cursor: 'pointer' }}
                    onClick={() => {
                        if (item.images.length > 0) setSelectedImageIndex(0);
                    }}
                >
                    {mainImage ? (
                        <div className="position-relative">
                            <img
                                src={mainImage}
                                alt="Kit"
                                className="rounded"
                                style={{
                                    width: '100%',
                                    aspectRatio: '3 / 4',
                                    objectFit: 'cover',
                                    display: 'block'
                                }}
                            />
                            {/* Badge showing number of photos if more than 1 */}
                            {item.images.length > 1 && (
                                <div 
                                    className="position-absolute bottom-0 end-0 m-2 badge bg-dark bg-opacity-75"
                                    style={{ fontSize: '0.7rem' }}
                                >
                                    <i className="bi bi-images me-1"></i>
                                    {item.images.length}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div 
                            className="bg-light d-flex align-items-center justify-content-center rounded text-muted"
                            style={{ width: '100%', aspectRatio: '3 / 4' }}
                        >
                            <small>No photo</small>
                        </div>
                    )}
                </div>
                
                <div className="card-body d-flex flex-column mt-auto pt-0 p-3">
                    
                    {/* Likes and Added At */}
                    <div className="d-flex justify-content-between align-items-center mb-2">

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
                        
                        <div>
                            {/* Owner */}
                            <small className="me-2" style={{ fontSize: '0.75rem' }}>
                                <Link 
                                    to={`/profile/${item.owner_username}`} 
                                    className="text-muted text-decoration-none"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <i className="bi bi-person me-1"></i>
                                    {item.owner_username}
                                </Link>
                            </small>
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
                    
                    {/* Voting */}
                    <div>
                        <span className="fw-bold"></span>
                    </div>

                    {/* EBAY Button */}
                    <div className="mt-auto">
                        <button
                            onClick={getEbayLink}
                            className="btn w-100 rounded-pill d-flex align-items-center justify-content-center gap-2 ebay-btn"
                            title="Find this kit on eBay"
                        >
                            <span className="fw-bold">Find on eBay</span>
                            <i className="bi bi-search"></i> 
                        </button>
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

                    <div className="lightbox-frame">
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

export default KitCardHistory;