import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import LoginButton from "./LoginButton";
import UserAvatar from "./UserAvatar";
import NotificationsDropdown from "./notifications/NotificationsDropdown";
import { Link, NavLink } from "react-router-dom";

import logo from "../assets/logo-worn11.svg";
import { canAccessModeration } from "../utils/permissions";

import "../styles/navbar.css";

const API_URL = "http://127.0.0.1:8000";

const NavBar = ({
	user,
	onLoginSuccess,
	onLogout,
	unreadMessagesCount = 0,
	unreadNotificationsCount = 0,
	refreshUnreadNotificationsCount,
}) => {
	const { t, i18n } = useTranslation();
	// State for hamburger menu (mobile)
	const [isOpen, setIsOpen] = useState(false);

	// Toggle hamburger menu
	const toggleMenu = () => setIsOpen(!isOpen);

	// Close menu (used when a link is clicked)
	const closeMenu = () => setIsOpen(false);
	const currentLanguage = i18n.language?.startsWith("pl") ? "pl" : "en";
	const handleLanguageChange = (nextLanguage) => {
		if (nextLanguage === currentLanguage) return;
		i18n.changeLanguage(nextLanguage);
	};

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
						<span className="navbar-brand-wordmark">
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
							<span className="navbar-brand-domain">.com</span>
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
						{user ? (
							<>
								<hr className="d-lg-none text-muted w-100 my-3" />
								<li className="nav-item">
									<NavLink
										to="/feed"
										className={({ isActive }) =>
											`nav-link px-3 fw-bold text-nowrap ${isActive ? "text-primary" : "text-dark"}`
										}
										onClick={closeMenu}
										style={{ fontSize: "1.1rem" }}
									>
										{t("nav.feed")}
									</NavLink>
								</li>
								{canAccessModeration(user) ? (
									<>
										<hr className="d-lg-none text-muted w-100 my-3" />
										<li className="nav-item">
											<NavLink
												to="/admin/kit-types"
												className={({ isActive }) =>
													`nav-link px-3 fw-bold text-nowrap ${isActive ? "text-primary" : "text-dark"}`
												}
												onClick={closeMenu}
												style={{ fontSize: "1.1rem" }}
											>
												{t("nav.admin")}
											</NavLink>
										</li>
									</>
								) : null}
							</>
						) : null}
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
								{t("nav.kitMuseum")}
							</NavLink>
						</li>
						<hr className="d-lg-none text-muted w-100 my-3" />
						<li className="nav-item">
							<NavLink
								to="/groups"
								className={({ isActive }) =>
									`nav-link px-3 fw-bold text-nowrap ${isActive ? "text-primary" : "text-dark"}`
								}
								onClick={closeMenu}
								style={{ fontSize: "1.1rem" }}
							>
								Groups
							</NavLink>
						</li>
						{/* More links here */}
					</ul>

					<hr className="d-lg-none text-muted w-100 my-3" />

					{/* Right side (User) */}
					<div className="navbar-user-area w-100 w-lg-auto">
						{user ? (
							<>
								{/* Desktop user controls */}
								<div className="d-none d-lg-flex align-items-center gap-3 justify-content-end">
									<Link
										to="/messages"
										className="text-decoration-none text-dark position-relative p-2 rounded hover-bg-light"
										onClick={closeMenu}
										title={t("nav.messages")}
									>
										<i className="bi bi-chat-dots fs-4"></i>
										{unreadMessagesCount > 0 && (
											<span
												className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
												style={{ fontSize: "0.65rem" }}
											>
												{unreadMessagesCount > 99
													? "99+"
													: unreadMessagesCount}
											</span>
										)}
									</Link>

									<NotificationsDropdown
										unreadCount={unreadNotificationsCount}
										refreshUnreadNotificationsCount={refreshUnreadNotificationsCount}
									/>

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
												{t("nav.viewProfile")}
											</span>
										</div>
									</Link>

									<div
										className="language-switcher"
										role="group"
										aria-label="Language switcher"
									>
										<button
											type="button"
											className={`language-switcher__option ${currentLanguage === "en" ? "active" : ""}`}
											onClick={() =>
												handleLanguageChange("en")
											}
											disabled={currentLanguage === "en"}
											aria-pressed={
												currentLanguage === "en"
											}
										>
											{t("nav.languageEnglish")}
										</button>
										<button
											type="button"
											className={`language-switcher__option ${currentLanguage === "pl" ? "active" : ""}`}
											onClick={() =>
												handleLanguageChange("pl")
											}
											disabled={currentLanguage === "pl"}
											aria-pressed={
												currentLanguage === "pl"
											}
										>
											{t("nav.languagePolish")}
										</button>
									</div>

									<div className="vr text-muted mx-2"></div>

									<button
										className="btn btn-link text-muted text-decoration-none p-2"
										onClick={() => {
											onLogout();
											closeMenu();
										}}
										title={t("nav.logout")}
										style={{
											display: "flex",
											alignItems: "center",
										}}
									>
										<i className="bi bi-box-arrow-right fs-3 logout-button"></i>
									</button>
								</div>

								{/* Mobile user controls */}
								<div className="d-lg-none navbar-mobile-user-controls d-flex flex-column align-items-center gap-2 mt-2">
									<Link
										to="/messages"
										className="text-decoration-none text-dark position-relative p-2 rounded hover-bg-light d-flex align-items-center"
										onClick={closeMenu}
										title={t("nav.messages")}
									>
										<i className="bi bi-chat-dots fs-4"></i>
										{unreadMessagesCount > 0 && (
											<span
												className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
												style={{ fontSize: "0.65rem" }}
											>
												{unreadMessagesCount > 99
													? "99+"
													: unreadMessagesCount}
											</span>
										)}
									</Link>

									<NotificationsDropdown
										unreadCount={unreadNotificationsCount}
										refreshUnreadNotificationsCount={refreshUnreadNotificationsCount}
										onCloseMobileMenu={closeMenu}
									/>

									<Link
										to="/my-collection"
										className="navbar-mobile-profile-row text-decoration-none text-dark d-flex align-items-center justify-content-center gap-2 p-2 rounded hover-bg-light w-100"
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
												{t("nav.viewProfile")}
											</span>
										</div>
									</Link>

									<div className="mobile-navbar-bottom-row">
										<div className="mobile-navbar-bottom-left">
											<div
												className="language-switcher"
												role="group"
												aria-label="Language switcher"
											>
												<button
													type="button"
													className={`language-switcher__option ${currentLanguage === "en" ? "active" : ""}`}
													onClick={() =>
														handleLanguageChange(
															"en",
														)
													}
													disabled={
														currentLanguage === "en"
													}
													aria-pressed={
														currentLanguage === "en"
													}
												>
													{t("nav.languageEnglish")}
												</button>
												<button
													type="button"
													className={`language-switcher__option ${currentLanguage === "pl" ? "active" : ""}`}
													onClick={() =>
														handleLanguageChange(
															"pl",
														)
													}
													disabled={
														currentLanguage === "pl"
													}
													aria-pressed={
														currentLanguage === "pl"
													}
												>
													{t("nav.languagePolish")}
												</button>
											</div>
										</div>

										<div
											className="mobile-navbar-bottom-divider"
											aria-hidden="true"
										/>

										<div className="mobile-navbar-bottom-right">
											<button
												className="btn btn-link text-muted text-decoration-none p-2"
												onClick={() => {
													onLogout();
													closeMenu();
												}}
												title={t("nav.logout")}
												style={{
													display: "flex",
													alignItems: "center",
												}}
											>
												<i className="bi bi-box-arrow-right fs-1"></i>
											</button>
										</div>
									</div>
								</div>
							</>
						) : (
							<div className="navbar-user-controls d-flex align-items-center justify-content-center justify-content-lg-end gap-2 gap-lg-3 w-100">
								<div
									className="language-switcher"
									role="group"
									aria-label="Language switcher"
								>
									<button
										type="button"
										className={`language-switcher__option ${currentLanguage === "en" ? "active" : ""}`}
										onClick={() =>
											handleLanguageChange("en")
										}
										disabled={currentLanguage === "en"}
										aria-pressed={currentLanguage === "en"}
									>
										{t("nav.languageEnglish")}
									</button>
									<button
										type="button"
										className={`language-switcher__option ${currentLanguage === "pl" ? "active" : ""}`}
										onClick={() =>
											handleLanguageChange("pl")
										}
										disabled={currentLanguage === "pl"}
										aria-pressed={currentLanguage === "pl"}
									>
										{t("nav.languagePolish")}
									</button>
								</div>
								<div onClick={closeMenu}>
									<LoginButton
										onLoginSuccess={onLoginSuccess}
									/>
								</div>
							</div>
						)}
					</div>
				</div>
			</div>
		</nav>
	);
};

export default NavBar;
