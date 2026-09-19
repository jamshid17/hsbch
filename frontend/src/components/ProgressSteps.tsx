import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import clsx from "clsx";

/**
 * Where the host is in building the bill.
 *
 * Only the host's own three screens are counted. The bar used to list steps
 * the flow never visits — it vanished on the people/assign/pick screens and
 * then reappeared on the summary for guests who had scanned nothing — so a
 * route that isn't one of these renders no bar at all rather than a wrong one.
 */
const STEPS = [
  { key: "scan", patterns: [/^\/scan/] },
  { key: "items", patterns: [/^\/edit\//] },
  // Both ways of splitting land here: the code screen, or the host's own
  // people + assign screens.
  { key: "split", patterns: [/^\/host\//, /^\/people\//, /^\/assign\//] },
] as const;

export default function ProgressSteps() {
  const { pathname } = useLocation();
  const { t } = useTranslation();

  const currentIndex = STEPS.findIndex((s) =>
    s.patterns.some((p) => p.test(pathname))
  );
  if (currentIndex === -1) return null;

  return (
    <div className="top-bar">
      <div className="progress-steps">
        {STEPS.map((step, idx) => {
          const done = idx < currentIndex;
          const active = idx === currentIndex;
          return (
            <div key={step.key} className="progress-step">
              <div className={clsx("step-dot", { done, active })}>
                {done ? "✓" : idx + 1}
              </div>
              <span className={clsx("step-label", { active })}>
                {t(`steps.${step.key}`)}
              </span>
              {idx < STEPS.length - 1 && (
                <div className={clsx("step-line", { done })} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
