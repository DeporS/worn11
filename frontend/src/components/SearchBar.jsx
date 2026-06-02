import React from 'react';
import { useTranslation } from "react-i18next";

const SearchBar = ({ value, onChange }) => {
    const { t } = useTranslation();
    return (
        <div style={{ maxWidth: '400px', margin: '0 auto' }}>
            <div className="input-group">
                <span className="input-group-text bg-white">@</span>
                <input
                    type="text"
                    className="form-control"
                    placeholder={t("search.placeholder")}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    autoFocus // Focus input on load
                />
            </div>
        </div>
    );
};

export default SearchBar;
