import React from "react";

const SocialLink = ({ url, icon, color, title }) => {
	if (!url) return null;
	return (
		<a
			href={url}
			target="_blank"
			rel="noopener noreferrer"
			className="text-decoration-none me-3"
			style={{
				fontSize: "1.5rem",
				color: color || "#333",
				transition: "transform 0.2s",
			}}
			onMouseOver={(e) =>
				(e.currentTarget.style.transform = "scale(1.2)")
			}
			onMouseOut={(e) => (e.currentTarget.style.transform = "scale(1)")}
			title={title}
		>
			<i className={`bi ${icon}`}></i>
		</a>
	);
};

export default SocialLink;
