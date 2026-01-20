import { useState, useEffect, useRef, use } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { addKitToCollection } from '../services/api';
import api from '../services/api';
import { nanoid } from 'nanoid';

import '../styles/photos.css';

const AddShirtFormPage = () => {
    const navigate = useNavigate();
    const location = useLocation();

    // States from Backend
    const [sizeOptions, setSizeOptions] = useState([]);
    const [conditionOptions, setConditionOptions] = useState([]);
    const [technologyOptions, setTechnologyOptions] = useState([]);
    const [typeOptions, setTypeOptions] = useState([]);
    const [suggestions, setSuggestions] = useState([]);

    // Form States
    const [teamName, setTeamName] = useState('');
    const [season, setSeason] = useState('');
    const [kitType, setKitType] = useState('');
    const [size, setSize] = useState('');
    const [condition, setCondition] = useState('');
    const [technology, setTechnology] = useState('');
    const [forSale, setForSale] = useState(false);
    const [manualValue, setManualValue] = useState('');
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [playerName, setPlayerName] = useState('');
    const [playerNumber, setPlayerNumber] = useState('');
    const [offerLink, setOfferLink] = useState('');

    // Error states
    const [teamError, setTeamError] = useState(null);
    const [seasonError, setSeasonError] = useState(null);
    const [technologyError, setTechnologyError] = useState(null);
    const [typeError, setTypeError] = useState(null);
    const [sizeError, setSizeError] = useState(null);
    const [conditionError, setConditionError] = useState(null);
    const [printError, setPrintError] = useState(null);
    const [linkError, setLinkError] = useState(null);

    // UI States
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const isSelectionRef = useRef(false);
    const fileInputRef = useRef(null); // Ref for file input
    const teamInputRef = useRef(null); // Ref for team name input
    const seasonInputRef = useRef(null); // Ref for season input
    const technologyInputRef = useRef(null); // Ref for technology input
    const typeInputRef = useRef(null); // Ref for type input
    const sizeInputRef = useRef(null); // Ref for size input
    const conditionInputRef = useRef(null); // Ref for condition input
    const printInputRef = useRef(null); // Ref for print input
    const linkInputRef = useRef(null); // Ref for link input
    const [dragOverIndex, setDragOverIndex] = useState(null); // for drag and drop

    // User
    const [isPro, setIsPro] = useState(false);
    const MAX_PHOTOS = isPro ? 20 : 5;

    // Current year for season options
    const currentYear = new Date().getFullYear();
    const maxYear = currentYear + 1;

    // Refs for drag and drop
    const dragItem = useRef(null);
    const dragOverItem = useRef(null);

    // Handle sorting of photos
    const handleSort = () => {

        // create a copy of the items array
        let _selectedFiles = [...selectedFiles];

        // Remove and save the dragged item content
        const draggedItemContent = _selectedFiles.splice(dragItem.current, 1)[0];

        // Switch the position
        _selectedFiles.splice(dragOverItem.current, 0, draggedItemContent);

        // Reset the references
        dragItem.current = null;
        dragOverItem.current = null;

        // Update the actual array
        setSelectedFiles(_selectedFiles);
    };

    // Handle file selection
    const handleFileSelect = (e) => {
        if (e.target.files) {
            const rawFiles = Array.from(e.target.files);
            
            const newFiles = rawFiles.map(file => ({
                file: file,
                id: nanoid(),
                preview: URL.createObjectURL(file)
            }));

            const totalFiles = selectedFiles.length + newFiles.length;

            if (totalFiles > MAX_PHOTOS) {
                if (!isPro) {
                    alert("Free users are limited to 5 photos. Upgrade to PRO to upload up to 20! 🚀");
                    // LINK TO UPGRADE TO PRO PAGE CAN BE ADDED HERE
                } else {
                    alert(`You are PRO and can upload up to ${MAX_PHOTOS} photos.`);
                }
                return;
            }

            // Add new files to existing ones (do not overwrite)
            setSelectedFiles(prevFiles => [...prevFiles, ...newFiles]);
        }
        // Reset file input value to allow re-selection of the same file
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    // Remove photo by index
    const removePhoto = (indexToRemove) => {
        setSelectedFiles(prevFiles => prevFiles.filter((_, index) => index !== indexToRemove));
    };

    // Remove photo by id
    const removePhotoById = (id) => {
        setSelectedFiles(prev => {
            const fileToRemove = prev.find(f => f.id === id);
            if (fileToRemove) {
                URL.revokeObjectURL(fileToRemove.preview);
            }
            return prev.filter(item => item.id !== id);
        });
    };

    // Trigger hidden file input click
    const triggerFileInput = () => {
        fileInputRef.current.click();
    };

    useEffect(() => {
        api.get('/options/') 
            .then(response => {
                const { sizes, conditions, technologies, types } = response.data;
                
                setSizeOptions(sizes);
                setConditionOptions(conditions);
                setTechnologyOptions(technologies);
                setTypeOptions(types);
        })
        .catch(err => console.error("Failed to fetch options", err));

        api.get('/auth/user/')
            .then(res => {
                // Check if user is pro
                if (res.data.profile?.is_pro === true) {
                    setIsPro(true);
                }
            })
            .catch(err => console.log("User not logged in or fetch error"));
    }, []);

    // Fetch team suggestions when teamName changes
    useEffect(() => {

        // If the change was due to a selection, do not fetch
        if (isSelectionRef.current) {
            isSelectionRef.current = false; // Reset the flag for future changes
            return;
        }

        // if team name is less than 3 characters, do not fetch
        if (teamName.length < 3) {
            setSuggestions([]);
            return;
        }

        // Debounce fetch
        const timerId = setTimeout(() => {
            api.get(`teams/search/?q=${teamName}`)
                .then(res => {
                    const results = res.data;
                    setSuggestions(results);
                    
                    if (results.length === 1 && results[0].name.toLowerCase() === teamName.toLowerCase()) {
                        setShowSuggestions(false);
                    } else {
                        setShowSuggestions(true);
                    }
                })
        }, 300); // 300ms debounce

        return () => clearTimeout(timerId); // Cleanup on unmount or teamName change
    }, [teamName]); // Do when teamName changes

    // Errors handling
    useEffect(() => {
        const fields = [
            { error: teamError, ref: teamInputRef },
            { error: seasonError, ref: seasonInputRef },
            { error: technologyError, ref: technologyInputRef },
            { error: typeError, ref: typeInputRef },
            { error: sizeError, ref: sizeInputRef },
            { error: conditionError, ref: conditionInputRef },
            { error: printError, ref: printInputRef },
            { error: linkError, ref: linkInputRef },
        ];

        const firstErrorField = fields.find(f => f.error && f.ref.current);

        if (firstErrorField) {
            firstErrorField.ref.current.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center'
            });
            firstErrorField.ref.current.focus();
        }
    }, [teamError, seasonError, technologyError, typeError, sizeError, conditionError, printError, linkError]);

    // Prefill form if data is in location state (comes from museum missing kit link)
    useEffect(() => {
        if (location.state && location.state.prefill) {
            const { season, type, team } = location.state.prefill;

            // console.log("Prefilling form with:", season, type, team);

            if (season) setSeason(season);
            if (type) setKitType(type);
            if (team) setTeamName(team);
        }
    }, [location]);


    const handleSuggestionClick = (team) => {
        isSelectionRef.current = true; // Mark that a suggestion was selected

        setTeamName(team.name); // Fill input with selected suggestion
        setSuggestions([]);     // Clear suggestions list
        setShowSuggestions(false); // Hide suggestions list
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setPrintError(null);
        setTeamError(null);
        setSeasonError(null);
        setTechnologyError(null);
        setTypeError(null);
        setSizeError(null);
        setConditionError(null);
        setLinkError(null);

        // Basic validation

        if (!teamName.trim()) {
            setTeamError("Team Name is required.");
            setLoading(false);
            return;
        } else if (!season) {
            setSeasonError("Season is required.");
            setLoading(false);
            return;
        } else if (!technology) {
            setTechnologyError("Technology is required.");
            setLoading(false);
            return;
        } else if (!kitType) {
            setTypeError("Kit Type is required.");
            setLoading(false);
            return;
        } else if (!size) {
            setSizeError("Size is required.");
            setLoading(false);
            return;
        } else if (!condition) {
            setConditionError("Condition is required.");
            setLoading(false);
            return;
        }

        // Validate Player Name and Number
        if ((playerName.trim() !== "" && playerNumber.trim() === "") || 
            (playerName.trim() === "" && playerNumber.trim() !== "")) {
            setPrintError("Both Player Name and Number must be filled, or both empty.");
            setLoading(false);
            return;
        }

        // Validate offer link - prevent malicious strings
        const urlPattern = /^(http|https):\/\/[^ "]+$/;
        if (offerLink && !urlPattern.test(offerLink)) {
            setLinkError("Link must start with http:// or https://");
            setLoading(false);
            return;
        }

        const formData = new FormData();
        formData.append('team_name', teamName);
        formData.append('season', season);
        formData.append('kit_type', kitType);
        formData.append('size', size);
        formData.append('condition', condition);
        formData.append('shirt_technology', technology);
        formData.append('for_sale', forSale);
        formData.append('manual_value', manualValue);
        formData.append('player_name', playerName);
        formData.append('player_number', playerNumber);
        formData.append('offer_link', offerLink);
        
        selectedFiles.forEach((item) => {
            formData.append('images', item.file); 
        });

        try {
            await addKitToCollection(formData);
            // Success - Redirect to profile
            navigate('/my-collection');
        } catch (err) {
            console.error(err);
            setError('Something went wrong. Check console for details.');
            setLoading(false);
        }
    };



  return (
    <div className="container py-5">
      <div className="row justify-content-center">
        <div className="col-md-8 col-lg-6">
            
            <div className="card shadow border-0 overflow-hidden" style={{ borderRadius: '15px' }}>

                <div className="bg-primary bg-gradient" style={{ height: '8px' }}></div>

                    <div className="card-body p-4">
                        
                        <div className="text-center mb-5 mt-2">
                            <div 
                                className="d-inline-flex align-items-center justify-content-center bg-light rounded-circle mb-3 shadow-sm" 
                                style={{ width: '70px', height: '70px' }}
                            >
                                <i className="bi bi-plus-lg fs-2 text-primary"></i>
                            </div>
                            
                            <h3 className="fw-bold mb-1">Add New Kit</h3>
                            <p className="text-muted small">
                                Fill in the details to expand your collection
                            </p>
                        </div>

                        {error && (
                            <div className="alert alert-danger d-flex align-items-center rounded-3 mb-4" role="alert">
                                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                                <div>{error}</div>
                            </div>
                        )}

                        <form onSubmit={handleSubmit} noValidate>
                            {/* Basic Info */}
                            <div className="mb-4 p-3 rounded border bg-light border-light" style={{ transition: 'all 0.3s ease' }}>
            
                                <div className="d-flex align-items-center gap-2 mb-3 text-muted">
                                    <i className="bi bi-info-circle fs-5"></i>
                                    <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                        Basic Info
                                    </span>
                                </div>

                                {/* Team Name (Full Width) */}
                                <div className="mb-3 position-relative">
                                    <div className="form-floating">
                                        <input 
                                            ref={teamInputRef}
                                            type="text" 
                                            className={`form-control ${teamError ? 'is-invalid' : ''}`}
                                            id="floatingTeamName"
                                            required
                                            placeholder="FC Barcelona"
                                            value={teamName} 
                                            onChange={e => setTeamName(e.target.value)}
                                            autoComplete="off"
                                        />
                                        <label htmlFor="floatingTeamName">Team Name</label>
                                    </div>

                                    {/* Suggestions Dropdown */}
                                    {showSuggestions && suggestions.length > 0 && (
                                        <ul className="list-group position-absolute w-100 shadow mt-1" style={{ zIndex: 1000 }}>
                                            {suggestions.map((team) => (
                                                <li 
                                                    key={team.id} 
                                                    className="list-group-item list-group-item-action d-flex align-items-center gap-3"
                                                    style={{ cursor: 'pointer' }}
                                                    onClick={() => handleSuggestionClick(team)}
                                                >
                                                    {team.logo ? (
                                                        <img src={team.logo} alt={team.name} style={{ width: '30px', height: '30px', objectFit: 'contain' }} />
                                                    ) : (
                                                        <div style={{width: '30px', height: '30px', background: '#eee', borderRadius: '50%'}}></div>
                                                    )}
                                                    <span>{team.name}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}

                                    {/* Error */}
                                    {teamError && (
                                        <div className="text-danger mt-2 small d-flex align-items-center">
                                            <i className="bi bi-exclamation-circle me-1"></i>
                                            {teamError}
                                        </div>
                                    )}
                                </div>

                                {/* Season & Type (Row) */}
                                <div className="row g-2">
                                    {/* Season */}
                                    <div className="col-6">
                                        <div className="form-floating">
                                            <select
                                                ref={seasonInputRef}
                                                className={`form-select ${seasonError ? 'is-invalid' : ''}`}
                                                id="floatingSeason"
                                                required
                                                value={season}
                                                onChange={e => setSeason(e.target.value)}
                                            >
                                                <option value=""></option>
                                                {Array.from({ length: maxYear - 1940 }, (_, i) => {
                                                    const start = maxYear - i;
                                                    return <option key={start} value={`${start - 1}/${start}`}>{start - 1}/{start}</option>
                                                })}
                                            </select>
                                            <label htmlFor="floatingSeason">Season</label>
                                        </div>
                                        {/* Error */}
                                        {seasonError && (
                                            <div className="text-danger mt-2 small d-flex align-items-center">
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {seasonError}
                                            </div>
                                        )}
                                    </div>

                                    {/* Type */}
                                    <div className="col-6">
                                        <div className="form-floating">
                                            <select
                                                className={`form-select ${typeError ? 'is-invalid' : ''}`}
                                                id="floatingType"
                                                required
                                                value={kitType} 
                                                onChange={e => setKitType(e.target.value)}
                                                disabled={typeOptions.length === 0}
                                                ref={typeInputRef}
                                            >
                                                <option value="" disabled hidden/>
                                                {typeOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                                            </select>
                                            <label htmlFor="floatingType">Type</label>
                                        </div>
                                        {/* Error */}
                                        {typeError && (
                                            <div className="text-danger mt-2 small d-flex align-items-center">
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {typeError}
                                            </div>
                                        )}
                                    </div>

                                    
                                </div>
                            </div>

                            {/* Photos */}
                            <div className={`mb-4 p-3 rounded border ${printError ? 'border-danger bg-danger bg-opacity-10' : 'bg-light border-light'}`} 
                                style={{ transition: 'all 0.3s ease' }}>
                                <div className="mb-4">
                                    <div className="d-flex justify-content-between align-items-center mb-3">
                                        {/* <label className="form-label fw-bold m-0">Photos ({selectedFiles.length}/{MAX_PHOTOS})</label> */}
                                        <div className="d-flex align-items-center gap-2 text-muted">
                                            <i className="bi bi-camera fs-5"></i>
                                            <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                                Photos ({selectedFiles.length}/{MAX_PHOTOS})
                                            </span>
                                        </div>
                                        
                                        {!isPro && (
                                            <small
                                                className="text-primary"
                                            >
                                                <a 
                                                    href="/get-pro" 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className="pro-link"
                                                >
                                                    Need more? Go PRO 💎
                                                </a>
                                            </small>
                                        )}
                                    </div>

                                    {/* Hidden input */}
                                    <input 
                                        type="file" 
                                        ref={fileInputRef}
                                        className="d-none" 
                                        accept="image/*"
                                        multiple
                                        onChange={handleFileSelect} 
                                    />

                                    {/* Container for tiles */}
                                    <div
                                        className="p-2"
                                        style={{
                                            display: 'grid',
                                            gridTemplateColumns: 'repeat(5, 1fr)',
                                            gap: '10px',
                                            maxWidth: '100%',
                                        }}
                                    >
                                        <AnimatePresence mode="popLayout">
                                        
                                            {/* Mapping added photos */}
                                            {selectedFiles.map((item, index) => (
                                                <motion.div 
                                                    key={item.id} 
                                                    layout
                                                    draggable
                                                    onDragStart={(e) => {
                                                        dragItem.current = index;
                                                        e.dataTransfer.effectAllowed = "move"; // Show move cursor
                                                        e.dataTransfer.setData("text/html", e.target.parentNode);
                                                    }}
                                                    onDragEnter={(e) => {
                                                        dragOverItem.current = index;
                                                        setDragOverIndex(index);
                                                    }}
                                                    onDragEnd={() => {
                                                        handleSort();
                                                        setDragOverIndex(null);
                                                    }}
                                                    onDragOver={(e) => e.preventDefault()} // Necessary to allow drop

                                                    initial={{ opacity: 0, scale: 0.8 }} // Start 
                                                    animate={{ opacity: 1, scale: 1 }}   // Visible state
                                                    exit={{ opacity: 0, scale: 0.5 }}    // End (removal)
                                                    transition={{ duration: 0.3 }}       // Duration
                                                    className="photo-tile position-relative rounded shadow-sm overflow-hidden"
                                                    style={{ 
                                                        width: '100%',
                                                        aspectRatio: '3 / 4',
                                                        cursor: 'grab',
                                                        border: dragOverIndex === index ? '3px solid #0d6efd' : '1px solid #dee2e6',
                                                        backgroundColor: '#f8f9fa'
                                                    }}
                                                    whileDrag={{ cursor: 'grabbing' }}
                                                >
                                                    <img
                                                        src={item.preview}
                                                        alt="preview"
                                                        className="w-100 h-100" 
                                                        style={{
                                                            position: 'absolute', 
                                                            top: 0,
                                                            left: 0,
                                                            objectFit: 'cover',   
                                                            pointerEvents: 'none' 
                                                        }}
                                                    />

                                                    <div className="hover-overlay position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-dark bg-opacity-10"
                                                        style={{ pointerEvents: 'none' }}>
                                                        <i className="bi bi-arrows-move text-white fs-3 drop-shadow"></i>
                                                    </div>

                                                    <div
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            removePhotoById(item.id);
                                                        }}
                                                        style={{
                                                            position: 'absolute',
                                                            top: '1px',
                                                            right: '2px',
                                                            color: '#000000', 
                                                            fontWeight: 'bold',    
                                                            fontSize: '14px',
                                                            cursor: 'pointer',
                                                            zIndex: 10,
                                                            lineHeight: 1,
                                                            textShadow: '0 0 3px #fff'
                                                        }}
                                                    >
                                                        ✕
                                                    </div>
                                                        

                                                    {/* Photo number */}
                                                    <span className="position-absolute bottom-0 start-0 badge bg-dark bg-opacity-50" style={{fontSize: '9px', margin: '2px'}}>
                                                        {index + 1}
                                                    </span>
                                                </motion.div>
                                            ))}

                                            {/* PLUS Button */}
                                            {selectedFiles.length < MAX_PHOTOS && (
                                                <motion.div 
                                                    layout
                                                    key="add-photo-btn"
                                                    onClick={triggerFileInput} 
                                                    className="rounded border d-flex flex-column align-items-center justify-content-center text-muted bg-white"
                                                    style={{ 
                                                        width: '100%',
                                                        aspectRatio: '3 / 4',
                                                        cursor: 'pointer', 
                                                        borderStyle: 'dashed',
                                                        borderWidth: '2px'
                                                    }}
                                                >
                                                    <i className="bi bi-plus-lg fs-3"></i>
                                                    <small style={{ fontSize: '10px' }}>Add Photo</small>
                                                </motion.div>
                                            )}

                                            {/* Locked slots for FREE users */}
                                            {!isPro && selectedFiles.length >= 5 && (
                                                <motion.a
                                                    href="/get-pro"
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    layout
                                                    className="text-decoration-none"
                                                    style={{ width: '100%' }}
                                                    >
                                                    <motion.div 
                                                        layout
                                                        key="lock-photo-btn"
                                                        className="rounded border d-flex flex-column align-items-center justify-content-center text-muted bg-light opacity-50"
                                                        style={{ 
                                                            width: '100%',
                                                            aspectRatio: '3 / 4',
                                                            cursor: 'pointer', 
                                                            borderStyle: 'dashed',
                                                            borderWidth: '2px'
                                                        }}
                                                    >
                                                        <i className="bi bi-lock-fill fs-3 text-warning"></i>
                                                        <small style={{ fontSize: '10px' }}>Unlock PRO</small>
                                                    </motion.div>
                                                </motion.a>
                                            )}

                                        </AnimatePresence>

                                    </div>
                                </div>
                                
                                <div className="form-text mt-2">
                                    {!isPro
                                        ? `You can add up to ${MAX_PHOTOS} photos.`
                                        : `As a PRO member, enjoy adding up to ${MAX_PHOTOS} photos!`
                                    }
                                </div>
                            </div>
                            
                            {/* Type, Size & Condition */}
                            <div className="mb-4 p-3 rounded border bg-light border-light" style={{ transition: 'all 0.3s ease' }}>
                                
                                <div className="d-flex align-items-center gap-2 mb-3 text-muted">
                                    <i className="bi bi-tags fs-5"></i> 
                                    <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                        Kit Details
                                    </span>
                                </div>

                                <div className="row g-2">                                    
                                    {/* Size */}
                                    <div className="col-6">
                                        <div className="form-floating">
                                            <select 
                                                className={`form-select ${sizeError ? 'is-invalid' : ''}`}
                                                id="floatingSize"
                                                required
                                                value={size} 
                                                onChange={e => setSize(e.target.value)}
                                                disabled={sizeOptions.length === 0}
                                                ref={sizeInputRef}
                                            >
                                                <option value="" disabled hidden/>
                                                {sizeOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                                            </select>
                                            <label htmlFor="floatingSize">Size</label>
                                        </div>
                                        {/* Error */}
                                        {sizeError && (
                                            <div className="text-danger mt-2 small d-flex align-items-center">
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {sizeError}
                                            </div>
                                        )}
                                    </div>
                                    
                                    {/* Technology */}
                                    <div className="col-6">
                                        <div className="form-floating">
                                            <select 
                                                ref={technologyInputRef}
                                                className={`form-select ${technologyError ? 'is-invalid' : ''}`}
                                                id="floatingTech"
                                                required
                                                value={technology} 
                                                onChange={e => setTechnology(e.target.value)}
                                                disabled={technologyOptions.length === 0}
                                            >
                                                <option value="" disabled hidden/>
                                                {technologyOptions.map(opt => (
                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                ))}
                                            </select>
                                            <label htmlFor="floatingTech">Technology</label>
                                        </div>
                                        {/* Error */}
                                        {technologyError && (
                                            <div className="text-danger mt-2 small d-flex align-items-center">
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {technologyError}
                                            </div>
                                        )}
                                    </div>

                                    {/* Condition (Full Width below) */}
                                    <div className="col-12">
                                        <div className="form-floating">
                                            <select 
                                                className={`form-select ${conditionError ? 'is-invalid' : ''}`}
                                                id="floatingCondition"
                                                required
                                                value={condition} 
                                                onChange={e => setCondition(e.target.value)}
                                                disabled={conditionOptions.length === 0}
                                                ref={conditionInputRef}
                                            >
                                                <option value="" disabled hidden/>
                                                {conditionOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                                            </select>
                                            <label htmlFor="floatingCondition">Condition</label>
                                        </div>
                                        {/* Error */}
                                        {conditionError && (
                                            <div className="text-danger mt-2 small d-flex align-items-center">
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {conditionError}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Player Name and Number */}
                            <div className={`mb-4 p-3 rounded border ${printError ? 'border-danger bg-danger bg-opacity-10' : 'bg-light border-light'}`} 
                                style={{ transition: 'all 0.3s ease' }}>
                                
                                <div className="d-flex align-items-center gap-2 mb-3 text-muted">
                                    <i className="bi bi-person-badge fs-5"></i>
                                    <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                        Shirt Printing (Optional)
                                    </span>
                                </div>

                                <div className="row g-2">
                                    {/* Player Name */}
                                    <div className="col-8">
                                        <div className="form-floating">
                                            <input 
                                                type="text" 
                                                className={`form-control ${printError ? 'is-invalid' : ''}`}
                                                id="floatingPlayerName"
                                                placeholder="Messi"
                                                value={playerName} 
                                                onChange={e => {
                                                    setPlayerName(e.target.value);
                                                    if(printError) setPrintError(null);
                                                }}
                                            />
                                            <label htmlFor="floatingPlayerName">Player Name</label>
                                        </div>
                                    </div>
                                    
                                    {/* Player Number */}
                                    <div className="col-4">
                                        <div className="form-floating">
                                            <input 
                                                type="text" 
                                                className={`form-control ${printError ? 'is-invalid' : ''}`}
                                                id="floatingPlayerNum"
                                                placeholder="10"
                                                value={playerNumber} 
                                                onChange={e => {
                                                    setPlayerNumber(e.target.value);
                                                    if(printError) setPrintError(null);
                                                }}
                                            />
                                            <label htmlFor="floatingPlayerNum">Number</label>
                                        </div>
                                    </div>
                                </div>

                                {/* Error */}
                                {printError && (
                                    <div className="text-danger mt-2 small d-flex align-items-center">
                                        <i className="bi bi-exclamation-circle me-1"></i>
                                        {printError}
                                    </div>
                                )}
                            </div>
                            
                            {/* Value and For Sale */}
                            <div className="mb-4 p-3 rounded border bg-light border-light" style={{ transition: 'all 0.3s ease' }}>
                                
                                <div className="d-flex align-items-center gap-2 mb-3 text-muted">
                                    <i className="bi bi-cash-coin fs-5"></i>
                                    <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                        Estimated Value
                                    </span>
                                </div>

                                <div className="row g-2 align-items-center">
                                    {/* Price Input */}
                                    <div className="col-7">
                                        <div className="form-floating">
                                            <input 
                                                type="number"
                                                className="form-control"
                                                id="floatingPrice"
                                                placeholder="Auto"
                                                value={manualValue} 
                                                onChange={e => setManualValue(e.target.value)}
                                            />
                                            <label htmlFor="floatingPrice">Value ($)</label>
                                        </div>
                                    </div>

                                    {/* For Sale Switch */}
                                    <div className="col-5">
                                        <div className="h-100 d-flex align-items-center justify-content-center p-2 rounded bg-white border">
                                            <div className="form-check form-switch d-flex align-items-center gap-2 m-0">
                                                <input 
                                                    className="form-check-input my-0" 
                                                    type="checkbox" 
                                                    role="switch" 
                                                    id="forSaleCheck"
                                                    style={{ cursor: 'pointer', width: '3em', height: '1.5em' }}
                                                    checked={forSale} 
                                                    onChange={e => setForSale(e.target.checked)} 
                                                />
                                                <label className="form-check-label small fw-bold text-muted cursor-pointer" htmlFor="forSaleCheck">
                                                    {forSale ? <span className="text-success">FOR SALE</span> : "NOT FOR SALE"}
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div className="form-text mt-2 small">
                                    Leave value blank to auto-calculate.
                                </div>
                            </div>
                            
                            
                            {/* Offer Link */}
                            <div className={`mb-4 p-3 rounded border ${linkError ? 'border-danger bg-danger bg-opacity-10' : 'bg-light border-light'}`} 
                                style={{ transition: 'all 0.3s ease' }}>
                                
                                <div className="d-flex align-items-center gap-2 mb-3 text-muted">
                                    <i className="bi bi-link-45deg fs-4"></i>
                                    <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                        Offer link (Optional)
                                    </span>
                                </div>

                                <div className="row g-2">
                                    <div className="">
                                        <div className="form-floating">
                                            <input 
                                                type="url" 
                                                className={`form-control ${linkError ? 'is-invalid' : ''}`}
                                                id="floatingOfferLink"
                                                placeholder="https://example.com/offer"
                                                value={offerLink} 
                                                onChange={e => setOfferLink(e.target.value)}
                                            />
                                            <label htmlFor="floatingOfferLink">Full URL to where your kit is listed</label>
                                        </div>
                                    </div>
                                </div>

                                {/* Error */}
                                {linkError && (
                                    <div className="text-danger mt-2 small d-flex align-items-center">
                                        <i className="bi bi-exclamation-circle me-1"></i>
                                        {linkError}
                                    </div>
                                )}
                            </div>
                            

                            {/* Buttons */}
                            <div className="d-grid gap-2">
                                <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
                                    {loading
                                        ? 'Uploading...'
                                        : 'Add to Collection'}
                                </button>
                                <button type="button" className="btn btn-light" onClick={() => navigate('/my-collection')}>
                                    Cancel
                                </button>
                            </div>

                        </form>
                    </div>
                </div>

            </div>
        </div>
    </div>
  );
};

export default AddShirtFormPage;