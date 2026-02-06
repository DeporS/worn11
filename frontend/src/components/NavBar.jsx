import React, { useState } from "react";
import LoginButton from "./LoginButton";
import UserAvatar from "./UserAvatar";
import { Link, NavLink } from "react-router-dom";

import logo from "../assets/logo-worn11.svg";

import "../styles/navbar.css";

const API_URL = "http://127.0.0.1:8000";

const NavBar = ({ user, onLoginSuccess, onLogout }) => {
	// State for hamburger menu (mobile)
	const [isOpen, setIsOpen] = useState(false);

	// Toggle hamburger menu
	const toggleMenu = () => setIsOpen(!isOpen);

	// Close menu (used when a link is clicked)
	const closeMenu = () => setIsOpen(false);

	return (
		<nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm py-3 sticky-top">
			<div className="container">
				{/* Logo */}
				<Link className="navbar-brand" to="/" onClick={closeMenu}>
					<div className="d-flex align-items-center">
						<img
							src={logo}
							alt="WORN11 Logo"
							style={{ height: "40px", marginRight: "10px" }}
						/>
						<span
							style={{
								fontWeight: 800,
								letterSpacing: "-0.5px",
								fontSize: "1.6rem",
							}}
						>
							WORN
						</span>
						<span
							className="text-primary"
							style={{
								fontWeight: 900,
								marginLeft: "1px",
								fontSize: "1.9rem",
							}}
						>
							11
						</span>
					</div>
				</Link>

				{/* Hamburger */}
				<div
					className={`navbar-toggler ${isOpen ? "open" : ""}`}
					onClick={toggleMenu}
					aria-label="Toggle navigation"
				>
					<span className="hamburger-lines"></span>
					<span className="hamburger-lines"></span>
					<span className="hamburger-lines"></span>
				</div>

				{/* Collapsible Content */}
				<div
					className={`collapse navbar-collapse ${isOpen ? "show" : ""}`}
					id="navbarNav"
				>
					{/* Left side (Links) */}
					<ul className="navbar-nav me-auto mb-2 mb-lg-0 mt-4 mt-lg-0 text-center text-lg-start ms-lg-5">
						<hr className="d-lg-none text-muted w-100 my-3" />
						<li className="nav-item">
							<NavLink
								to="/history"
								className={({ isActive }) =>
									`nav-link px-3 fw-bold text-nowrap ${isActive ? "text-primary" : "text-dark"}`
								}
								onClick={closeMenu}
								style={{ fontSize: "1.1rem" }}
							>
								Kit Museum
							</NavLink>
						</li>
						<hr className="d-lg-none text-muted w-100 my-3" />
						<li className="nav-item">
							<NavLink
								to="/history"
								className={({ isActive }) =>
									`nav-link px-3 fw-bold text-nowrap ${isActive ? "text-primary" : "text-dark"}`
								}
								onClick={closeMenu}
								style={{ fontSize: "1.1rem" }}
							>
								Kit Museum
							</NavLink>
						</li>
						{/* More links here */}
					</ul>

					<hr className="d-lg-none text-muted w-100 my-3" />

					{/* Right side (User) */}
					<div className="d-flex flex-column flex-lg-row align-items-center gap-3 w-100 w-lg-auto justify-content-center justify-content-lg-end">
						{user ? (
							<>
								<div className="d-flex align-items-center gap-3 w-100 justify-content-center justify-content-lg-end">
									{/* Profil Link */}
									<Link
										to="/my-collection"
										className="text-decoration-none text-dark d-flex align-items-center gap-2 p-2 rounded hover-bg-light"
										onClick={closeMenu}
									>
										<UserAvatar user={user} size={40} />
										<div className="d-flex flex-column align-items-start">
											<span className="fw-bold">
												{user.username}
											</span>
											<span
												className="text-muted small"
												style={{ fontSize: "0.8rem" }}
											>
												View profile
											</span>
										</div>
									</Link>

									{/* Vertical separator */}
									<div className="vr text-muted mx-2"></div>

									{/* Logout button */}
									<button
										className="btn btn-link text-muted text-decoration-none p-2"
										onClick={() => {
											onLogout();
											closeMenu();
										}}
										title="Logout"
										style={{
											display: "flex",
											alignItems: "center",
										}}
									>
										{/* Logout icon */}
										{/* Mobile */}
										<i className="bi bi-box-arrow-right fs-1 d-lg-none"></i>
										{/* Desktop */}
										<i className="bi bi-box-arrow-right fs-3 d-none d-lg-inline logout-button"></i>
									</button>
								</div>
							</>
						) : (
							<div onClick={closeMenu}>
								<LoginButton onLoginSuccess={onLoginSuccess} />
							</div>
						)}
					</div>
				</div>
			</div>
		</nav>
	);
};

export default NavBar;
