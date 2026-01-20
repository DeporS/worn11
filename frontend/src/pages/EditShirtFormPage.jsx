import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../services/api';
import { nanoid } from 'nanoid';

import '../styles/photos.css';

const EditShirtFormPage = () => {
    const navigate = useNavigate();
    const { id } = useParams();

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
    const [deletedImageIds, setDeletedImageIds] = useState([]);

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
    const [initialLoading, setInitialLoading] = useState(true);
    const [error, setError] = useState(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    
    const isSelectionRef = useRef(false);
    const fileInputRef = useRef(null);
    const teamInputRef = useRef(null);
    const seasonInputRef = useRef(null);
    const technologyInputRef = useRef(null);
    const typeInputRef = useRef(null);
    const sizeInputRef = useRef(null);
    const conditionInputRef = useRef(null);
    const printInputRef = useRef(null);
    const linkInputRef = useRef(null);
    const [dragOverIndex, setDragOverIndex] = useState(null);

    // User
    const [isPro, setIsPro] = useState(false);
    const MAX_PHOTOS = isPro ? 20 : 5;

    // Refs for drag and drop
    const dragItem = useRef(null);
    const dragOverItem = useRef(null);

    // --- FETCHING DATA ---
    useEffect(() => {
        const fetchOptionsAndUser = async () => {
            try {
                const optionsRes = await api.get('/options/');
                const { sizes, conditions, technologies, types } = optionsRes.data;
                setSizeOptions(sizes);
                setConditionOptions(conditions);
                setTechnologyOptions(technologies);
                setTypeOptions(types);

                const userRes = await api.get('/auth/user/');
                if (userRes.data.profile?.is_pro === true) {
                    setIsPro(true);
                }
            } catch (err) {
                console.error("Failed to fetch options/user", err);
            }
        };

        const fetchKitDetails = async () => {
            try {
                const response = await api.get(`/my-collection/${id}/`);
                const data = response.data;
                const kit = data.kit; 
                
                isSelectionRef.current = true;

                setTeamName(kit.team.name);
                setSeason(kit.season);
                setKitType(kit.kit_type);
                setSize(data.size);
                setCondition(data.condition);
                setTechnology(data.shirt_technology);
                setForSale(data.for_sale);
                setManualValue(data.manual_value ? data.manual_value.toString() : '');
                setPlayerName(data.player_name || '');
                setPlayerNumber(data.player_number || '');
                setOfferLink(data.offer_link || '');

                if (data.images && Array.isArray(data.images)) {
                    const mappedImages = data.images.map(img => ({
                        id: img.id,          
                        preview: img.image,  
                        file: null,          
                        isExisting: true     
                    }));
                    setSelectedFiles(mappedImages);
                }

                setInitialLoading(false);
            } catch (err) {
                console.error("Failed to fetch kit details", err);
                setError("Could not load kit details.");
                setInitialLoading(false);
            }
        };

        fetchOptionsAndUser().then(() => fetchKitDetails());
    }, [id]);

    // Handle sorting of photos
    const handleSort = () => {
        let _selectedFiles = [...selectedFiles];
        const draggedItemContent = _selectedFiles.splice(dragItem.current, 1)[0];
        _selectedFiles.splice(dragOverItem.current, 0, draggedItemContent);
        dragItem.current = null;
        dragOverItem.current = null;
        setSelectedFiles(_selectedFiles);
    };

    // Handle file selection (New Photos)
    const handleFileSelect = (e) => {
        if (e.target.files) {
            const rawFiles = Array.from(e.target.files);
            
            const newFiles = rawFiles.map(file => ({
                file: file,
                id: nanoid(),
                preview: URL.createObjectURL(file),
                isExisting: false 
            }));

            const totalFiles = selectedFiles.length + newFiles.length;

            if (totalFiles > MAX_PHOTOS) {
                if (!isPro) {
                    alert("Free users are limited to 5 photos. Upgrade to PRO to upload up to 20! 🚀");
                } else {
                    alert(`You are PRO and can upload up to ${MAX_PHOTOS} photos.`);
                }
                return;
            }

            setSelectedFiles(prevFiles => [...prevFiles, ...newFiles]);
        }
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    // Remove photo logic (Old vs New)
    const removePhotoById = (id) => {
        const itemToRemove = selectedFiles.find(item => item.id === id);
        
        if (itemToRemove) {
            if (itemToRemove.isExisting) {
                setDeletedImageIds(prev => [...prev, itemToRemove.id]);
            } else {
                URL.revokeObjectURL(itemToRemove.preview);
            }
        }

        setSelectedFiles(prev => prev.filter(item => item.id !== id));
    };

    const triggerFileInput = () => {
        fileInputRef.current.click();
    };

    // Fetch team suggestions (Same as Add Page)
    useEffect(() => {
        if (isSelectionRef.current) {
            isSelectionRef.current = false;
            return;
        }
        if (teamName.length < 2) {
            setSuggestions([]);
            return;
        }
        const timerId = setTimeout(() => {
            api.get(`teams/search/?q=${teamName}`)
                .then(res => {
                    setSuggestions(res.data);
                    setShowSuggestions(true);
                })
        }, 300);
        return () => clearTimeout(timerId);
    }, [teamName]);

    // Error handling scrolling (Same as Add Page)
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
            firstErrorField.ref.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
            firstErrorField.ref.current.focus();
        }
    }, [teamError, seasonError, technologyError, typeError, sizeError, conditionError, printError, linkError]);

    const handleSuggestionClick = (team) => {
        isSelectionRef.current = true;
        setTeamName(team.name);
        setSuggestions([]);
        setShowSuggestions(false);
    };

    // --- SUBMIT (PATCH) ---
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
        if (!teamName.trim()) { setTeamError("Team Name is required."); setLoading(false); return; }
        else if (!season) { setSeasonError("Season is required."); setLoading(false); return; }
        else if (!technology) { setTechnologyError("Technology is required."); setLoading(false); return; }
        else if (!kitType) { setTypeError("Kit Type is required."); setLoading(false); return; }
        else if (!size) { setSizeError("Size is required."); setLoading(false); return; }
        else if (!condition) { setConditionError("Condition is required."); setLoading(false); return; }

        if ((playerName.trim() !== "" && playerNumber.trim() === "") || 
            (playerName.trim() === "" && playerNumber.trim() !== "")) {
            setPrintError("Both Player Name and Number must be filled, or both empty.");
            setLoading(false);
            return;
        }

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
        
        // --- COMPLEX IMAGE HANDLING FOR EDIT ---
        const fullOrder = [];
        let newImageIndex = 0;

        selectedFiles.forEach((item) => {
            if (item.isExisting) {
                fullOrder.push(item.id);
            } else if (item.file) {
                formData.append('new_images', item.file);
                fullOrder.push(`new_${newImageIndex}`);
                newImageIndex++;
            }
        });

        deletedImageIds.forEach(id => {
            formData.append('deleted_images', id);
        });

        formData.append('images_order', JSON.stringify(fullOrder));

        try {
            await api.patch(`/my-collection/${id}/`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            navigate('/my-collection');
        } catch (err) {
            console.error(err);
            setError('Something went wrong while updating. Check console.');
            setLoading(false);
        }
    };

    if (initialLoading) {
        return (
            <div className="container py-5 text-center">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2 text-muted">Loading kit details...</p>
            </div>
        );
    }

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
                                <i className="bi bi-pencil-fill fs-3 text-primary"></i>
                            </div>
                            
                            <h3 className="fw-bold mb-1">Edit Kit Details</h3>
                            <p className="text-muted small">
                                Update the details of your shirt
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
                                                {Array.from({ length: 2026 - 1940 }, (_, i) => {
                                                    const start = 2026 - i
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
                                        <div className="d-flex align-items-center gap-2 text-muted">
                                            <i className="bi bi-camera fs-5"></i>
                                            <span className="fw-bold text-uppercase" style={{ fontSize: '0.75rem', letterSpacing: '1px' }}>
                                                Photos ({selectedFiles.length}/{MAX_PHOTOS})
                                            </span>
                                        </div>
                                        
                                        {!isPro && (
                                            <small className="text-primary">
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
                                                        e.dataTransfer.effectAllowed = "move"; 
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
                                                    onDragOver={(e) => e.preventDefault()} 

                                                    initial={{ opacity: 0, scale: 0.8 }} 
                                                    animate={{ opacity: 1, scale: 1 }} 
                                                    exit={{ opacity: 0, scale: 0.5 }} 
                                                    transition={{ duration: 0.3 }} 
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
                                                    
                                                    {/* Badge NEW vs OLD */}
                                                    {!item.isExisting && (
                                                        <span className="position-absolute top-0 start-0 badge bg-success" style={{fontSize: '8px', margin: '2px'}}>NEW</span>
                                                    )}

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
                                        ? 'Saving Changes...'
                                        : 'Save Changes'}
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

export default EditShirtFormPage;