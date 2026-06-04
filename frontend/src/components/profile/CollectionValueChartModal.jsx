import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getMyCollectionValueHistory } from "../../services/api";
import CollectionValueLineChart from "./CollectionValueLineChart";

const CollectionValueChartModal = ({ isOpen, onClose }) => {
	const { t } = useTranslation();
	const [history, setHistory] = useState([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState(false);

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
		if (!isOpen) return;

		let isCancelled = false;

		const loadHistory = async () => {
			setLoading(true);
			setError(false);
			try {
				const response = await getMyCollectionValueHistory();
				if (isCancelled) return;
				setHistory(Array.isArray(response?.results) ? response.results : []);
			} catch (loadError) {
				if (isCancelled) return;
				setError(true);
			} finally {
				if (!isCancelled) {
					setLoading(false);
				}
			}
		};

		loadHistory();

		return () => {
			isCancelled = true;
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
				className="collection-value-modal"
				onClick={(event) => event.stopPropagation()}
			>
				<div className="collection-value-modal-header">
					<div>
						<h5 className="mb-1 fw-bold">{t("collectionValue.title")}</h5>
						<p className="mb-0 text-muted collection-value-modal-subtitle">
							{t("collectionValue.subtitle")}
						</p>
					</div>
					<button
						type="button"
						className="btn-close"
						onClick={onClose}
						aria-label={t("collectionValue.close")}
					></button>
				</div>
				<div className="collection-value-modal-body">
					{loading ? (
						<div className="collection-value-status">
							{t("collectionValue.loading")}
						</div>
					) : error ? (
						<div className="collection-value-status text-danger">
							{t("collectionValue.error")}
						</div>
					) : (
						<CollectionValueLineChart points={history} />
					)}
				</div>
			</div>
		</div>
	);
};

export default CollectionValueChartModal;
