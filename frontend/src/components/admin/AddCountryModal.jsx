import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const AddCountryModal = ({
	isOpen,
	onClose,
	onSubmit,
	submitting,
	error,
}) => {
	const { t } = useTranslation();
	const [name, setName] = useState("");
	const [code, setCode] = useState("");

	useEffect(() => {
		if (!isOpen) {
			setName("");
			setCode("");
		}
	}, [isOpen]);

	if (!isOpen) return null;

	const handleSubmit = (event) => {
		event.preventDefault();
		onSubmit({
			name,
			code,
		});
	};

	return (
		<div className="moderation-dialog-backdrop" role="presentation">
			<div
				className="moderation-dialog card shadow-lg border-0"
				role="dialog"
				aria-modal="true"
				aria-labelledby="add-country-title"
			>
				<div className="card-body moderation-dialog-body">
					<div className="d-flex align-items-start justify-content-between gap-3">
						<div>
							<h3 id="add-country-title" className="h5 fw-bold mb-1">
								{t("moderation.countries.addTitle")}
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
								{t("moderation.countries.name")}
							</label>
							<input
								type="text"
								className="form-control"
								value={name}
								onChange={(event) => setName(event.target.value)}
								disabled={submitting}
							/>
						</div>

						<div>
							<label className="form-label fw-semibold">
								{t("moderation.countries.code")}
							</label>
							<input
								type="text"
								className="form-control"
								value={code}
								onChange={(event) => setCode(event.target.value.toUpperCase())}
								disabled={submitting}
								maxLength={10}
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
							<button type="submit" className="btn btn-primary" disabled={submitting}>
								{t("moderation.countries.create")}
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
	);
};

export default AddCountryModal;
