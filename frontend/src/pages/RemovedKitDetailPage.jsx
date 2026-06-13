import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { getRemovedKitDetail } from "../services/api";

const RemovedKitDetailPage = () => {
	const { t, i18n } = useTranslation();
	const navigate = useNavigate();
	const { userKitId } = useParams();
	const [kit, setKit] = useState(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() => {
		let cancelled = false;

		const loadRemovedKit = async () => {
			setLoading(true);
			setError("");
			try {
				const data = await getRemovedKitDetail(userKitId);
				if (cancelled) return;
				setKit(data);
			} catch (loadError) {
				if (cancelled) return;
				console.error("Failed to load removed kit detail", loadError);
				const statusCode = loadError?.response?.status;
				setError(
					statusCode === 403 || statusCode === 404
						? t("moderation.removedKit.noAccess")
						: t("profile.loadError"),
				);
			} finally {
				if (!cancelled) {
					setLoading(false);
				}
			}
		};

		loadRemovedKit();

		return () => {
			cancelled = true;
		};
	}, [t, userKitId]);

	const removedAtLabel = kit?.removed_at
		? new Intl.DateTimeFormat(i18n.language, {
				year: "numeric",
				month: "short",
				day: "numeric",
				hour: "2-digit",
				minute: "2-digit",
			}).format(new Date(kit.removed_at))
		: "";

	return (
		<div className="container py-5">
			{loading ? (
				<div className="text-center py-5">
					<div className="spinner-border text-primary" role="status" />
				</div>
			) : error ? (
				<div className="text-center py-5">
					<h1 className="h4 fw-bold mb-2">{t("moderation.removedKit.title")}</h1>
					<p className="text-muted mb-4">{error}</p>
					<button
						type="button"
						className="btn btn-outline-secondary rounded-pill"
						onClick={() => navigate("/my-collection")}
					>
						{t("common.cancel")}
					</button>
				</div>
			) : (
				<section className="mx-auto" style={{ maxWidth: "960px" }}>
					<div className="card border-0 shadow-sm rounded-4 overflow-hidden">
						<div className="card-body p-4 p-lg-5">
							<div className="d-flex flex-wrap align-items-start justify-content-between gap-3 mb-4">
								<div>
									<h1 className="h3 fw-bold mb-2">{t("moderation.removedKit.title")}</h1>
									<p className="text-muted mb-0">
										{t("moderation.removedKit.description")}
									</p>
								</div>
								<span className="badge rounded-pill text-bg-danger-subtle text-danger-emphasis px-3 py-2">
									{t("kitCard.removedByModerationBadge")}
								</span>
							</div>

							<div className="row g-4">
								<div className="col-12 col-lg-5">
									{kit.images?.length ? (
										<img
											src={kit.images[0].image}
											alt={kit.title}
											className="w-100 rounded-4 border"
											style={{ aspectRatio: "3 / 4", objectFit: "cover" }}
										/>
									) : (
										<div
											className="bg-light border rounded-4 d-flex align-items-center justify-content-center text-muted"
											style={{ width: "100%", aspectRatio: "3 / 4" }}
										>
											<small>{t("kitCard.noPhoto")}</small>
										</div>
									)}
								</div>

								<div className="col-12 col-lg-7">
									<h2 className="h4 fw-bold mb-3">{kit.title}</h2>
									<div className="d-grid gap-2 mb-4">
										<div><strong>{t("forms.teamName")}:</strong> {kit.team}</div>
										<div><strong>{t("kitCard.season")}:</strong> {kit.season}</div>
										<div><strong>{t("kitCard.kitType")}:</strong> {kit.kit_type}</div>
										<div><strong>{t("moderation.removedKit.removedAt")}:</strong> {removedAtLabel}</div>
									</div>

									{kit.moderation_note ? (
										<div className="rounded-4 border bg-light p-3 mb-4">
											<div className="fw-semibold mb-2">{t("moderation.removedKit.note")}</div>
											<div className="text-muted">{kit.moderation_note}</div>
										</div>
									) : null}

								</div>
							</div>
						</div>
					</div>
				</section>
			)}
		</div>
	);
};

export default RemovedKitDetailPage;
