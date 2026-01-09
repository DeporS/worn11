import React from 'react';

const SearchBar = ({ value, onChange }) => {
    return (
        <div style={{ maxWidth: '400px', margin: '0 auto' }}>
            <div className="input-group">
                <span className="input-group-text bg-white">@</span>
                <input 
                    type="text" 
                    className="form-control" 
                    placeholder="Type to search users..."
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    autoFocus // Focus input on load
                />
            </div>
        </div>
    );
};

export default SearchBar;