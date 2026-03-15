import { useState, useEffect } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { getKitVariants } from "../services/api";
import KitCardHistory from "../components/history/KitCardHistory";

const KitVariantsPage = ({ user }) => {
	const { teamId } = useParams();
	const [searchParams] = useSearchParams();
	const navigate = useNavigate();

	const season = searchParams.get("season");
	const type = searchParams.get("type");

	const [kits, setKits] = useState([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		setLoading(true);
		getKitVariants(teamId, season, type)
			.then((data) => {
				setKits(data.results || data);
			})
			.catch((err) => console.error(err))
			.finally(() => setLoading(false));
	}, [teamId, season, type]);

	return (
		<div className="container py-5" style={{ maxWidth: "1400px" }}>
			<button className="btn btn-light mb-4" onClick={() => navigate(-1)}>
				&larr; Back to Museum
			</button>

			<h2 className="mb-4 fw-bold">
				{type} Kits from {season} Season
			</h2>

			{loading ? (
				<div className="text-center py-5">
					<div className="spinner-border text-primary"></div>
				</div>
			) : (
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
					) : (
						<p className="text-muted">
							No kits found for this season and type.
						</p>
					)}
				</div>
			)}
		</div>
	);
};

export default KitVariantsPage;
