import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams, useNavigate } from "react-router-dom";
import { getKitVariants, getMyWishlist, resolveTeam } from "../services/api";
import KitCardHistory from "../components/history/KitCardHistory";
import WishlistToggleButton from "../components/wishlist/WishlistToggleButton";

const normalizeKitTypeForClient = (kitType) => {
	const normalized = (kitType || "").trim().toLowerCase();
	if (normalized === "gk" || normalized === "goalkeeper") {
		return "Goalkeeper";
	}
	if (normalized.startsWith("special")) {
		return "Special";
	}
	return kitType;
};

const KitVariantsPage = ({ user }) => {
	const { t } = useTranslation();
	const { teamIdentifier } = useParams();
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const season = searchParams.get("season");
	const type = searchParams.get("type");

	const [kits, setKits] = useState([]);
	const [teamData, setTeamData] = useState(null);
	const [isWishlisted, setIsWishlisted] = useState(false);
	const [loading, setLoading] = useState(true);
	const teamName = teamData?.name || "";
	const teamId = teamData?.id || null;
	const displayTeamName = teamName || t("history.unknownTeam");
	const addCardState = {
		prefill: {
			season,
			type,
			team: teamName,
		},
	};

	useEffect(() => {
		setLoading(true);
		getKitVariants(teamIdentifier, season, type)
			.then((data) => {
				setKits(data.results || data);
			})
			.catch((err) => console.error(err))
			.finally(() => setLoading(false));
	}, [teamIdentifier, season, type]);

	useEffect(() => {
		resolveTeam(teamIdentifier)
			.then((data) => setTeamData(data || null))
			.catch((err) => {
				console.error(err);
				setTeamData(null);
			});
	}, [teamIdentifier]);

	useEffect(() => {
		if (!user || !teamId || !season || !type) {
			setIsWishlisted(false);
			return;
		}

		let cancelled = false;

		getMyWishlist()
			.then((items) => {
				if (cancelled) {
					return;
				}
				const match = (Array.isArray(items) ? items : []).some(
					(item) =>
						item.team_id === teamId &&
						item.season === season &&
						item.kit_type === normalizeKitTypeForClient(type),
				);
				setIsWishlisted(match);
			})
			.catch((err) => {
				console.error(err);
				if (!cancelled) {
					setIsWishlisted(false);
				}
			});

		return () => {
			cancelled = true;
		};
	}, [teamId, season, type, user]);

	return (
		<div className="container py-5" style={{ maxWidth: "1400px" }}>
			<button className="btn btn-light mb-4" onClick={() => navigate(-1)}>
				&larr; {t("history.backToMuseum")}
			</button>

			<h2 className="mb-4 fw-bold">
				{t("history.variantsTitle", { team: displayTeamName, type, season })}
			</h2>

			{teamId && season && type ? (
				<div className="mb-4">
					<WishlistToggleButton
						currentUser={user}
						teamId={teamId}
						season={season}
						kitType={type}
						initialIsWishlisted={isWishlisted}
						className="btn btn-outline-dark rounded-pill px-4"
						onToggle={(payload) => setIsWishlisted(Boolean(payload?.is_wishlisted))}
					/>
				</div>
			) : null}

			{loading ? (
				<div className="text-center py-5">
					<div className="spinner-border text-primary"></div>
				</div>
			) : (
				<>
					{kits.length === 0 ? (
						<p className="text-muted mb-4">
							{t("history.variantsEmpty", { team: displayTeamName, type, season })}
						</p>
					) : null}

					<div className="row g-4">
					{kits.length > 0 ? (
						kits.map((kit) => (
							<div
								key={kit.id}
								className="col-12 col-sm-6 col-lg-4 col-xl-3"
							>
								<KitCardHistory item={kit} user={user} />
							</div>
						))
					) : null}

						<div className="col-12 col-sm-6 col-lg-4 col-xl-3">
							<Link
								to="/add-kit"
								state={addCardState}
								className="card h-100 shadow-sm text-decoration-none border-2 border-primary-subtle"
								style={{
									borderStyle: "dashed",
									minHeight: "100%",
									background:
										"linear-gradient(180deg, rgba(13,110,253,0.05) 0%, rgba(13,110,253,0.12) 100%)",
								}}
							>
								<div className="card-body d-flex flex-column align-items-center justify-content-center text-center p-4">
									<div
										className="rounded-circle border border-primary-subtle d-flex align-items-center justify-content-center mb-3"
										style={{
											width: "64px",
											height: "64px",
											backgroundColor: "rgba(13,110,253,0.08)",
										}}
									>
										<i className="bi bi-plus-lg fs-3 text-primary"></i>
									</div>
									<h3 className="h5 fw-bold text-dark mb-2">
										{t("history.addThisKit")}
									</h3>
									<p className="text-muted small mb-0">
										{t("history.addThisKitSubtitle", {
											team: displayTeamName,
											season,
											type,
										})}
									</p>
								</div>
							</Link>
						</div>
					</div>
				</>
			)}
		</div>
	);
};

export default KitVariantsPage;
