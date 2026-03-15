import React, { useEffect } from "react";
import { Link } from "react-router-dom";

const UserListModal = ({ isOpen, onClose, title, users, loading }) => {
	// Block scroll when modal is open
	useEffect(() => {
		if (isOpen) {
			document.body.style.overflow = "hidden";
		} else {
			document.body.style.overflow = "unset";
		}
		return () => {
			document.body.style.overflow = "unset";
		};
	}, [isOpen]);

	if (!isOpen) return null; // If not open, render nothing

	return (
		<div
			className="d-flex justify-content-center align-items-center"
			style={{
				position: "fixed",
				top: 0,
				left: 0,
				width: "100%",
				height: "100%",
				backgroundColor: "rgba(0, 0, 0, 0.8)",
				zIndex: 1050,
			}}
			onClick={onClose} // Close modal when clicking on backdrop
		>
			<div
				className="card shadow"
				style={{
					width: "90%",
					maxWidth: "400px",
					maxHeight: "70vh",
					display: "flex",
					flexDirection: "column",
					overflow: "hidden",
				}}
				onClick={(e) => e.stopPropagation()} // Prevent closing when clicking inside the modal
			>
				{/* HEADER */}
				<div className="card-header bg-white d-flex justify-content-between align-items-center border-bottom-0 pt-3 pb-2">
					<h5 className="fw-bold mb-0 text-capitalize">{title}</h5>
					<button className="btn-close" onClick={onClose}></button>
				</div>

				{/* BODY */}
				<div className="card-body overflow-auto p-0">
					{loading ? (
						<div className="text-center p-4">
							<div className="spinner-border spinner-border-sm text-primary"></div>
						</div>
					) : users.length === 0 ? (
						<div className="text-center p-4 text-muted">
							No {title.toLowerCase()} yet.
						</div>
					) : (
						<ul className="list-group list-group-flush">
							{users.map((u) => (
								<Link
									key={u.id}
									to={`/profile/${u.username}`}
									className="list-group-item list-group-item-action d-flex align-items-center gap-3 p-3 border-0 border-bottom"
									onClick={onClose} // Close modal when clicking on a user
								>
									{/* Avatar */}
									{u.avatar ? (
										<img
											src={u.avatar}
											alt="avatar"
											className="rounded-circle"
											style={{
												width: "40px",
												height: "40px",
												objectFit: "cover",
											}}
										/>
									) : (
										<div
											className="bg-primary text-white rounded-circle d-flex justify-content-center align-items-center"
											style={{
												width: "40px",
												height: "40px",
											}}
										>
											{u.username.charAt(0).toUpperCase()}
										</div>
									)}

									{/* Data */}
									<div>
										<h6 className="mb-0 fw-bold text-dark">
											{u.username}
										</h6>
										<small className="text-muted">
											{/* Dynamic subtitle - depending on API response */}
											{u.followers_count !== undefined
												? `${u.followers_count} ${u.followers_count === 1 ? "follower" : "followers"}`
												: `${u.kits_count || 0} kits`}
										</small>
									</div>
								</Link>
							))}
						</ul>
					)}
				</div>
			</div>
		</div>
	);
};

export default UserListModal;
