import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import "../styles/get-pro.css";

const GetProPage = () => {
	const { t } = useTranslation();
	const [notice, setNotice] = useState("");

	useEffect(() => {
		const root = document.documentElement;
		root.classList.add("get-pro-no-scroll");
		document.body.classList.add("get-pro-no-scroll");

		return () => {
			root.classList.remove("get-pro-no-scroll");
			document.body.classList.remove("get-pro-no-scroll");
		};
	}, []);

	useEffect(() => {
		if (!notice) return undefined;

		const timeoutId = window.setTimeout(() => {
			setNotice("");
		}, 3200);

		return () => window.clearTimeout(timeoutId);
	}, [notice]);

	const showComingSoon = () => {
		setNotice(t("getPro.paymentsComingSoon"));
	};

	const proFeatures = [
		t("getPro.features.valueHistory"),
		t("getPro.features.analytics"),
		t("getPro.features.purchaseTracking"),
		t("getPro.features.roi"),
		t("getPro.features.topShirts"),
		t("getPro.features.breakdowns"),
		t("getPro.features.unlimitedWishlist"),
		t("getPro.features.privateNotes"),
		t("getPro.features.csvExport"),
		t("getPro.features.featuredShirts"),
		t("getPro.features.proBadge"),
		t("getPro.features.spotlightPoints"),
	];

	const faqs = [
		{
			question: t("getPro.faqPaymentsQuestion"),
			answer: t("getPro.faqPaymentsAnswer"),
		},
		{
			question: t("getPro.faqPrivacyQuestion"),
			answer: t("getPro.faqPrivacyAnswer"),
		},
		{
			question: t("getPro.faqFounderQuestion"),
			answer: t("getPro.faqFounderAnswer"),
		},
	];

	return (
		<div className="get-pro-page">
			<div className="container">
				<div className="get-pro-shell">
					<div className="get-pro-main">
						<section className="get-pro-header">
							<h1>{t("getPro.title")}</h1>
							<p className="get-pro-subtitle">
								{t("getPro.subtitle")}
							</p>
							<p className="get-pro-founder-line">
								<span className="get-pro-founder-line-label">
									{t("getPro.founderLabel")}
								</span>
								<span className="get-pro-founder-line-separator">·</span>
								<span className="get-pro-founder-line-text">
									{t("getPro.founderLine")}
								</span>
							</p>
						</section>

						<section className="get-pro-pricing-section">
							<div className="get-pro-pricing-grid">
								<article className="get-pro-pricing-card">
									<div className="get-pro-pricing-card-head">
										<h2>{t("getPro.monthlyTitle")}</h2>
										<p>{t("getPro.monthlyDescription")}</p>
									</div>
									<div className="get-pro-price-row">
										<span className="get-pro-price">
											{t("getPro.monthlyPrice")}
										</span>
										<span className="get-pro-period">
											{t("getPro.perMonth")}
										</span>
									</div>
									<button
										type="button"
										className="btn get-pro-outline-button"
										onClick={showComingSoon}
									>
										{t("getPro.chooseMonthly")}
									</button>
								</article>

								<article className="get-pro-pricing-card get-pro-pricing-card-featured">
									<div className="get-pro-best-value-pill">
										{t("getPro.bestValue")}
									</div>
									<div className="get-pro-pricing-card-head">
										<h2>{t("getPro.yearlyTitle")}</h2>
										<p>{t("getPro.yearlyDescription")}</p>
									</div>
									<div className="get-pro-price-row">
										<span className="get-pro-price">
											{t("getPro.yearlyPrice")}
										</span>
										<span className="get-pro-period">
											{t("getPro.perYear")}
										</span>
									</div>
									<button
										type="button"
										className="btn get-pro-primary-button"
										onClick={showComingSoon}
									>
										{t("getPro.chooseYearly")}
									</button>
								</article>
							</div>

							{notice ? (
								<div className="get-pro-inline-notice" role="status">
									{notice}
								</div>
							) : null}
						</section>
					</div>

					<section className="get-pro-features-section">
						<div className="get-pro-section-card">
							<div className="get-pro-section-heading">
								<h2>{t("getPro.featuresTitle")}</h2>
							</div>
							<ul className="get-pro-feature-list">
								{proFeatures.map((feature) => (
									<li key={feature}>{feature}</li>
								))}
							</ul>
						</div>
					</section>
				</div>

				{/* <section className="get-pro-faq-section">
					<div className="get-pro-section-card">
						<div className="get-pro-section-heading">
							<h2>{t("getPro.faqTitle")}</h2>
						</div>
						<div className="get-pro-faq-list">
							{faqs.map((item) => (
								<article
									key={item.question}
									className="get-pro-faq-item"
								>
									<h3>{item.question}</h3>
									<p>{item.answer}</p>
								</article>
							))}
						</div>
					</div>
				</section> */}
			</div>
		</div>
	);
};

export default GetProPage;
