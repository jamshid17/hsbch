import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

export default function ProgressSteps() {
  const { pathname } = useLocation();
  const { t } = useTranslation();

  const STEPS = [
    { label: t("steps.scan"),    pattern: /^\/$/ },
    { label: t("steps.items"),   pattern: /^\/edit\// },
    { label: t("steps.people"),  pattern: /^\/people\// },
    { label: t("steps.assign"),  pattern: /^\/assign\// },
    { label: t("steps.summary"), pattern: /^\/summary\// },
  ];

  const currentIndex = STEPS.findIndex((s) => s.pattern.test(pathname));
  if (currentIndex === -1) return null;

  return (
    <div className="progress-steps">
      {STEPS.map((step, idx) => {
        const done = idx < currentIndex;
        const active = idx === currentIndex;
        return (
          <div key={step.label} className="progress-step">
            <div className={clsx("step-dot", { done, active })}>
              {done ? "✓" : idx + 1}
            </div>
            <span className={clsx("step-label", { active })}>{step.label}</span>
            {idx < STEPS.length - 1 && (
              <div className={clsx("step-line", { done })} />
            )}
          </div>
        );
      })}
    </div>
  );
}
