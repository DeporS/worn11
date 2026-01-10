import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { nanoid } from 'nanoid';
import api from '../services/api';

import '../styles/photos.css';

const EditShirtFormPage = () => {
    const navigate = useNavigate();
    const { id } = useParams(); // Download ID from URL (ec. /edit/15)

    // Backend Options for Selects
    const [sizeOptions, setSizeOptions] = useState([]);
    const [conditionOptions, setConditionOptions] = useState([]);
    const [technologyOptions, setTechnologyOptions] = useState([]);
    const [typeOptions, setTypeOptions] = useState([]);
    const [suggestions, setSuggestions] = useState([]);

    // Form States (unchanged)
    const [teamName, setTeamName] = useState('');
    const [season, setSeason] = useState('');
    const [kitType, setKitType] = useState('');
    const [size, setSize] = useState('');
    const [condition, setCondition] = useState('');
    const [technology, setTechnology] = useState('');
    const [forSale, setForSale] = useState(false);
    const [manualValue, setManualValue] = useState('');

    // Photos States
    const [galleryItems, setGalleryItems] = useState([]); // Existing photos
    const [deletedImageIds, setDeletedImageIds] = useState([]); // IDs of photos to delete

    // Drag and Drop Refs & States
    const dragItem = useRef(null);
    const dragOverItem = useRef(null);
    const [dragOverIndex, setDragOverIndex] = useState(null);
    const fileInputRef = useRef(null);

    const [isPro, setIsPro] = useState(false); // User subscription status
    const MAX_PHOTOS = isPro ? 20 : 5;

    // UI States
    const [loading, setLoading] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true); // Data loading state
    const [error, setError] = useState(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const isSelectionRef = useRef(false);

    // FETCHING OPTIONS (Selects)
    useEffect(() => {
        api.get('/options/').then(res => {
            setSizeOptions(res.data.sizes);
            setConditionOptions(res.data.conditions);
            setTechnologyOptions(res.data.technologies);
            setTypeOptions(res.data.types);
        });

        api.get('/auth/user/').then(res => {
            if (res.data.is_pro) setIsPro(true);
        });
    }, []);

    // DOWNLOAD EXISTING SHIRT DATA TO EDIT
    useEffect(() => {

        api.get(`/my-collection/${id}/`)
            .then(response => {
                const data = response.data;

                // Block autocomplete on initial load
                isSelectionRef.current = true;

                // Map backend data to form states
                setTeamName(data.kit.team.name);
                setSeason(data.kit.season);
                setKitType(data.kit.kit_type);

                setSize(data.size);
                setCondition(data.condition);
                setTechnology(data.shirt_technology);
                setForSale(data.for_sale);
                // Convert to string to prevent input from complaining about null
                setManualValue(data.manual_value ? data.manual_value.toString() : '');

                // Existing photos mapping
                // data.images is an object table: [{ id: 1, image: "url..." }, ...]
                if (data.images && Array.isArray(data.images)) {
                    const mappedImages = data.images.map(img => ({
                        id: img.id,          // ID from backend
                        preview: img.image,  // URL of the image
                        file: null,          // No file, because it's already on the server
                        isExisting: true     // Flag that this is an old photo
                    }));
                    setGalleryItems(mappedImages);
                }

                setInitialLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch kit details", err);
                setError("Could not load kit details.");
                setInitialLoading(false);
            });
    }, [id]);

    // PHOTO HANDLERS
    const handleFileSelect = (e) => {
        if (e.target.files) {
            const rawFiles = Array.from(e.target.files);

            // Create new objects for each file
            const newItems = rawFiles.map(file => ({
                id: nanoid(),            // Temporary ID for React
                preview: URL.createObjectURL(file),
                file: file,              // Actual file for upload
                isExisting: false        // Flag that this is new
            }));

            const total = galleryItems.length + newItems.length;
            if (total > MAX_PHOTOS) {
                alert(`Limit reached. You can max have ${MAX_PHOTOS} photos.`);
                return;
            }

            setGalleryItems(prev => [...prev, ...newItems]);
        }
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    // Remove photo handler
    const handleRemovePhoto = (id) => {
        // Find the item to remove
        const itemToRemove = galleryItems.find(item => item.id === id);

        if (itemToRemove && itemToRemove.isExisting) {
            // If it's an OLD photo, add its ID to the list of deleted images
            setDeletedImageIds(prev => [...prev, itemToRemove.id]);
        } else if (itemToRemove && !itemToRemove.isExisting) {
            // If it's a NEW photo, release memory
            URL.revokeObjectURL(itemToRemove.preview);
        }

        // Remove from view
        setGalleryItems(prev => prev.filter(item => item.id !== id));
    };

    // sort photos after drag and drop
    const handleSort = () => {
        let _items = [...galleryItems];
        const draggedItemContent = _items.splice(dragItem.current, 1)[0];
        _items.splice(dragOverItem.current, 0, draggedItemContent);

        dragItem.current = null;
        dragOverItem.current = null;
        setGalleryItems(_items);
    };

    const triggerFileInput = () => fileInputRef.current.click(); // Open file dialog

    // SAVING CHANGES
    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const formData = new FormData();
        // Send everything as in adding
        formData.append('team_name', teamName);
        formData.append('season', season);
        formData.append('kit_type', kitType);
        formData.append('size', size);
        formData.append('condition', condition);
        formData.append('shirt_technology', technology);
        formData.append('for_sale', forSale);

        // Manual value is sent only if something was entered, otherwise an empty string
        if (manualValue) {
            formData.append('manual_value', manualValue);
        } else {
            // If the backend supports clearing the value, you can send null or an empty string
            // Depending on the serializer configuration:
            formData.append('manual_value', '');
        }

        const fullOrder = [];
        let newImageIndex = 0;

        // iterate over galleryItems to build the order and append new images
        galleryItems.forEach((item) => {
            if (item.isExisting) {
                // If the photo exists, add its ID to the order
                fullOrder.push(item.id);
            } else if (item.file) {
                // If it's a new photo:
                // 1. Add the file to FormData
                formData.append('new_images', item.file);
                
                // 2. In the order, save a placeholder, e.g. "new_0"
                fullOrder.push(`new_${newImageIndex}`);
                
                newImageIndex++;
            }
        });

        // Append IDs of deleted photos
        deletedImageIds.forEach(id => {
            formData.append('deleted_images', id);
        });

        const existingImagesOrder = galleryItems
            .filter(item => item.isExisting)
            .map(item => item.id);

        formData.append('images_order', JSON.stringify(fullOrder));

        console.log("=== Sending to backend ===");
        for (let pair of formData.entries()) {
            console.log(pair[0] + ': ' + pair[1]);
        }

        try {
            await api.patch(`/my-collection/${id}/`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });

            navigate('/my-collection'); // Return to list
        } catch (err) {
            console.error(err);
            setError('Something went wrong while updating.');
            setLoading(false);
        }
    };

    // Autocomplete Team Name
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

    const handleSuggestionClick = (team) => {
        isSelectionRef.current = true;
        setTeamName(team.name);
        setSuggestions([]);
        setShowSuggestions(false);
    };

    if (initialLoading) return <div className="text-center mt-5">Loading kit details...</div>;

    const isFormIncomplete = !technology || !size || !condition || !kitType;

    return (
        <div className="container py-5">
            <div className="row justify-content-center">
                <div className="col-md-8 col-lg-6">

                    <div className="card shadow-sm border-0">
                        <div className="card-body p-4">

                            <h3 className="mb-4 fw-bold">Edit Kit Details ✏️</h3>

                            {error && <div className="alert alert-danger">{error}</div>}

                            <form onSubmit={handleSubmit}>
                                {/* Team Name */}
                                <div className="mb-3 position-relative">
                                    <label className="form-label">Team Name</label>
                                    <input
                                        type="text" className="form-control" required
                                        value={teamName} onChange={e => setTeamName(e.target.value)}
                                        autoComplete="off"
                                    />
                                    {showSuggestions && suggestions.length > 0 && (
                                        <ul className="list-group position-absolute w-100 shadow" style={{ zIndex: 1000, top: '100%' }}>
                                            {suggestions.map((team) => (
                                                <li key={team.id} className="list-group-item list-group-item-action d-flex align-items-center gap-3"
                                                    style={{ cursor: 'pointer' }} onClick={() => handleSuggestionClick(team)}>
                                                    {team.logo && <img src={team.logo} alt={team.name} style={{ width: '30px' }} />}
                                                    <span>{team.name}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </div>

                                {/* Season */}
                                <div className="mb-3">
                                    <label className="form-label">Season</label>
                                    {/* <input type="text" className="form-control" required
                                value={season} onChange={e => setSeason(e.target.value)} /> */}
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
                                    <select className="form-select" value={technology} onChange={e => setTechnology(e.target.value)}>
                                        {technologyOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                    </select>
                                </div>

                                {/* Type & Size */}
                                <div className="row">
                                    <div className="col-6 mb-3">
                                        <label className="form-label">Type</label>
                                        <select className="form-select" value={kitType} onChange={e => setKitType(e.target.value)}>
                                            {typeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                    <div className="col-6 mb-3">
                                        <label className="form-label">Size</label>
                                        <select className="form-select" value={size} onChange={e => setSize(e.target.value)}>
                                            {sizeOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                        </select>
                                    </div>
                                </div>

                                {/* Condition */}
                                <div className="mb-3">
                                    <label className="form-label">Condition</label>
                                    <select className="form-select" value={condition} onChange={e => setCondition(e.target.value)}>
                                        {conditionOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                    </select>
                                </div>

                                {/* Photos */}
                                <div className="mb-4">
                                    <div className="d-flex justify-content-between align-items-center mb-2">
                                        <label className="form-label fw-bold m-0">Photos ({galleryItems.length}/{MAX_PHOTOS})</label>
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

                                    <input type="file" ref={fileInputRef} className="d-none" accept="image/*" multiple onChange={handleFileSelect} />

                                    <div className="d-flex flex-wrap" style={{ gap: '16px' }}>
                                        <AnimatePresence mode="popLayout">
                                            {galleryItems.map((item, index) => (
                                                <motion.div
                                                    key={item.id} // id (from database or nanoid)
                                                    layout
                                                    draggable
                                                    onDragStart={(e) => {
                                                        dragItem.current = index;
                                                        e.dataTransfer.effectAllowed = "move";
                                                    }}
                                                    onDragEnter={() => {
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
                                                    className="photo-tile position-relative"
                                                    style={{
                                                        width: '100px', height: '100px', cursor: 'grab',
                                                        border: dragOverIndex === index ? '2px solid #0d6efd' : 'none',
                                                        borderRadius: '0.375rem'
                                                    }}
                                                    whileDrag={{ cursor: 'grabbing' }}
                                                >
                                                    <img src={item.preview} alt="preview" className="rounded border shadow-sm w-100 h-100" style={{ objectFit: 'cover', pointerEvents: 'none' }} />

                                                    {/* OVERLAY */}
                                                    <div className="hover-overlay position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-dark bg-opacity-25" style={{ pointerEvents: 'none' }}>
                                                        <i className="bi bi-arrows-move text-white fs-3 drop-shadow"></i>
                                                    </div>

                                                    <button
                                                        type="button"
                                                        className="btn btn-danger btn-sm position-absolute top-0 end-0 rounded-circle p-0 d-flex align-items-center justify-content-center"
                                                        style={{ width: '20px', height: '20px', transform: 'translate(30%, -30%)', zIndex: 10 }}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleRemovePhoto(item.id)
                                                        }}
                                                    >
                                                        <span style={{ fontSize: '12px', lineHeight: 1 }}>&times;</span>
                                                    </button>

                                                    {/* Info old or new */}
                                                    <span
                                                        className={`position-absolute bottom-0 end-0 badge ${item.isExisting ? 'bg-info' : 'bg-success'
                                                            } bg-opacity-75`}
                                                        style={{ fontSize: '8px', margin: '2px' }}
                                                    >
                                                        {item.isExisting ? 'OLD' : 'NEW'}
                                                    </span>

                                                    {/* Photo number */}
                                                    <span className="position-absolute bottom-0 start-0 badge bg-dark bg-opacity-50" style={{ fontSize: '9px', margin: '2px' }}>
                                                        {index + 1}
                                                    </span>
                                                </motion.div>
                                            ))}

                                            {/* PLUS BUTTON */}
                                            {galleryItems.length < MAX_PHOTOS && (
                                                <motion.div layout key="add-btn" onClick={triggerFileInput}
                                                    className="rounded border border-2 d-flex flex-column align-items-center justify-content-center text-muted bg-light"
                                                    style={{ width: '100px', height: '100px', cursor: 'pointer', borderStyle: 'dashed' }}>
                                                    <i className="bi bi-plus-lg fs-3"></i>
                                                    <small style={{ fontSize: '10px' }}>Add</small>
                                                </motion.div>
                                            )}
                                        </AnimatePresence>
                                    </div>
                                </div>

                                {/* Price & For Sale */}
                                <div className="row">

                                    {/* Price */}
                                    <div className="col-6 mb-3">
                                        <label className="form-label">Price ($)</label>
                                        <input type="text" className="form-control" placeholder="Auto"
                                            value={manualValue} onChange={e => setManualValue(e.target.value)} />
                                    </div>

                                    {/* For Sale Toggle */}
                                    <div className="col-6 mb-3">
                                        <label className="form-label d-block">&nbsp;</label>
                                        <div className="form-check form-switch fs-4 d-flex align-items-center justify-content-center ps-0">
                                            <input className="form-check-input my-0" type="checkbox" role="switch" id="forSaleCheck"
                                                style={{ cursor: 'pointer' }} checked={forSale} onChange={e => setForSale(e.target.checked)} />
                                            <label className="form-check-label ms-3 fs-6" htmlFor="forSaleCheck">
                                                {forSale ? <b>For sale</b> : 'Not for sale'}
                                            </label>
                                        </div>
                                    </div>
                                </div>

                                {/* Buttons */}
                                <div className="d-grid gap-2">
                                    <button type="submit" className="btn btn-warning btn-lg text-white" disabled={loading || isFormIncomplete}>
                                        {loading ? 'Saving...' : 'Save Changes'}
                                    </button>
                                    <button type="button" className="btn btn-light" onClick={() => navigate(-1)}>
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