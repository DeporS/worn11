import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../services/api';

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
    
    // New photos
    const [selectedFiles, setSelectedFiles] = useState([]);

    // UI States
    const [loading, setLoading] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true); // Data loading state
    const [error, setError] = useState(null);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const isSelectionRef = useRef(false);

    // FETCHING OPTIONS (Selects)
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
                
                setInitialLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch kit details", err);
                setError("Could not load kit details.");
                setInitialLoading(false);
            });
    }, [id]);

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

        // Add photos only if the user selected NEW ones
        selectedFiles.forEach((file) => {
            formData.append('images', file); 
        });

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
                            <input type="text" className="form-control" required
                                value={season} onChange={e => setSeason(e.target.value)} />
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
                            <label className="form-label">Add New Photos (Optional)</label>
                            <input type="file" className="form-control" accept="image/*" multiple
                                onChange={(e) => { if (e.target.files) setSelectedFiles(Array.from(e.target.files)); }} 
                            />
                            <div className="form-text">Uploading new photos will add them to existing ones.</div>
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