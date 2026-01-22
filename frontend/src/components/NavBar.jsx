import React from "react";
import LoginButton from "./LoginButton";
import UserAvatar from "./UserAvatar";
import { Link, NavLink } from "react-router-dom";

import logo from "../assets/logo-worn11.svg";

const API_URL = "http://127.0.0.1:8000";

const NavBar = ({ user, onLoginSuccess, onLogout }) => {
	return (
		<nav className="navbar navbar-expand-lg navbar-light bg-white shadow-sm py-3 sticky-top">
			<div className="container">
				{/* Logo */}
				<Link className="navbar-brand" to="/">
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
								fontSize: "1.6rem",
							}}
						>
							11
						</span>
					</div>
				</Link>

				{/* Hamburger */}
				<button
					className="navbar-toggler border-0"
					type="button"
					data-bs-toggle="collapse"
					data-bs-target="#navbarNav"
					aria-controls="navbarNav"
					aria-expanded="false"
					aria-label="Toggle navigation"
				>
					<span className="navbar-toggler-icon"></span>
				</button>

				{/* Collapsible Content */}
				<div className="collapse navbar-collapse" id="navbarNav">
					{/* Navigation Links (Left side) */}
					<ul className="navbar-nav me-auto mb-2 mb-lg-0">
						<li className="nav-item">
							<NavLink
								to="/history"
								className={({ isActive }) =>
									`nav-link px-3 fw-bold ${isActive ? "text-primary" : "text-dark"}`
								}
							>
								Kit Museum
							</NavLink>
						</li>
					</ul>

					{/* User actions (Right side) */}
					<div className="d-flex align-items-center">
						{user ? (
							// --- LOGGED IN ---
							<div className="d-flex align-items-center gap-3">
								{/* Profile Link */}
								<Link
									to="/my-collection"
									className="text-decoration-none text-dark d-flex align-items-center gap-2 user-nav-link p-1 rounded pe-3"
									style={{ transition: "background 0.2s" }}
								>
									<UserAvatar user={user} size={35} />
									<span className="fw-bold small">
										{user.username}
									</span>
								</Link>

								{/* Divider (vertical line) */}
								<div className="vr d-none d-lg-block mx-2 text-muted"></div>

								{/* Logout Button */}
								<button
									className="btn btn-link text-muted text-decoration-none p-0"
									onClick={onLogout}
									title="Logout"
								>
									<i className="bi bi-box-arrow-right fs-5"></i>
								</button>
							</div>
						) : (
							// --- NOT LOGGED IN ---
							<div>
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
