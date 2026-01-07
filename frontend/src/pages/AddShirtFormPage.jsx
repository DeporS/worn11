import { useState, useEffect, useRef, use } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { addKitToCollection } from '../services/api';
import api from '../services/api';
import { nanoid } from 'nanoid';

import '../styles/photos.css';

const AddShirtFormPage = () => {
    const navigate = useNavigate();

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

    // UI States
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const isSelectionRef = useRef(false);
    const fileInputRef = useRef(null); // Ref for file input
    const [dragOverIndex, setDragOverIndex] = useState(null); // for drag and drop

    // User
    const [isPro, setIsPro] = useState(false);
    const MAX_PHOTOS = isPro ? 20 : 5;

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
                if (res.data.is_pro === true) {
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

        // if team name is less than 2 characters, do not fetch
        if (teamName.length < 2) {
            setSuggestions([]);
            return;
        }

        // Debounce fetch
        const timerId = setTimeout(() => {
            api.get(`teams/search/?q=${teamName}`)
                .then(res => {
                    setSuggestions(res.data);
                    setShowSuggestions(true);
                })
        }, 300); // 300ms debounce

        return () => clearTimeout(timerId); // Cleanup on unmount or teamName change
    }, [teamName]); // Do when teamName changes

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

        const formData = new FormData();
        formData.append('team_name', teamName);
        formData.append('season', season);
        formData.append('kit_type', kitType);
        formData.append('size', size);
        formData.append('condition', condition);
        formData.append('shirt_technology', technology);
        formData.append('for_sale', forSale);
        formData.append('manual_value', manualValue);
        
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
            
          <div className="card shadow-sm border-0">
            <div className="card-body p-4">
                <h3 className="mb-4 fw-bold">Add New Kit to Collection ➕</h3>
                
                {error && <div className="alert alert-danger">{error}</div>}

                <form onSubmit={handleSubmit}>
                    {/* Team */}
                    <div className="mb-3 position-relative">
                        <label className="form-label">Team Name</label>
                        <input 
                            type="text" 
                            className="form-control" 
                            required
                            placeholder=""
                            value={teamName} 
                            onChange={e => setTeamName(e.target.value)}
                            autoComplete="off"
                        />
                        {/* Suggestions Dropdown */}
                        {showSuggestions && suggestions.length > 0 && (
                            <ul className="list-group position-absolute w-100 shadow" style={{ zIndex: 1000, top: '100%' }}>
                                {suggestions.map((team) => (
                                    <li 
                                        key={team.id} 
                                        className="list-group-item list-group-item-action d-flex align-items-center gap-3"
                                        style={{ cursor: 'pointer' }}
                                        onClick={() => handleSuggestionClick(team)}
                                    >
                                        {/* LOGO */}
                                        {team.logo ? (
                                            <img 
                                                src={team.logo} 
                                                alt={team.name} 
                                                style={{ width: '30px', height: '30px', objectFit: 'contain' }} 
                                            />
                                        ) : (
                                            <div style={{width: '30px', height: '30px', background: '#eee', borderRadius: '50%'}}></div>
                                        )}
                                        
                                        {/* TEAM NAME */}
                                        <span>{team.name}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>

                    {/* Season */}
                    <div className="mb-3">
                        <label className="form-label">Season</label>
                        <select
                            className="form-select"
                            required
                            value={season}
                            onChange={e => setSeason(e.target.value)}
                        >
                            <option value=""></option>
                            {Array.from({ length: 2026 - 1960 }, (_, i) => {
                            const start = 2026 - i
                            return (
                                <option key={start} value={`${start - 1}/${start}`}>
                                {start - 1}/{start}
                                </option>
                            )
                            })}
                        </select>
                    </div>

                    {/* Technology */}
                    <div className="mb-3">
                        <label className="form-label">Shirt Technology</label>
                        <select 
                            className="form-select" 
                            required
                            value={technology} 
                            onChange={e => setTechnology(e.target.value)}
                            disabled={technologyOptions.length === 0} // Disable before options load
                        >
                            <option value="" disabled hidden/>

                            {technologyOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Type and Size (in one row) */}
                    <div className="row">

                        {/* Type */}
                        <div className="col-6 mb-3">
                            <label className="form-label">Type</label>
                            <select 
                                className="form-select" 
                                required
                                value={kitType} 
                                onChange={e => setKitType(e.target.value)}
                                disabled={typeOptions.length === 0} // Disable before options load
                            >
                                <option value="" disabled hidden/>

                                {typeOptions.map(option => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        
                        {/* Size */}
                        <div className="col-6 mb-3">
                            <label className="form-label">Size</label>
                            <select 
                                className="form-select" 
                                required
                                value={size} 
                                onChange={e => setSize(e.target.value)}
                                disabled={sizeOptions.length === 0} // Disable before options load
                            >
                                <option value="" disabled hidden/>

                                {sizeOptions.map(option => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {/* Condition */}
                    <div className="mb-3">
                        <label className="form-label">Condition</label>
                        <select 
                            className="form-select" 
                            required
                            value={condition} 
                            onChange={e => setCondition(e.target.value)}
                            disabled={conditionOptions.length === 0} // Disable before options load
                        >
                            <option value="" disabled hidden/>

                            {conditionOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Photos */}
                    <div className="mb-4">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <label className="form-label fw-bold m-0">Photos ({selectedFiles.length}/{MAX_PHOTOS})</label>
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
                            className="d-flex flex-wrap align-items-start"
                            style={{ gap: '16px' }}
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
                                        className="photo-tile position-relative"
                                        style={{ 
                                            width: '100px', 
                                            height: '100px', 
                                            cursor: 'grab',
                                            border: dragOverIndex === index ? '2px solid #0d6efd' : 'none',
                                            borderRadius: '0.375rem' 
                                        }}
                                        whileDrag={{ cursor: 'grabbing' }}
                                    >
                                        <img 
                                            src={item.preview} 
                                            alt="preview" 
                                            className="rounded border shadow-sm w-100 h-100"
                                            style={{ objectFit: 'cover', pointerEvents: 'none' }}
                                        />

                                        <div className="hover-overlay position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-dark bg-opacity-10"
                                            style={{ pointerEvents: 'none' }}>
                                            <i className="bi bi-arrows-move text-white fs-3 drop-shadow"></i>
                                        </div>

                                        <button
                                            type="button"
                                            className="btn btn-danger btn-sm position-absolute top-0 end-0 rounded-circle p-0 d-flex align-items-center justify-content-center"
                                            style={{ width: '20px', height: '20px', transform: 'translate(30%, -30%)', zIndex: 10 }}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removePhotoById(item.id)
                                            }}
                                        >
                                            <span style={{ fontSize: '12px', lineHeight: 1 }}>&times;</span>
                                        </button>

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
                                        className="rounded border border-2 d-flex flex-column align-items-center justify-content-center text-muted bg-light"
                                        style={{ width: '100px', height: '100px', cursor: 'pointer', borderStyle: 'dashed' }}
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
                                        >
                                        <motion.div 
                                            layout
                                            key="lock-photo-btn"
                                            className="rounded border border-2 d-flex flex-column align-items-center justify-content-center text-muted bg-light opacity-50"
                                            style={{ width: '100px', height: '100px', cursor: 'pointer', borderStyle: 'dashed' }}
                                        >
                                            <i className="bi bi-lock-fill fs-3 text-warning"></i>
                                            <small style={{ fontSize: '10px' }}>Unlock PRO</small>
                                        </motion.div>
                                    </motion.a>
                                )}

                            </AnimatePresence>

                        </div>
                        
                        <div className="form-text mt-2">
                            {!isPro
                                ? `You can add up to ${MAX_PHOTOS} photos.`
                                : `As a PRO member, enjoy adding up to ${MAX_PHOTOS} photos!`
                            }
                        </div>
                    </div>
                    
                    {/* Price and For Sale (in one row) */}
                    <div className="row">

                        {/* Price */}
                        <div className="col-6 mb-3">
                            <label className="form-label">Price ($)</label>
                            <input 
                                type="text" className="form-control"
                                placeholder="Leave blank to auto-calculate"
                                value={manualValue} onChange={e => setManualValue(e.target.value)}
                            />
                        </div>

                        {/* For Sale */}
                        <div className="col-6 mb-3 form-check">
                            <label className="form-label d-block">&nbsp;</label> 
    
                            <div className="form-check form-switch fs-4 d-flex align-items-center justify-content-center ps-0">
                                <input 
                                    className="form-check-input my-0" 
                                    type="checkbox" 
                                    role="switch" 
                                    id="forSaleCheck"
                                    style={{ cursor: 'pointer' }}
                                    checked={forSale} 
                                    onChange={e => setForSale(e.target.checked)} 
                                />
                                <label className="form-check-label ms-3 fs-6" htmlFor="forSaleCheck">
                                    {forSale ? <b>For sale</b> : 'Not for sale'}
                                </label>
                            </div>
                        </div>
                    </div>
                    

                    {/* Buttons */}
                    <div className="d-grid gap-2">
                        <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
                            {loading
                                ? 'Uploading...'
                                : 'Add to Collection'}
                        </button>
                        <button type="button" className="btn btn-light" onClick={() => navigate('/profile')}>
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