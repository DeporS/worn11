import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Swal from "sweetalert2";

import { reportKit } from "../../services/api";

const ReportKitModal = ({ isOpen, onClose, kitId }) => {
	const { t } = useTranslation();
	const [reason, setReason] = useState("");
	const [description, setDescription] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const reportReasons = [
		"wrong_team",
		"wrong_season",
		"wrong_kit_type",
		"wrong_details",
		"fake_or_misleading",
		"prohibited_content",
		"spam",
		"harassment_or_abuse",
		"other",
	];

	useEffect(() => {
		if (!isOpen) {
			setReason("");
			setDescription("");
		}
	}, [isOpen]);

	useEffect(() => {
		if (!isOpen) return;

		const handleKeyDown = (e) => {
			if (e.key === "Escape") {
				e.stopPropagation();
				onClose();
			}
		};

		window.addEventListener("keydown", handleKeyDown);
		return () => window.removeEventListener("keydown", handleKeyDown);
	}, [isOpen, onClose]);

	if (!isOpen) return null;

	const handleSubmit = async () => {
		const trimmedDescription = description.trim();

		if (!reason) {
			Swal.fire(t("common.error"), t("report.selectReasonError"), "error");
			return;
		}

		if (reason === "other" && !trimmedDescription) {
			Swal.fire(t("common.error"), t("report.otherDescriptionError"), "error");
			return;
		}

		try {
			setSubmitting(true);
			const payload = {
				reason,
				description: trimmedDescription,
			};

			await reportKit(kitId, payload);
			onClose();
			Swal.fire(t("common.success"), t("report.success"), "success");
		} catch (error) {
			const message =
				error?.response?.data?.detail ||
				error?.response?.data?.description?.[0] ||
				error?.response?.data?.reason?.[0] ||
				t("report.submitError");
			Swal.fire(t("common.error"), message, "error");
		} finally {
			setSubmitting(false);
		}
	};

	return (
		<div
			className="report-kit-backdrop d-flex justify-content-center align-items-center"
			style={{
				position: "fixed",
				top: 0,
				left: 0,
				width: "100%",
				height: "100%",
				backgroundColor: "rgba(0, 0, 0, 0.8)",
			}}
			onClick={onClose}
		>
			<div
				className="report-kit-dialog card shadow"
				style={{
					width: "92%",
					maxWidth: "520px",
				}}
				onMouseDown={(e) => e.stopPropagation()}
				onKeyDown={(e) => e.stopPropagation()}
				onClick={(e) => e.stopPropagation()}
			>
				<div className="card-header bg-white d-flex justify-content-between align-items-center border-bottom-0 pt-3 pb-2">
					<h5 className="fw-bold mb-0">{t("report.title")}</h5>
					<button className="btn-close" onClick={onClose}></button>
				</div>
				<div className="card-body">
					<div className="mb-3">
						<label className="form-label small text-muted">{t("report.reason")}</label>
						<select
							className="form-select"
							value={reason}
							onChange={(e) => setReason(e.target.value)}
							disabled={submitting}
						>
							<option value="">{t("report.selectReason")}</option>
							{reportReasons.map((value) => (
								<option key={value} value={value}>
									{t(`report.reasons.${value}`)}
								</option>
							))}
						</select>
					</div>

					<div className="mb-3">
						<label className="form-label small text-muted">
							{t(reason === "other" ? "report.descriptionRequired" : "report.descriptionOptional")}
						</label>
						<textarea
							className="form-control"
							rows="4"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							disabled={submitting}
							placeholder={t("report.placeholder")}
						/>
					</div>

					<div className="d-flex justify-content-end gap-2">
						<button
							type="button"
							className="btn btn-outline-secondary rounded-pill px-4"
							onClick={onClose}
							disabled={submitting}
						>
							{t("report.cancel")}
						</button>
						<button
							type="button"
							className="btn btn-danger rounded-pill px-4"
							onClick={handleSubmit}
							disabled={submitting}
						>
							{submitting ? t("report.submitting") : t("report.submit")}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
};

export default ReportKitModal;
