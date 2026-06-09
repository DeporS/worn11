import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigationType } from "react-router-dom";
import api, { getApprovedTeamSeasonKitTypes } from "../services/api";

// Importy nowych komponentów
import LeaguesGrid from "../components/history/LeaguesGrid";
import TeamsGrid from "../components/history/TeamsGrid";
import KitsGrid from "../components/history/KitsGrid";

// Import CSS
import "../styles/history.css";

const HistoryPage = ({ user }) => {
	const { t } = useTranslation();
	const navType = useNavigationType();
	const [loading, setLoading] = useState(false);

	// --- DATA ---
	const [leagues, setLeagues] = useState([]);
	const [teams, setTeams] = useState([]);
	const [kits, setKits] = useState([]);
	const [kitTypes, setKitTypes] = useState([]);
	const [approvedTeamSeasonTypes, setApprovedTeamSeasonTypes] = useState([]);

	// --- STATE WITH SESSION STORAGE ---
	const [step, setStep] = useState(() => {
		if (navType !== "POP") return 1; // Default to step 1 on normal navigation, but restore on back/forward

		const saved = sessionStorage.getItem("history_step");
		return saved ? parseInt(saved) : 1;
	});

	const [selectedLeague, setSelectedLeague] = useState(() => {
		if (navType !== "POP") return null;

		const saved = sessionStorage.getItem("history_league");
		return saved ? JSON.parse(saved) : null;
	});

	const [selectedTeam, setSelectedTeam] = useState(() => {
		if (navType !== "POP") return null;

		const saved = sessionStorage.getItem("history_team");
		return saved ? JSON.parse(saved) : null;
	});

	// Save to session storage on changes
	useEffect(() => {
		sessionStorage.setItem("history_step", step);
		sessionStorage.setItem(
			"history_league",
			JSON.stringify(selectedLeague),
		);
		sessionStorage.setItem("history_team", JSON.stringify(selectedTeam));
	}, [step, selectedLeague, selectedTeam]);

	// 1. Fetch Leagues
	useEffect(() => {
		setLoading(true);
		Promise.all([api.get("/leagues/"), api.get("/options/")])
			.then(([leaguesResponse, optionsResponse]) => {
				setLeagues(leaguesResponse.data);
				setKitTypes(optionsResponse.data.kit_types || []);
				setLoading(false);
			})
			.catch((err) => {
				console.error(err);
				setLoading(false);
			});
	}, []);

	// 2. Fetch Teams
	useEffect(() => {
		if (selectedLeague && step === 2) {
			setLoading(true);
			api.get(`/teams/league/${selectedLeague.id}/`)
				.then((res) => {
					setTeams(res.data);
					setLoading(false);
				})
				.catch((err) => setLoading(false));
		}
	}, [selectedLeague, step]);

	// 3. Fetch Kits
	useEffect(() => {
		if (selectedTeam && step === 3) {
			setLoading(true);
			Promise.all([
				api.get(`/kits/team/${selectedTeam.id}/best/`),
				getApprovedTeamSeasonKitTypes(selectedTeam.id),
			])
				.then(([kitsResponse, approvedTypesResponse]) => {
					setKits(kitsResponse.data.results || kitsResponse.data);
					setApprovedTeamSeasonTypes(approvedTypesResponse || []);
					setLoading(false);
				})
				.catch((err) => setLoading(false));
		} else if (step !== 3) {
			setApprovedTeamSeasonTypes([]);
		}
	}, [selectedTeam, step]);

	// Handlers
	const handleSelectLeague = (league) => {
		setSelectedLeague(league);
		setStep(2);
	};

	const handleSelectTeam = (team) => {
		setSelectedTeam(team);
		setStep(3);
	};

	const handleReset = (targetStep) => {
		setStep(targetStep);
		if (targetStep === 1) {
			setSelectedLeague(null);
			setSelectedTeam(null);
		} else if (targetStep === 2) {
			setSelectedTeam(null);
		}
	};

	return (
		<div className="container py-5" style={{ maxWidth: "1400px" }}>
			{/* HEADER & BREADCRUMBS */}
			<div className="mb-5">
				<nav aria-label="breadcrumb">
					<ol className="breadcrumb fs-5 align-items-center">
						<li
							className={`breadcrumb-item ${step === 1 ? "active" : ""}`}
						>
							<span
								role="button"
								className={
									step > 1 ? "breadcrumb-link" : "fw-semibold"
								}
								onClick={() => handleReset(1)}
							>
								{t("history.leagues")}
							</span>
						</li>
						{step > 1 && selectedLeague && (
							<li
								className={`breadcrumb-item ${step === 2 ? "active" : ""}`}
							>
								<span
									role="button"
									className={
										step > 2
											? "breadcrumb-link"
											: "breadcrumb-item active"
									}
									onClick={() => handleReset(2)}
								>
									{selectedLeague.name}
								</span>
							</li>
						)}
						{step > 2 && selectedTeam && (
							<li className="breadcrumb-item active">
								{selectedTeam.name}
							</li>
						)}
					</ol>
				</nav>
			</div>

			{/* --- VIEW SWITCHER --- */}
			{step === 1 && (
				<LeaguesGrid
					leagues={leagues}
					loading={loading}
					onSelectLeague={handleSelectLeague}
				/>
			)}

			{step === 2 && (
				<TeamsGrid
					teams={teams}
					loading={loading}
					selectedLeagueName={selectedLeague?.name}
					onSelectTeam={handleSelectTeam}
				/>
			)}

			{step === 3 && (
				<KitsGrid
					kits={kits}
					kitTypes={kitTypes}
					approvedTeamSeasonTypes={approvedTeamSeasonTypes}
					loading={loading}
					selectedTeamName={selectedTeam?.name}
					selectedTeamId={selectedTeam?.id}
					user={user}
				/>
			)}
		</div>
	);
};

export default HistoryPage;
