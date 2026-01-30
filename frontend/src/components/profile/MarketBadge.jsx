import React, { useState } from "react";

const MarketBadge = ({ url, icon, label, hoverColor }) => {
	const [isHovered, setIsHovered] = useState(false);

	if (!url) return null;

	return (
		<a
			href={url}
			target="_blank"
			rel="noopener noreferrer"
			className="market-badge me-2 mb-2"
			style={{
				color: isHovered ? hoverColor : "#555555",
				borderColor: isHovered ? hoverColor : "#e0e0e0",
			}}
			onMouseEnter={() => setIsHovered(true)}
			onMouseLeave={() => setIsHovered(false)}
		>
			<i className={`bi ${icon}`} style={{ fontSize: "1rem" }}></i>
			<span>{label}</span>
		</a>
	);
};

export default MarketBadge;
