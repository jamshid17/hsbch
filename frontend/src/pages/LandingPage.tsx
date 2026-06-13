import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import LanguageSwitcher from "../components/LanguageSwitcher";

export default function LandingPage() {
  const { t } = useTranslation();

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => api.getConfig(),
    staleTime: Infinity,
  });

  const botUser = config?.bot_username ?? "hsbchbot";
  const tgLink = `https://t.me/${botUser}?startapp`;

  const features = [
    { icon: "📷", text: t("landing.feature1") },
    { icon: "🔗", text: t("landing.feature2") },
    { icon: "🧮", text: t("landing.feature3") },
  ];

  return (
    <div className="landing">
      <div className="landing-top">
        <LanguageSwitcher />
      </div>

      <div className="landing-hero">
        <div className="landing-logo">🧾</div>
        <h1 className="landing-title">{t("landing.title")}</h1>
        <p className="landing-tagline">{t("landing.tagline")}</p>
      </div>

      <div className="landing-features">
        {features.map((f, i) => (
          <div className="landing-feature" key={i}>
            <span className="landing-feature-icon">{f.icon}</span>
            <span>{f.text}</span>
          </div>
        ))}
      </div>

      <a
        className="landing-cta"
        href={tgLink}
        target="_blank"
        rel="noopener noreferrer"
      >
        <span style={{ fontSize: 18 }}>✈️</span> {t("landing.cta")}
      </a>

      <p className="landing-note">{t("landing.note")}</p>
    </div>
  );
}
