import { useState } from "react";

interface Props {
  data: { date: string; scans: number }[];
}

/** 14-day scan volume. One series, so no legend: the title names it, and the
 * selected bar labels itself on tap (mobile has no hover). */
export default function DailyScansChart({ data }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.scans), 1);
  const dayMonth = (iso: string) => iso.slice(8, 10) + "." + iso.slice(5, 7);
  const active = selected !== null ? data[selected] : data[data.length - 1];

  return (
    <div className="card chart-card">
      <div className="chart-head">
        <div className="label">Kunlik skanlar · 14 kun</div>
        <div className="chart-readout">
          <span className="chart-readout-value">{active.scans}</span>
          <span className="chart-readout-date">{dayMonth(active.date)}</span>
        </div>
      </div>

      <div className="chart-bars" role="img" aria-label="Kunlik skanlar, 14 kun">
        {data.map((d, i) => {
          const isActive = (selected === null ? data.length - 1 : selected) === i;
          return (
            <button
              key={d.date}
              className={`chart-bar-hit ${isActive ? "is-active" : ""}`}
              onClick={() => setSelected(i)}
              aria-label={`${d.date}: ${d.scans} skan`}
            >
              <span
                className="chart-bar"
                style={{ height: `${Math.max((d.scans / max) * 100, 2)}%` }}
              />
            </button>
          );
        })}
      </div>

      <div className="chart-axis">
        <span>{dayMonth(data[0].date)}</span>
        <span>bugun</span>
      </div>
    </div>
  );
}
