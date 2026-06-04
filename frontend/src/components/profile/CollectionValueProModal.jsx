import { useEffect } from "react";
import { useTranslation } from "react-i18next";

const CollectionValueProModal = ({ isOpen, onClose }) => {
	const { t } = useTranslation();

	useEffect(() => {
		if (!isOpen) {
			return undefined;
		}

		document.body.style.overflow = "hidden";
		return () => {
			document.body.style.overflow = "unset";
		};
	}, [isOpen]);

	useEffect(() => {
		if (!isOpen) return undefined;

		const handleKeyDown = (event) => {
			if (event.key === "Escape") {
				onClose();
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onClose]);

	if (!isOpen) {
		return null;
	}

	return (
		<div className="collection-value-modal-backdrop" onClick={onClose}>
			<div
				className="collection-value-modal collection-value-pro-modal"
				onClick={(event) => event.stopPropagation()}
			>
				<div className="collection-value-modal-header">
					<div>
						<h5 className="mb-1 fw-bold">{t("collectionValue.proTitle")}</h5>
						<p className="mb-0 text-muted collection-value-modal-subtitle">
							{t("collectionValue.proSubtitle")}
						</p>
					</div>
					<button
						type="button"
						className="btn-close"
						onClick={onClose}
						aria-label={t("collectionValue.proClose")}
					></button>
				</div>
				<div className="collection-value-modal-body">
					<div className="collection-value-pro-benefits">
						<div className="collection-value-pro-benefit">
							<span className="collection-value-pro-benefit-icon">📈</span>
							<span>{t("collectionValue.proBenefitChart")}</span>
						</div>
						<div className="collection-value-pro-benefit">
							<span className="collection-value-pro-benefit-icon">💎</span>
							<span>{t("collectionValue.proBenefitInsights")}</span>
						</div>
						<div className="collection-value-pro-benefit">
							<span className="collection-value-pro-benefit-icon">🕒</span>
							<span>{t("collectionValue.proBenefitTracking")}</span>
						</div>
					</div>
					<div className="collection-value-pro-actions">
						<button
							type="button"
							className="btn btn-outline-secondary rounded-pill px-4"
							onClick={onClose}
						>
							{t("collectionValue.proClose")}
						</button>
						<a
							href="/get-pro"
							className="btn btn-primary rounded-pill px-4 fw-semibold"
						>
							{t("collectionValue.proUpgrade")}
						</a>
					</div>
				</div>
			</div>
		</div>
	);
};

export default CollectionValueProModal;
