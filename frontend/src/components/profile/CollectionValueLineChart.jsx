import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

const CHART_WIDTH = 720;
const CHART_HEIGHT = 280;
const PLOT_LEFT = 64;
const PLOT_RIGHT = 24;
const PLOT_TOP = 20;
const PLOT_BOTTOM = 38;
const DESKTOP_TOOLTIP_EDGE_INSET = 18;
const DESKTOP_TOOLTIP_VERTICAL_THRESHOLD = 78;
const DAY_IN_MS = 24 * 60 * 60 * 1000;
const MIN_VISIBLE_DAY_WINDOW_DAYS = 7;
const MIN_VISIBLE_WEEK_WINDOW_WEEKS = 6;
const MIN_VISIBLE_MONTH_WINDOW_MONTHS = 6;
const X_AXIS_TICK_COUNT = 4;

const formatCurrency = (value) =>
	`$${Number(value || 0).toLocaleString(undefined, {
		maximumFractionDigits: 0,
	})}`;

const formatDate = (value, language) =>
	new Intl.DateTimeFormat(language, {
		day: "numeric",
		month: "short",
		year: "numeric",
	}).format(value);

const formatShortDate = (value, language) =>
	new Intl.DateTimeFormat(language, {
		day: "numeric",
		month: "short",
	}).format(value);

const formatMonth = (value, language) =>
	new Intl.DateTimeFormat(language, {
		month: "long",
		year: "numeric",
	}).format(value);

const formatShortMonth = (value, language) =>
	new Intl.DateTimeFormat(language, {
		month: "short",
		year: "numeric",
	}).format(value);

const parseSnapshotDate = (snapshot) => {
	const parsedDate = new Date(snapshot?.created_at);
	return Number.isNaN(parsedDate.getTime()) ? null : parsedDate;
};

const getStartOfDay = (date) =>
	new Date(date.getFullYear(), date.getMonth(), date.getDate());

const getStartOfWeek = (date) => {
	const startOfDay = getStartOfDay(date);
	const day = startOfDay.getDay();
	const diff = day === 0 ? -6 : 1 - day;
	startOfDay.setDate(startOfDay.getDate() + diff);
	return startOfDay;
};

const getStartOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1);

const addDays = (date, days) => {
	const nextDate = new Date(date);
	nextDate.setDate(nextDate.getDate() + days);
	return nextDate;
};

const addWeeks = (date, weeks) => addDays(date, weeks * 7);

const addMonths = (date, months) =>
	new Date(date.getFullYear(), date.getMonth() + months, 1);

const getDateRangeDays = (snapshots) => {
	if (snapshots.length <= 1) {
		return 0;
	}

	const firstDate = parseSnapshotDate(snapshots[0]);
	const lastDate = parseSnapshotDate(snapshots[snapshots.length - 1]);
	if (!firstDate || !lastDate) {
		return 0;
	}

	return Math.max(
		0,
		Math.round((getStartOfDay(lastDate) - getStartOfDay(firstDate)) / DAY_IN_MS),
	);
};

const getGranularityForRange = (rangeDays) => {
	if (rangeDays <= 90) {
		return "day";
	}

	if (rangeDays <= 730) {
		return "week";
	}

	return "month";
};

const getBucketStart = (date, granularity) => {
	if (granularity === "month") {
		return getStartOfMonth(date);
	}

	if (granularity === "week") {
		return getStartOfWeek(date);
	}

	return getStartOfDay(date);
};

const getBucketKey = (date, granularity) => {
	const bucketStart = getBucketStart(date, granularity);
	return bucketStart.toISOString();
};

const getBucketPresentation = (bucketStart, granularity, language, t) => {
	if (granularity === "month") {
		return {
			tooltipLabel: formatMonth(bucketStart, language),
			tooltipKey: "collectionValue.tooltipMonth",
		};
	}

	if (granularity === "week") {
		return {
			tooltipLabel: t("collectionValue.weekOf", {
				date: formatDate(bucketStart, language),
			}),
			tooltipKey: "collectionValue.tooltipWeek",
		};
	}

	return {
		tooltipLabel: formatDate(bucketStart, language),
		tooltipKey: "collectionValue.tooltipDate",
	};
};

// Group raw snapshots into a cleaner analytics series by taking the final state
// in each day/week/month bucket based on total history range.
const buildCollectionValueSeries = (snapshots, language, t) => {
	const sortedSnapshots = [...(Array.isArray(snapshots) ? snapshots : [])]
		.map((snapshot) => {
			const parsedDate = parseSnapshotDate(snapshot);
			return parsedDate ? { ...snapshot, parsedDate } : null;
		})
		.filter(Boolean)
		.sort((left, right) => left.parsedDate - right.parsedDate);

	if (sortedSnapshots.length === 0) {
		return {
			granularity: "day",
			points: [],
			latestRawSnapshot: null,
		};
	}

	const granularity = getGranularityForRange(getDateRangeDays(sortedSnapshots));
	const groupedSnapshots = new Map();

	sortedSnapshots.forEach((snapshot) => {
		groupedSnapshots.set(getBucketKey(snapshot.parsedDate, granularity), snapshot);
	});

	const points = Array.from(groupedSnapshots.values()).map((snapshot) => {
		const bucketStart = getBucketStart(snapshot.parsedDate, granularity);
		const presentation = getBucketPresentation(bucketStart, granularity, language, t);
		return {
			id: snapshot.id ?? `${granularity}-${bucketStart.toISOString()}`,
			bucketKey: getBucketKey(snapshot.parsedDate, granularity),
			bucketStart,
			createdAt: snapshot.created_at,
			totalValue: Number(snapshot.total_value || 0),
			kitsCount: Number(snapshot.kits_count || 0),
			tooltipLabel: presentation.tooltipLabel,
			tooltipKey: presentation.tooltipKey,
			rawSnapshot: snapshot,
		};
	});

	return {
		granularity,
		points,
		latestRawSnapshot: sortedSnapshots[sortedSnapshots.length - 1],
	};
};

const getMinimumDomainStart = (latestBucketStart, granularity) => {
	if (granularity === "month") {
		return addMonths(latestBucketStart, -(MIN_VISIBLE_MONTH_WINDOW_MONTHS - 1));
	}

	if (granularity === "week") {
		return addWeeks(latestBucketStart, -(MIN_VISIBLE_WEEK_WINDOW_WEEKS - 1));
	}

	return addDays(latestBucketStart, -(MIN_VISIBLE_DAY_WINDOW_DAYS - 1));
};

const getTimeDomain = (seriesPoints, granularity) => {
	const firstBucketStart = seriesPoints[0]?.bucketStart;
	const lastBucketStart = seriesPoints[seriesPoints.length - 1]?.bucketStart;

	if (!firstBucketStart || !lastBucketStart) {
		return {
			domainStart: null,
			domainEnd: null,
			domainRange: 1,
		};
	}

	if (seriesPoints.length === 1) {
		if (granularity === "month") {
			const domainStart = addMonths(firstBucketStart, -2);
			const domainEnd = addMonths(firstBucketStart, 2);
			return {
				domainStart,
				domainEnd,
				domainRange: Math.max(1, domainEnd.getTime() - domainStart.getTime()),
			};
		}

		if (granularity === "week") {
			const domainStart = addWeeks(firstBucketStart, -2);
			const domainEnd = addWeeks(firstBucketStart, 2);
			return {
				domainStart,
				domainEnd,
				domainRange: Math.max(1, domainEnd.getTime() - domainStart.getTime()),
			};
		}

		const domainStart = addDays(firstBucketStart, -3);
		const domainEnd = addDays(firstBucketStart, 3);
		return {
			domainStart,
			domainEnd,
			domainRange: Math.max(1, domainEnd.getTime() - domainStart.getTime()),
		};
	}

	const minimumDomainStart = getMinimumDomainStart(lastBucketStart, granularity);
	const domainStart =
		firstBucketStart < minimumDomainStart ? firstBucketStart : minimumDomainStart;
	const domainEnd = lastBucketStart;
	const domainRange = Math.max(1, domainEnd.getTime() - domainStart.getTime());

	return {
		domainStart,
		domainEnd,
		domainRange,
	};
};

const getYDomain = (values) => {
	const maxValue = Math.max(...values);
	const paddedMaxValue = Math.ceil(Math.max(maxValue * 1.1, maxValue + 40, 100));

	return {
		maxValue,
		paddedMinValue: 0,
		paddedMaxValue,
		valueRange: Math.max(1, paddedMaxValue),
	};
};

const getXAxisTicks = (domainStart, domainRange, granularity, language) =>
	Array.from({ length: X_AXIS_TICK_COUNT }, (_, index) => {
		const ratio = index / (X_AXIS_TICK_COUNT - 1);
		const date = new Date(domainStart.getTime() + domainRange * ratio);
		return {
			date,
			label:
				granularity === "month"
					? formatShortMonth(date, language)
					: formatShortDate(date, language),
		};
	});

const getYAxisTicks = (topValue) => [
	{ value: topValue, position: 0 },
	{ value: topValue / 2, position: 0.5 },
	{ value: 0, position: 1 },
];

const CollectionValueLineChart = ({ points: rawPoints = [] }) => {
	const { t, i18n } = useTranslation();
	const [activePoint, setActivePoint] = useState(null);

	const { granularity, points, latestRawSnapshot } = useMemo(
		() => buildCollectionValueSeries(rawPoints, i18n.language, t),
		[rawPoints, i18n.language, t],
	);

	const hasPoints = points.length > 0;
	const summarySnapshot = latestRawSnapshot || null;
	const summaryValue = hasPoints
		? formatCurrency(summarySnapshot?.total_value)
		: formatCurrency(0);
	const summaryCount = Number(summarySnapshot?.kits_count || 0);

	if (!hasPoints) {
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

	const values = points.map((point) => point.totalValue);
	const { paddedMinValue, paddedMaxValue, valueRange } = getYDomain(values);
	const { domainStart, domainRange } = getTimeDomain(points, granularity);
	const plotWidth = CHART_WIDTH - PLOT_LEFT - PLOT_RIGHT;
	const plotHeight = CHART_HEIGHT - PLOT_TOP - PLOT_BOTTOM;
	const getXForDate = (date) => {
		const elapsedTime = Math.max(0, date.getTime() - domainStart.getTime());
		const normalizedX = elapsedTime / domainRange;
		return PLOT_LEFT + normalizedX * plotWidth;
	};

	const chartPoints = points.map((point) => {
		const x = getXForDate(point.bucketStart);
		const normalized = (point.totalValue - paddedMinValue) / valueRange;
		const y = CHART_HEIGHT - PLOT_BOTTOM - normalized * plotHeight;
		return {
			...point,
			x,
			y,
			labelValue: formatCurrency(point.totalValue),
		};
	});

	const path =
		chartPoints.length > 1
			? chartPoints
					.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
					.join(" ")
			: "";

	const xAxisTicks = getXAxisTicks(domainStart, domainRange, granularity, i18n.language);
	const yAxisTicks = getYAxisTicks(paddedMaxValue);
	const tooltipDateLabelKey = activePoint?.tooltipKey || "collectionValue.tooltipDate";

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
						{summaryValue}
					</div>
				</div>
				<div className="collection-value-summary-count">
					{t("collectionValue.kitsCount", { count: summaryCount })}
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
								{t(tooltipDateLabelKey)}
							</span>
							<span className="collection-value-chart-tooltip-value">
								{activePoint.tooltipLabel}
							</span>
						</div>
						<div className="collection-value-chart-tooltip-row">
							<span className="collection-value-chart-tooltip-label">
								{t("collectionValue.tooltipKits")}
							</span>
							<span className="collection-value-chart-tooltip-value">
								{t("collectionValue.kitsCount", {
									count: activePoint.kitsCount,
								})}
							</span>
						</div>
					</div>
				) : null}
				<svg
					viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
					className="collection-value-chart"
					role="img"
					aria-label={t("collectionValue.title")}
				>
					<line
						x1={PLOT_LEFT}
						y1={CHART_HEIGHT - PLOT_BOTTOM}
						x2={CHART_WIDTH - PLOT_RIGHT}
						y2={CHART_HEIGHT - PLOT_BOTTOM}
						className="collection-value-axis"
					/>
					<line
						x1={PLOT_LEFT}
						y1={PLOT_TOP}
						x2={PLOT_LEFT}
						y2={CHART_HEIGHT - PLOT_BOTTOM}
						className="collection-value-axis"
					/>
					{yAxisTicks.map((tick) => {
						const y = PLOT_TOP + tick.position * plotHeight;
						return (
							<React.Fragment key={tick.position}>
								{tick.position !== 1 ? (
									<line
										x1={PLOT_LEFT}
										y1={y}
										x2={CHART_WIDTH - PLOT_RIGHT}
										y2={y}
										className="collection-value-grid-line"
									/>
								) : null}
								<text
									x={PLOT_LEFT - 10}
									y={y + 4}
									className="collection-value-axis-label collection-value-axis-label-y"
									textAnchor="end"
								>
									{formatCurrency(tick.value)}
								</text>
							</React.Fragment>
						);
					})}
					{path ? <path d={path} className="collection-value-line" /> : null}
					{chartPoints.map((point) => (
						<React.Fragment key={point.id}>
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
							/>
						</React.Fragment>
					))}
					{xAxisTicks.map((tick, index) => (
						<React.Fragment key={`${tick.date.toISOString()}-${index}`}>
							<line
								x1={PLOT_LEFT + (index / (X_AXIS_TICK_COUNT - 1)) * plotWidth}
								y1={CHART_HEIGHT - PLOT_BOTTOM}
								x2={PLOT_LEFT + (index / (X_AXIS_TICK_COUNT - 1)) * plotWidth}
								y2={CHART_HEIGHT - PLOT_BOTTOM + 5}
								className="collection-value-axis-tick"
							/>
							<text
								x={PLOT_LEFT + (index / (X_AXIS_TICK_COUNT - 1)) * plotWidth}
								y={CHART_HEIGHT - 10}
								className="collection-value-axis-label collection-value-axis-label-x"
								textAnchor={index === 0 ? "start" : index === X_AXIS_TICK_COUNT - 1 ? "end" : "middle"}
							>
								{tick.label}
							</text>
						</React.Fragment>
					))}
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
								{t(activePoint.tooltipKey)}
							</span>
							<span className="collection-value-chart-point-detail-value">
								{activePoint.tooltipLabel}
							</span>
						</div>
						<div className="collection-value-chart-point-detail">
							<span className="collection-value-chart-point-detail-label">
								{t("collectionValue.tooltipKits")}
							</span>
							<span className="collection-value-chart-point-detail-value">
								{t("collectionValue.kitsCount", {
									count: activePoint.kitsCount,
								})}
							</span>
						</div>
					</div>
				</div>
			) : null}
		</div>
	);
};

export default CollectionValueLineChart;
