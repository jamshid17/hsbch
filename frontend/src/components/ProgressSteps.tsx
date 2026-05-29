import { useLocation } from "react-router-dom";
import clsx from "clsx";

const STEPS = [
  { label: "Scan", pattern: /^\/$/ },
  { label: "Items", pattern: /^\/edit\// },
  { label: "People", pattern: /^\/people\// },
  { label: "Assign", pattern: /^\/assign\// },
  { label: "Summary", pattern: /^\/summary\// },
];

export default function ProgressSteps() {
  const { pathname } = useLocation();
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
