import React from 'react';

const SearchBar = ({ value, onChange, onSearch }) => {
  return (
    <div className="input-group" style={{maxWidth: '400px', margin: '0 auto'}}>
        <span className="input-group-text bg-white">@</span>
        <input 
            type="text" 
            className="form-control" 
            placeholder="Username (e.g. messi)"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
        />
        <button className="btn btn-primary" onClick={onSearch}>
            Search
        </button>
    </div>
  );
};

export default SearchBar;