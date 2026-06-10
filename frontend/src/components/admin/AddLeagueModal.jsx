import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

const AddLeagueModal = ({
	isOpen,
	onClose,
	onSubmit,
	submitting,
	error,
	countries,
	selectedCountryId,
}) => {
	const { t } = useTranslation();
	const [name, setName] = useState("");

	useEffect(() => {
		if (!isOpen) {
			setName("");
		}
	}, [isOpen]);

	const selectedCountry = useMemo(
		() =>
			countries.find((country) => Number(country.id) === Number(selectedCountryId)) || null,
		[countries, selectedCountryId],
	);

	if (!isOpen) return null;

	const handleSubmit = (event) => {
		event.preventDefault();
		if (!selectedCountry) return;
		onSubmit({
			name,
			country_id: selectedCountry.id,
		});
	};

	return (
		<div className="moderation-dialog-backdrop" role="presentation">
			<div
				className="moderation-dialog card shadow-lg border-0"
				role="dialog"
				aria-modal="true"
				aria-labelledby="add-league-title"
			>
				<div className="card-body moderation-dialog-body">
					<div className="d-flex align-items-start justify-content-between gap-3">
						<div>
							<h3 id="add-league-title" className="h5 fw-bold mb-1">
								{t("moderation.leagues.addTitle")}
							</h3>
						</div>
						<button
							type="button"
							className="btn btn-sm btn-outline-secondary"
							onClick={onClose}
							disabled={submitting}
						>
							{t("common.cancel")}
						</button>
					</div>

					<form className="d-flex flex-column gap-3 mt-3" onSubmit={handleSubmit}>
						<div>
							<label className="form-label fw-semibold">
								{t("moderation.leagues.country")}
							</label>
							<input
								type="text"
								className="form-control"
								value={selectedCountry?.name || ""}
								disabled
							/>
						</div>

						<div>
							<label className="form-label fw-semibold">
								{t("moderation.leagues.name")}
							</label>
							<input
								type="text"
								className="form-control"
								value={name}
								onChange={(event) => setName(event.target.value)}
								disabled={submitting}
							/>
						</div>

						{error ? (
							<div className="alert alert-danger mb-0" role="alert">
								{error}
							</div>
						) : null}

						<div className="d-flex justify-content-end gap-2">
							<button
								type="button"
								className="btn btn-outline-secondary"
								onClick={onClose}
								disabled={submitting}
							>
								{t("common.cancel")}
							</button>
							<button
								type="submit"
								className="btn btn-primary"
								disabled={submitting || !selectedCountry}
							>
								{t("moderation.leagues.create")}
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
	);
};

export default AddLeagueModal;
