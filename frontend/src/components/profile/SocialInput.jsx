import React from "react";

const SocialInput = ({ label, iconClass, value, setValue, placeholder }) => (
	<div className="mb-3">
		<label className="form-label small fw-bold text-muted">{label}</label>
		<div className="input-group">
			<span className="input-group-text bg-light border-end-0">
				<i className={`bi ${iconClass}`}></i>
			</span>
			<input
				type="url"
				className="form-control border-start-0"
				placeholder={placeholder}
				value={value}
				onChange={(e) => setValue(e.target.value)}
			/>
		</div>
	</div>
);

export default SocialInput;
