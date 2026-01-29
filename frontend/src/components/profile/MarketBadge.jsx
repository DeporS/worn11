import React from "react";

const MarketBadge = ({ url, icon, label, colorClass }) => {
	if (!url) return null;
	return (
		<a
			href={url}
			target="_blank"
			rel="noopener noreferrer"
			className={`btn btn-sm ${colorClass} me-2 mb-2 d-inline-flex align-items-center gap-1`}
			style={{ borderRadius: "20px", padding: "5px 15px" }}
		>
			<i className={`bi ${icon}`}></i> {label}
		</a>
	);
};

export default MarketBadge;
