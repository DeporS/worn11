import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const DEFAULT_VARIANTS = {
	flag: {
		shapeClass: "catalog-thumbnail--flag",
		fallbackClass: "catalog-thumbnail-placeholder--flag",
		placeholder: "No flag",
	},
	logo: {
		shapeClass: "catalog-thumbnail--logo",
		fallbackClass: "catalog-thumbnail-placeholder--logo",
		placeholder: "No logo",
	},
};

const CatalogImagePreview = ({
	src,
	alt,
	variant = "logo",
	previewLabel,
	fallbackLabel,
	showLabel = false,
	className = "",
}) => {
	const { t } = useTranslation();
	const [broken, setBroken] = useState(false);

	useEffect(() => {
		setBroken(false);
	}, [src]);

	const config = DEFAULT_VARIANTS[variant] || DEFAULT_VARIANTS.logo;
	const displayPreviewLabel = previewLabel || t("admin.catalog.imagePreview");
	const displayFallbackLabel = fallbackLabel || config.placeholder;

	if (!src || broken) {
		return (
			<div className={`catalog-thumbnail-shell ${config.shapeClass} ${className}`.trim()}>
				{showLabel ? <div className="catalog-thumbnail-label">{displayPreviewLabel}</div> : null}
				<div className={`catalog-thumbnail-placeholder ${config.fallbackClass}`}>
					<span>{displayFallbackLabel}</span>
				</div>
			</div>
		);
	}

	return (
		<div className={`catalog-thumbnail-shell ${config.shapeClass} ${className}`.trim()}>
			{showLabel ? <div className="catalog-thumbnail-label">{displayPreviewLabel}</div> : null}
			<img
				src={src}
				alt={alt}
				className="catalog-thumbnail-image"
				onError={() => setBroken(true)}
			/>
		</div>
	);
};

export default CatalogImagePreview;
