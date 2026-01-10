import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { updateUserProfile } from '../services/api';

const EditProfilePage = ({ user, setUser }) => {
    const navigate = useNavigate();
    
    // Form states
    const [bio, setBio] = useState('');
    const [avatarFile, setAvatarFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Load existing profile data on mount
    useEffect(() => {
        if (user?.profile) {
            setBio(user.profile.bio || '');
            // If the user already has an avatar, set it as the preview
            if (user.profile.avatar) {
                setPreviewUrl(user.profile.avatar);
            }
        }
    }, [user]);

    // Handle file selection (and create preview)
    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            setAvatarFile(file);
            // Create a temporary URL to display the image immediately
            setPreviewUrl(URL.createObjectURL(file));
        }
    };

    // Submit the form
    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);

        const formData = new FormData();
        formData.append('bio', bio);
        
        // We send the file only if the user selected a new one
        if (avatarFile) {
            formData.append('avatar', avatarFile);
        }

        try {
            const updatedProfile = await updateUserProfile(formData);
            
            // Update the main user state in the app (e.g., to refresh the header)
            // Assuming setUser is a function from App.js or Context
            if (setUser) {
                setUser(prevUser => {
                    const newUser = {
                        ...prevUser,
                        profile: updatedProfile
                    };
                    localStorage.setItem('user_data', JSON.stringify(newUser)); 

                    return newUser;
                });
            }

            navigate(`/profile/${user.username}`); // Return to profile
        } catch (err) {
            console.error(err);
            setError('Failed to update profile. Please try again.');
            setLoading(false);
        }
    };

    if (!user) return <div className="text-center mt-5">Loading...</div>;

    return (
        <div className="container py-5">
            <div className="row justify-content-center">
                <div className="col-md-8 col-lg-6">
                    <div className="card shadow-sm border-0">
                        <div className="card-body p-4">
                            <h3 className="mb-4 fw-bold text-center">Edit Profile ✏️</h3>

                            {error && <div className="alert alert-danger">{error}</div>}

                            <form onSubmit={handleSubmit}>
                                
                                {/* AVATAR SECTION */}
                                <div className="d-flex flex-column align-items-center mb-4">
                                    <div 
                                        className="rounded-circle overflow-hidden mb-3 border border-3 border-light shadow-sm"
                                        style={{ width: '120px', height: '120px', position: 'relative', backgroundColor: '#f0f0f0' }}
                                    >
                                        {previewUrl ? (
                                            <img 
                                                src={previewUrl} 
                                                alt="Avatar Preview" 
                                                className="w-100 h-100"
                                                style={{ objectFit: 'cover' }} 
                                            />
                                        ) : (
                                            // Placeholder (initial letter)
                                            <div className="w-100 h-100 d-flex align-items-center justify-content-center bg-primary text-white fs-1">
                                                {user.username.charAt(0).toUpperCase()}
                                            </div>
                                        )}
                                    </div>
                                    
                                    <label className="btn btn-outline-primary btn-sm">
                                        Change Photo
                                        <input 
                                            type="file" 
                                            hidden 
                                            accept="image/*"
                                            onChange={handleFileChange}
                                        />
                                    </label>
                                </div>

                                {/* BIO SECTION */}
                                <div className="mb-3">
                                    <label className="form-label fw-bold">Bio</label>
                                    <textarea 
                                        className="form-control" 
                                        rows="4" 
                                        placeholder="Tell us something about yourself and your collection..."
                                        value={bio}
                                        onChange={(e) => setBio(e.target.value)}
                                        maxLength={500}
                                    ></textarea>
                                    <div className="form-text text-end">{bio.length}/500</div>
                                </div>

                                {/* BUTTONS */}
                                <div className="d-grid gap-2">
                                    <button 
                                        type="submit" 
                                        className="btn btn-primary py-2"
                                        disabled={loading}
                                    >
                                        {loading ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2"></span>
                                                Saving...
                                            </>
                                        ) : 'Save Changes'}
                                    </button>
                                    
                                    <button 
                                        type="button" 
                                        className="btn btn-light text-muted"
                                        onClick={() => navigate(-1)}
                                    >
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

export default EditProfilePage;