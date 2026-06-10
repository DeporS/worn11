const CatalogModal = ({
	isOpen,
	title,
	onClose,
	onSubmit,
	submitting,
	error,
	submitLabel,
	closeLabel,
	cancelLabel,
	children,
}) => {
	if (!isOpen) return null;

	return (
		<div className="moderation-dialog-backdrop" role="presentation">
			<div
				className="moderation-dialog card shadow-lg border-0"
				role="dialog"
				aria-modal="true"
			>
				<div className="card-body moderation-dialog-body">
					<div className="d-flex align-items-start justify-content-between gap-3">
						<div>
							<h3 className="h5 fw-bold mb-1">{title}</h3>
						</div>
						<button
							type="button"
							className="btn btn-sm btn-outline-secondary"
							onClick={onClose}
							disabled={submitting}
						>
							{closeLabel}
						</button>
					</div>

					<form className="d-flex flex-column gap-3 mt-3" onSubmit={onSubmit}>
						{children}

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
								{cancelLabel}
							</button>
							<button type="submit" className="btn btn-primary" disabled={submitting}>
								{submitLabel}
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
	);
};

export default CatalogModal;
