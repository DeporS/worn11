import { useEffect, useState } from "react";
import Swal from "sweetalert2";

import { reportKit } from "../../services/api";

const REPORT_REASONS = [
	{ value: "wrong_team", label: "Wrong team" },
	{ value: "wrong_season", label: "Wrong season" },
	{ value: "wrong_kit_type", label: "Wrong kit type" },
	{ value: "wrong_details", label: "Wrong details" },
	{ value: "fake_or_misleading", label: "Fake or misleading" },
	{ value: "prohibited_content", label: "Prohibited content" },
	{ value: "spam", label: "Spam" },
	{ value: "harassment_or_abuse", label: "Harassment or abuse" },
	{ value: "other", label: "Other" },
];

const ReportKitModal = ({ isOpen, onClose, kitId }) => {
	const [reason, setReason] = useState("");
	const [description, setDescription] = useState("");
	const [submitting, setSubmitting] = useState(false);

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
			Swal.fire("Error", "Please select a reason.", "error");
			return;
		}

		if (reason === "other" && !trimmedDescription) {
			Swal.fire("Error", "Please add a description for Other.", "error");
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
			Swal.fire("Success", "Report submitted successfully.", "success");
		} catch (error) {
			const message =
				error?.response?.data?.detail ||
				error?.response?.data?.description?.[0] ||
				error?.response?.data?.reason?.[0] ||
				"Could not submit report.";
			Swal.fire("Error", message, "error");
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
					<h5 className="fw-bold mb-0">Report kit</h5>
					<button className="btn-close" onClick={onClose}></button>
				</div>
				<div className="card-body">
					<div className="mb-3">
						<label className="form-label small text-muted">Reason</label>
						<select
							className="form-select"
							value={reason}
							onChange={(e) => setReason(e.target.value)}
							disabled={submitting}
						>
							<option value="">Select a reason</option>
							{REPORT_REASONS.map((option) => (
								<option key={option.value} value={option.value}>
									{option.label}
								</option>
							))}
						</select>
					</div>

					<div className="mb-3">
						<label className="form-label small text-muted">
							Description {reason === "other" ? "(Required)" : "(Optional)"}
						</label>
						<textarea
							className="form-control"
							rows="4"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							disabled={submitting}
							placeholder="Add a few details to help moderators review this report."
						/>
					</div>

					<div className="d-flex justify-content-end gap-2">
						<button
							type="button"
							className="btn btn-outline-secondary rounded-pill px-4"
							onClick={onClose}
							disabled={submitting}
						>
							Cancel
						</button>
						<button
							type="button"
							className="btn btn-danger rounded-pill px-4"
							onClick={handleSubmit}
							disabled={submitting}
						>
							{submitting ? "Submitting..." : "Submit report"}
						</button>
					</div>
				</div>
			</div>
		</div>
	);
};

export default ReportKitModal;
