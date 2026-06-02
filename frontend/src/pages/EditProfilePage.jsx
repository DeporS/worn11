import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { updateUserProfile } from "../services/api";
import api from "../services/api";
import SocialInput from "../components/profile/SocialInput";
import { localizeCountryName } from "../utils/localizedCountries";
const EditProfilePage = ({ user, setUser }) => {
	const { t } = useTranslation();
	const navigate = useNavigate();

	// Form states
	const [username, setUsername] = useState("");
	const [bio, setBio] = useState("");
	const [avatarFile, setAvatarFile] = useState(null);
	const [previewUrl, setPreviewUrl] = useState(null);
	const [contactEmail, setContactEmail] = useState(null);
	const [facebookLink, setFacebookLink] = useState(null);
	const [instagramLink, setInstagramLink] = useState(null);
	const [twitterLink, setTwitterLink] = useState(null);
	const [youTubeLink, setYouTubeLink] = useState(null);
	const [tiktokLink, setTiktokLink] = useState(null);
	const [vintedLink, setVintedLink] = useState(null);
	const [ebayLink, setEbayLink] = useState(null);
	const [depopLink, setDepopLink] = useState(null);
	const [websiteLink, setWebsiteLink] = useState(null);
	const [name, setName] = useState("");
	const [surname, setSurname] = useState("");

	// Country selection states
	const [countriesList, setCountriesList] = useState([]); // Countries fetched from backend
	const [filteredCountries, setFilteredCountries] = useState([]); // List after filtering by search
	const [countrySearch, setCountrySearch] = useState(""); // Users input for searching countries
	const [selectedCountry, setSelectedCountry] = useState(null); // Currently selected country
	const [showCountryDropdown, setShowCountryDropdown] = useState(false); // Whether to show the dropdown list

	// Validation states
	const [usernameAvailable, setUsernameAvailable] = useState(true);
	const [usernameError, setUsernameError] = useState(null);
	const [checkingUsername, setCheckingUsername] = useState(false);

	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(null);

	const isUsernameLocked = user?.profile?.has_changed_username;

	// Fetch countries on mount
	useEffect(() => {
		api.get("/countries/")
			.then((res) => {
				setCountriesList(res.data);
			})
			.catch((err) => console.error("Failed to load countries", err));
	}, []);

	// Load existing profile data on mount
	useEffect(() => {
		if (user?.profile) {
			setUsername(user.username);

			// If the user already has an avatar, set it as the preview
			if (user.profile.avatar) {
				setPreviewUrl(user.profile.avatar);
			}

			setBio(user.profile.bio || "");
			setContactEmail(user.profile.contact_email || "");
			setFacebookLink(user.profile.facebook_link || "");
			setInstagramLink(user.profile.instagram_link || "");
			setTwitterLink(user.profile.twitter_link || "");
			setYouTubeLink(user.profile.youTube_link || "");
			setTiktokLink(user.profile.tiktok_link || "");

			setVintedLink(user.profile.vinted_link || "");
			setEbayLink(user.profile.ebay_link || "");
			setDepopLink(user.profile.depop_link || "");
			setWebsiteLink(user.profile.website_link || "");
			setName(user.profile.name || "");
			setSurname(user.profile.surname || "");

			// Set country on mount if exists
			if (user.profile.country_info) {
				setSelectedCountry(user.profile.country_info);
				setCountrySearch(
					localizeCountryName(user.profile.country_info.name, t),
				);
			}
		}
	}, [user, t]);

	useEffect(() => {
		if (!selectedCountry || showCountryDropdown) return;

		setCountrySearch(localizeCountryName(selectedCountry.name, t));
	}, [selectedCountry, showCountryDropdown, t]);

	// Check username availability when it changes
	useEffect(() => {
		// Dont check if username is unchanged
		if (!user || username === user.username) {
			setUsernameAvailable(true);
			setUsernameError(null);
			return;
		}

		// Simple validations
		if (username.length < 3) {
			setUsernameError(t("editProfile.usernameTooShort"));
			setUsernameAvailable(false);
			return;
		}
		if (!/^[a-zA-Z0-9_]+$/.test(username)) {
			setUsernameError(t("editProfile.usernamePattern"));
			setUsernameAvailable(false);
			return;
		}

		// Debounce API check
		const timer = setTimeout(async () => {
			setCheckingUsername(true);
			setUsernameError(null);

			try {
				const res = await api.get(
					`/auth/check-username/?q=${username}`,
				);

				if (res.data.available) {
					setUsernameAvailable(true);
				} else {
					setUsernameAvailable(false);
					setUsernameError(t("editProfile.usernameTaken"));
				}
			} catch (err) {
				console.error("Error checking username", err);
				// In case of network error, allow to try saving (backend will check anyway)
				setUsernameAvailable(true);
			} finally {
				setCheckingUsername(false);
			}
		}, 500);

		return () => clearTimeout(timer);
	}, [username, user, t]);

	// Handle file selection (and create preview)
	const handleFileChange = (e) => {
		const file = e.target.files[0];
		if (file) {
			setAvatarFile(file);
			// Create a temporary URL to display the image immediately
			setPreviewUrl(URL.createObjectURL(file));
		}
	};

	// Filter countries as user types and handle selection
	const handleCountrySearch = (e) => {
		const value = e.target.value;
		setCountrySearch(value);
		setShowCountryDropdown(true); // Open dropdown when user types

		// If the typed text doesn't match the selected country, it means the user wants to change it
		if (
			selectedCountry &&
			value !== selectedCountry.name &&
			value !== localizeCountryName(selectedCountry.name, t)
		) {
			setSelectedCountry(null);
		}

		if (value) {
			const filtered = countriesList.filter((c) =>
				c.name.toLowerCase().includes(value.toLowerCase()) ||
				localizeCountryName(c.name, t)
					.toLowerCase()
					.includes(value.toLowerCase()),
			);
			setFilteredCountries(filtered);
		} else {
			setFilteredCountries(countriesList);
		}
	};

	// When user selects a country from the list
	const handleSelectCountry = (country) => {
		setSelectedCountry(country);
		setCountrySearch(localizeCountryName(country.name, t));
		setShowCountryDropdown(false); // Close the list
	};

	// Submit the form
	const handleSubmit = async (e) => {
		e.preventDefault();

		// Block submission if username is invalid
		if (!usernameAvailable || usernameError) return;

		setLoading(true);
		setError(null);

		const formData = new FormData();
		if (username !== user.username) {
			formData.append("username", username);
		}

		formData.append("bio", bio);
		formData.append("contact_email", contactEmail || "");
		formData.append("facebook_link", facebookLink || "");
		formData.append("instagram_link", instagramLink || "");
		formData.append("twitter_link", twitterLink || "");
		formData.append("youTube_link", youTubeLink || "");
		formData.append("tiktok_link", tiktokLink || "");
		formData.append("vinted_link", vintedLink || "");
		formData.append("ebay_link", ebayLink || "");
		formData.append("depop_link", depopLink || "");
		formData.append("website_link", websiteLink || "");
		formData.append("name", name || "");
		formData.append("surname", surname || "");

		// Append country ID if selected, otherwise send empty to clear it
		if (selectedCountry) {
			formData.append("country", selectedCountry.id);
		} else {
			formData.append("country", ""); // Send empty string if cleared
		}

		// We send the file only if the user selected a new one
		if (avatarFile) {
			formData.append("avatar", avatarFile);
		}

		try {
			const updatedProfile = await updateUserProfile(formData);

			// Update the main user state in the app (e.g., to refresh the header)
			// Assuming setUser is a function from App.js or Context
			if (setUser) {
				setUser((prevUser) => {
					const newUser = {
						...prevUser,
						username: username,
						profile: updatedProfile,
					};
					localStorage.setItem("user_data", JSON.stringify(newUser));

					return newUser;
				});
			}

			navigate(`/my-collection`); // Return to profile
		} catch (err) {
			console.error(err);
			setError(t("editProfile.updateFailed"));
			setLoading(false);
		}
	};

	if (!user) return <div className="text-center mt-5">{t("editProfile.loading")}</div>;

	return (
		<div className="container py-5">
			<div className="row justify-content-center">
				<div className="col-md-8 col-lg-6">
					<div className="card shadow-sm border-0">
						<div className="card-body p-4">
							<h3 className="mb-4 fw-bold text-center">
								{t("editProfile.title")}
							</h3>

							{error && (
								<div className="alert alert-danger">
									{error}
								</div>
							)}

							<form onSubmit={handleSubmit}>
								{/* AVATAR SECTION */}
								<div className="d-flex flex-column align-items-center mb-4">
									<div
										className="rounded-circle overflow-hidden mb-3 border border-3 border-light shadow-sm"
										style={{
											width: "120px",
											height: "120px",
											position: "relative",
											backgroundColor: "#f0f0f0",
										}}
									>
										{previewUrl ? (
											<img
												src={previewUrl}
												alt={t("editProfile.avatarPreview")}
												className="w-100 h-100"
												style={{ objectFit: "cover" }}
											/>
										) : (
											// Placeholder (initial letter)
											<div className="w-100 h-100 d-flex align-items-center justify-content-center bg-primary text-white fs-1">
												{user.username
													.charAt(0)
													.toUpperCase()}
											</div>
										)}
									</div>

									<label className="btn btn-outline-primary btn-sm">
										{t("editProfile.changePhoto")}
										<input
											type="file"
											hidden
											accept="image/*"
											onChange={handleFileChange}
										/>
									</label>
								</div>

								{/* USERNAME SECTION */}
								<div className="mb-3">
									<label className="form-label fw-bold">
										{t("editProfile.username")}
										{isUsernameLocked && (
											<span
												className="badge bg-secondary ms-2"
												style={{ fontSize: "0.7rem" }}
											>
												{t("editProfile.changeLimitReached")}
											</span>
										)}
									</label>
									<div className="input-group has-validation">
										<span className="input-group-text bg-light text-muted">
											@
										</span>
										<input
											type="text"
											className={`form-control ${
												usernameError
													? "is-invalid"
													: username !==
																user.username &&
														  usernameAvailable
														? "is-valid"
														: ""
											}`}
											value={username}
											onChange={(e) =>
												setUsername(e.target.value)
											}
											required
											minLength={3}
											disabled={isUsernameLocked}
										/>

										{/* Validation Message */}
										<div className="invalid-feedback">
											{usernameError}
										</div>
										<div className="valid-feedback">
											{t("editProfile.usernameAvailable")}
										</div>
									</div>
									<div className="form-text text-danger small">
										{isUsernameLocked
											? t("editProfile.usernameLocked")
											: t("editProfile.usernameWarning")}
									</div>
								</div>

								{/* NAME & SURNAME SECTION */}
								<div className="row mb-3">
									<div className="col-6">
										<label className="form-label fw-bold">
											{t("editProfile.name")}
										</label>
										<div className="input-group">
											<span className="input-group-text bg-light border-end-0">
												<i className="bi bi-person-badge"></i>
											</span>
											<input
												type="text"
												className="form-control border-start-0"
												placeholder={t("editProfile.name")}
												value={name}
												onChange={(e) =>
													setName(e.target.value)
												}
											/>
										</div>
									</div>
									<div className="col-6">
										<label className="form-label fw-bold">
											{t("editProfile.surname")}
										</label>
										<div className="input-group">
											<span className="input-group-text bg-light border-end-0">
												<i className="bi bi-person-vcard"></i>
											</span>
											<input
												type="text"
												className="form-control border-start-0"
												placeholder={t("editProfile.surname")}
												value={surname}
												onChange={(e) =>
													setSurname(e.target.value)
												}
											/>
										</div>
									</div>
								</div>

								{/* COUNTRY SECTION (AUTOCOMPLETE) */}
								<div className="mb-3 position-relative">
									<label className="form-label fw-bold">
										{t("editProfile.country")}
									</label>
									<div className="input-group">
										{/* Display flag in input if country is selected */}
										{selectedCountry?.flag ? (
											<span className="input-group-text bg-white border-end-0 pe-1">
												<img
													src={selectedCountry.flag}
													alt="flag"
													style={{
														height: "16px",
														borderRadius: "2px",
													}}
												/>
											</span>
										) : (
											<span className="input-group-text bg-white border-end-0 pe-1">
												<i className="bi bi-geo-alt text-muted"></i>
											</span>
										)}

										<input
											type="text"
											className="form-control border-start-0 ps-2"
											placeholder={t("editProfile.countryPlaceholder")}
											value={countrySearch}
											onChange={handleCountrySearch}
											// Show list on input click:
											onFocus={() => {
												setShowCountryDropdown(true);
												setFilteredCountries(
													countrySearch
														? countriesList.filter(
																(c) =>
																	c.name
																		.toLowerCase()
																		.includes(
																			countrySearch.toLowerCase(),
																		) ||
																	localizeCountryName(c.name, t)
																		.toLowerCase()
																		.includes(
																			countrySearch.toLowerCase(),
																		),
															)
														: countriesList,
												);
											}}
											// Hide list on input blur (timeout to allow click on list item first)
											onBlur={() =>
												setTimeout(
													() =>
														setShowCountryDropdown(
															false,
														),
													200,
												)
											}
										/>
									</div>

									{/* Country dropdown */}
									{showCountryDropdown &&
										filteredCountries.length > 0 && (
											<ul
												className="dropdown-menu show w-100 position-absolute shadow-sm"
												style={{
													top: "100%",
													left: 0,
													zIndex: 1050,
													maxHeight: "250px",
													overflowY: "auto",
													marginTop: "2px",
												}}
											>
												{filteredCountries.map((c) => (
													<li key={c.id}>
														<button
															type="button"
															className="dropdown-item d-flex align-items-center gap-2 py-2"
															onClick={() =>
																handleSelectCountry(
																	c,
																)
															}
														>
															{c.flag && (
																<img
																	src={c.flag}
																	alt="flag"
																	style={{
																		height: "16px",
																		borderRadius:
																			"2px",
																	}}
																/>
															)}
															{localizeCountryName(c.name, t)}
														</button>
													</li>
												))}
											</ul>
										)}
								</div>

								{/* BIO SECTION */}
								<div className="mb-3">
									<label className="form-label fw-bold">
										{t("editProfile.bio")}
									</label>
									<textarea
										className="form-control"
										rows="4"
										placeholder={t("editProfile.bioPlaceholder")}
										value={bio}
										onChange={(e) => setBio(e.target.value)}
										maxLength={500}
									></textarea>
									<div className="form-text text-end">
										{bio.length}/500
									</div>
								</div>

								{/* --- CONTACT INFO --- */}
								<h5 className="fw-bold mb-3">{t("editProfile.contactInfo")}</h5>
								<div className="mb-3">
									<label className="form-label small fw-bold text-muted">
										{t("editProfile.publicContactEmail")}
									</label>
									<div className="input-group">
										<span className="input-group-text bg-light border-end-0">
											<i className="bi bi-envelope"></i>
										</span>
										<input
											type="email"
											className="form-control border-start-0"
											placeholder="contact@example.com"
											value={contactEmail}
											onChange={(e) =>
												setContactEmail(e.target.value)
											}
										/>
									</div>
									<div className="form-text">
										{t("editProfile.publicContactEmailHelp")}
									</div>
								</div>

								<div className="mb-3">
									<label className="form-label small fw-bold text-muted">
										{t("editProfile.websitePortfolio")}
									</label>
									<div className="input-group">
										<span className="input-group-text bg-light border-end-0">
											<i className="bi bi-globe"></i>
										</span>
										<input
											type="url"
											className="form-control border-start-0"
											placeholder="https://mywebsite.com"
											value={websiteLink}
											onChange={(e) =>
												setWebsiteLink(e.target.value)
											}
										/>
									</div>
								</div>

								{/* --- SOCIAL MEDIA --- */}
								<h5 className="fw-bold mb-3 mt-4">
									{t("editProfile.socialMedia")}
								</h5>
								<div className="row">
									<div className="col-6">
										<SocialInput
											label="Instagram"
											iconClass="bi-instagram"
											value={instagramLink}
											setValue={setInstagramLink}
											placeholder="https://instagram.com/..."
										/>
									</div>
									<div className="col-6">
										<SocialInput
											label="Twitter / X"
											iconClass="bi-twitter-x"
											value={twitterLink}
											setValue={setTwitterLink}
											placeholder="https://twitter.com/..."
										/>
									</div>
									<div className="col-6">
										<SocialInput
											label="TikTok"
											iconClass="bi-tiktok"
											value={tiktokLink}
											setValue={setTiktokLink}
											placeholder="https://tiktok.com/..."
										/>
									</div>
									<div className="col-6">
										<SocialInput
											label="YouTube"
											iconClass="bi-youtube"
											value={youTubeLink}
											setValue={setYouTubeLink}
											placeholder="https://youtube.com/..."
										/>
									</div>
									<div className="col-12">
										<SocialInput
											label="Facebook"
											iconClass="bi-facebook"
											value={facebookLink}
											setValue={setFacebookLink}
											placeholder="https://facebook.com/..."
										/>
									</div>
								</div>

								{/* --- MARKETPLACES --- */}
								<h5 className="fw-bold mb-3 mt-4">
									{t("editProfile.marketplaces")}
								</h5>

								<SocialInput
									label="Vinted"
									iconClass="bi-shop"
									value={vintedLink}
									setValue={setVintedLink}
									placeholder="https://vinted.com/member/..."
								/>
								<SocialInput
									label="Depop"
									iconClass="bi-bag-heart"
									value={depopLink}
									setValue={setDepopLink}
									placeholder="https://depop.com/..."
								/>
								<SocialInput
									label="eBay"
									iconClass="bi-cart"
									value={ebayLink}
									setValue={setEbayLink}
									placeholder="https://ebay.com/usr/..."
								/>

								{/* BUTTONS */}
								<div className="d-grid gap-2">
									<button
										type="submit"
										className="btn btn-primary py-2"
										disabled={loading}
									>
										{loading ? (
											<>
												<span className="spinner-border spinner-border-sm me-2"></span>
												{t("forms.saving")}
											</>
										) : (
											t("forms.saveChanges")
										)}
									</button>

									<button
										type="button"
										className="btn btn-light text-muted"
										onClick={() => navigate(-1)}
									>
										{t("common.cancel")}
									</button>
								</div>
							</form>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
};

export default EditProfilePage;
