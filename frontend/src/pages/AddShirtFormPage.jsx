import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { addKitToCollection } from '../services/api';
import api from '../services/api';

const AddShirtFormPage = () => {
    const navigate = useNavigate();

    // States from Backend
    const [sizeOptions, setSizeOptions] = useState([]);
    const [conditionOptions, setConditionOptions] = useState([]);
    const [technologyOptions, setTechnologyOptions] = useState([]);
    const [typeOptions, setTypeOptions] = useState([]);

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
        
        selectedFiles.forEach((file) => {
            formData.append('images', file); 
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

    const isFormIncomplete = !technology || !size || !condition || !kitType;

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
                    <div className="mb-3">
                        <label className="form-label">Team Name</label>
                        <input 
                            type="text" className="form-control" required
                            placeholder=""
                            value={teamName} onChange={e => setTeamName(e.target.value)}
                        />
                    </div>

                    {/* Season */}
                    <div className="mb-3">
                        <label className="form-label">Season</label>
                        <input 
                            type="text" className="form-control" required
                            placeholder=""
                            value={season} onChange={e => setSeason(e.target.value)}
                        />
                    </div>

                    {/* Technology */}
                    <div className="mb-3">
                        <label className="form-label">Shirt Technology</label>
                        <select 
                            className="form-select" 
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
                        <div className="col-6 mb-3">
                            <label className="form-label">Type</label>
                            <select 
                                className="form-select" 
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

                        <div className="col-6 mb-3">
                            <label className="form-label">Size</label>
                            <select 
                                className="form-select" 
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

                    {/* Photos (Input File) */}
                    <div className="mb-4">
                        <label className="form-label">Photos</label>
                        <input 
                            type="file" 
                            className="form-control" 
                            accept="image/*"
                            multiple
                            onChange={(e) => {
                                if (e.target.files) {
                                    setSelectedFiles(Array.from(e.target.files));
                                }
                            }} 
                        />
                        <div className="form-text">Select one or more photos of the shirt.</div>
                    </div>

                    {/* Buttons */}
                    <div className="d-grid gap-2">
                        <button type="submit" className="btn btn-primary btn-lg" disabled={loading || isFormIncomplete}>
                            {loading
                                ? 'Uploading...'
                                : isFormIncomplete
                                    ? 'Fill all fields to add to collection'
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