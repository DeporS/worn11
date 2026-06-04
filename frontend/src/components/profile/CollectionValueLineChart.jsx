import React, { useState } from "react";
import { useTranslation } from "react-i18next";

const CHART_WIDTH = 720;
const CHART_HEIGHT = 280;
const PADDING_X = 36;
const PADDING_Y = 24;
const DESKTOP_TOOLTIP_EDGE_INSET = 18;
const DESKTOP_TOOLTIP_VERTICAL_THRESHOLD = 78;

const formatCurrency = (value) =>
	`$${Number(value || 0).toLocaleString(undefined, {
		maximumFractionDigits: 0,
	})}`;

const formatPointDate = (value, language) =>
	new Intl.DateTimeFormat(language, {
		day: "numeric",
		month: "short",
		year: "numeric",
	}).format(new Date(value));

const getReasonLabel = (reason, t) => {
	const reasonKeyMap = {
		initial: "collectionValue.reasonInitial",
		kit_added: "collectionValue.reasonKitAdded",
		kit_removed: "collectionValue.reasonKitRemoved",
		kit_updated: "collectionValue.reasonKitUpdated",
		value_updated: "collectionValue.reasonValueUpdated",
		collection_status_changed: "collectionValue.reasonCollectionStatusChanged",
		backfill: "collectionValue.reasonBackfill",
	};

	return reasonKeyMap[reason] ? t(reasonKeyMap[reason]) : reason;
};

const CollectionValueLineChart = ({ points = [] }) => {
	const { t, i18n } = useTranslation();
	const [activePoint, setActivePoint] = useState(null);
	const hasPoints = Array.isArray(points) && points.length > 0;
	const lastRawPoint = hasPoints ? points[points.length - 1] : null;
	const summaryValue = hasPoints ? formatCurrency(lastRawPoint.total_value) : formatCurrency(0);
	const summaryCount = lastRawPoint?.kits_count || 0;

	if (!Array.isArray(points) || points.length < 2) {
		return (
			<div className="collection-value-chart-shell">
				<div className="collection-value-chart-summary">
					<div>
						<span className="collection-value-summary-label">
							{t("collectionValue.currentValue")}
						</span>
						<div className="collection-value-summary-number">
							{summaryValue}
						</div>
					</div>
					<div className="collection-value-summary-count">
						{t("collectionValue.kitsCount", { count: summaryCount })}
					</div>
				</div>
				<div className="collection-value-empty">
					{t("collectionValue.empty")}
				</div>
			</div>
		);
	}

	const values = points.map((point) => Number(point.total_value || 0));
	const minValue = Math.min(...values);
	const maxValue = Math.max(...values);
	const valueRange = maxValue - minValue || 1;
	const stepX = points.length > 1 ? (CHART_WIDTH - PADDING_X * 2) / (points.length - 1) : 0;

	const chartPoints = points.map((point, index) => {
		const x = PADDING_X + index * stepX;
		const normalized = (Number(point.total_value || 0) - minValue) / valueRange;
		const y = CHART_HEIGHT - PADDING_Y - normalized * (CHART_HEIGHT - PADDING_Y * 2);
		return {
			...point,
			x,
			y,
			labelDate: formatPointDate(point.created_at, i18n.language),
			labelValue: formatCurrency(point.total_value),
		};
	});

	const path = chartPoints
		.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
		.join(" ");

	const firstPoint = chartPoints[0];
	const lastPoint = chartPoints[chartPoints.length - 1];
	const desktopTooltipPosition = activePoint
		? {
				left:
					activePoint.x > CHART_WIDTH * 0.8
						? `${((activePoint.x - DESKTOP_TOOLTIP_EDGE_INSET) / CHART_WIDTH) * 100}%`
						: activePoint.x < CHART_WIDTH * 0.2
							? `${((activePoint.x + DESKTOP_TOOLTIP_EDGE_INSET) / CHART_WIDTH) * 100}%`
							: `${(activePoint.x / CHART_WIDTH) * 100}%`,
				top: `${(activePoint.y / CHART_HEIGHT) * 100}%`,
				align:
					activePoint.x > CHART_WIDTH * 0.8
						? "right"
						: activePoint.x < CHART_WIDTH * 0.2
							? "left"
							: "center",
				vertical:
					activePoint.y < DESKTOP_TOOLTIP_VERTICAL_THRESHOLD
						? "below"
						: "above",
			}
		: null;
	return (
		<div className="collection-value-chart-shell">
			<div className="collection-value-chart-summary">
				<div>
					<span className="collection-value-summary-label">
						{t("collectionValue.currentValue")}
					</span>
					<div className="collection-value-summary-number">
						{lastPoint.labelValue}
					</div>
				</div>
				<div className="collection-value-summary-count">
					{t("collectionValue.kitsCount", { count: lastPoint.kits_count || 0 })}
				</div>
			</div>
			<div
				className="collection-value-chart-frame"
				onMouseLeave={() => setActivePoint(null)}
				onPointerDown={() => setActivePoint(null)}
			>
				{activePoint && desktopTooltipPosition ? (
					<div
						className={`collection-value-chart-tooltip collection-value-chart-tooltip-${desktopTooltipPosition.align} collection-value-chart-tooltip-${desktopTooltipPosition.vertical}`}
						style={{
							left: desktopTooltipPosition.left,
							top: desktopTooltipPosition.top,
						}}
					>
						<div className="collection-value-chart-tooltip-row">
							<span className="collection-value-chart-tooltip-label">
								{t("collectionValue.tooltipValue")}
							</span>
							<span className="collection-value-chart-tooltip-value">
								{activePoint.labelValue}
							</span>
						</div>
						<div className="collection-value-chart-tooltip-row">
							<span className="collection-value-chart-tooltip-label">
								{t("collectionValue.tooltipDate")}
							</span>
							<span className="collection-value-chart-tooltip-value">
								{activePoint.labelDate}
							</span>
						</div>
						<div className="collection-value-chart-tooltip-row">
							<span className="collection-value-chart-tooltip-label">
								{t("collectionValue.tooltipKits")}
							</span>
							<span className="collection-value-chart-tooltip-value">
								{t("collectionValue.kitsCount", {
									count: activePoint.kits_count || 0,
								})}
							</span>
						</div>
						{activePoint.reason ? (
							<div className="collection-value-chart-tooltip-row">
								<span className="collection-value-chart-tooltip-label">
									{t("collectionValue.tooltipReason")}
								</span>
								<span className="collection-value-chart-tooltip-value">
									{getReasonLabel(activePoint.reason, t)}
								</span>
							</div>
						) : null}
					</div>
				) : null}
				<svg
					viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
					className="collection-value-chart"
					role="img"
					aria-label={t("collectionValue.title")}
				>
					<line
						x1={PADDING_X}
						y1={CHART_HEIGHT - PADDING_Y}
						x2={CHART_WIDTH - PADDING_X}
						y2={CHART_HEIGHT - PADDING_Y}
						className="collection-value-axis"
					/>
					<line
						x1={PADDING_X}
						y1={PADDING_Y}
						x2={PADDING_X}
						y2={CHART_HEIGHT - PADDING_Y}
						className="collection-value-axis"
					/>
					<path d={path} className="collection-value-line" />
					{chartPoints.map((point) => (
						<g key={point.id}>
							<circle
								cx={point.x}
								cy={point.y}
								r="4.5"
								className="collection-value-dot"
								onMouseEnter={() => setActivePoint(point)}
								onFocus={() => setActivePoint(point)}
								onBlur={() => setActivePoint(null)}
								onPointerDown={(event) => {
									event.stopPropagation();
									setActivePoint(point);
								}}
								tabIndex="0"
							>
								<title>{`${point.labelDate} • ${point.labelValue}`}</title>
							</circle>
						</g>
					))}
					<text x={firstPoint.x} y={CHART_HEIGHT - 6} className="collection-value-axis-label" textAnchor="start">
						{firstPoint.labelDate}
					</text>
					<text x={lastPoint.x} y={CHART_HEIGHT - 6} className="collection-value-axis-label" textAnchor="end">
						{lastPoint.labelDate}
					</text>
					<text x={PADDING_X - 8} y={PADDING_Y + 4} className="collection-value-axis-label" textAnchor="end">
						{formatCurrency(maxValue)}
					</text>
					<text x={PADDING_X - 8} y={CHART_HEIGHT - PADDING_Y + 4} className="collection-value-axis-label" textAnchor="end">
						{formatCurrency(minValue)}
					</text>
				</svg>
			</div>
			{activePoint ? (
				<div className="collection-value-chart-point-details">
					<div className="collection-value-chart-point-details-grid">
						<div className="collection-value-chart-point-detail">
							<span className="collection-value-chart-point-detail-label">
								{t("collectionValue.tooltipValue")}
							</span>
							<span className="collection-value-chart-point-detail-value">
								{activePoint.labelValue}
							</span>
						</div>
						<div className="collection-value-chart-point-detail">
							<span className="collection-value-chart-point-detail-label">
								{t("collectionValue.tooltipDate")}
							</span>
							<span className="collection-value-chart-point-detail-value">
								{activePoint.labelDate}
							</span>
						</div>
						<div className="collection-value-chart-point-detail">
							<span className="collection-value-chart-point-detail-label">
								{t("collectionValue.tooltipKits")}
							</span>
							<span className="collection-value-chart-point-detail-value">
								{t("collectionValue.kitsCount", {
									count: activePoint.kits_count || 0,
								})}
							</span>
						</div>
						{activePoint.reason ? (
							<div className="collection-value-chart-point-detail">
								<span className="collection-value-chart-point-detail-label">
									{t("collectionValue.tooltipReason")}
								</span>
								<span className="collection-value-chart-point-detail-value">
									{getReasonLabel(activePoint.reason, t)}
								</span>
							</div>
						) : null}
					</div>
				</div>
			) : null}
		</div>
	);
};

export default CollectionValueLineChart;
