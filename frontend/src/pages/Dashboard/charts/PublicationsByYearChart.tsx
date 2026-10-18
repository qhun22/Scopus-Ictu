import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  type ChartOptions,
} from "chart.js";
import type { PublicationsByYearItem } from "../../../types/dashboard";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip);

interface Props {
  data: PublicationsByYearItem[];
  locale: "vi" | "en";
}

// The only specified year rule is the database constraint ck_publications_year_range (1000–9999).
// Every year inside it is plotted; values outside it can only come from a malformed response and are listed in a note.
const MIN_VALID_YEAR = 1000;
const MAX_VALID_YEAR = 9999;

export function buildYearSeries(data: PublicationsByYearItem[]) {
  const isValid = (y: number) => Number.isInteger(y) && y >= MIN_VALID_YEAR && y <= MAX_VALID_YEAR;
  const inRange = data.filter((d) => isValid(d.year));
  const outliers = data.filter((d) => !isValid(d.year));
  if (inRange.length === 0) return { points: [] as PublicationsByYearItem[], outliers };
  const counts = new Map(inRange.map((d) => [d.year, d.count]));
  const first = Math.min(...counts.keys());
  const last = Math.max(...counts.keys());
  const points: PublicationsByYearItem[] = [];
  for (let year = first; year <= last; year += 1) points.push({ year, count: counts.get(year) ?? 0 });
  return { points, outliers };
}

export default function PublicationsByYearChart({ data, locale }: Props) {
  const { points, outliers } = buildYearSeries(data);
  const labels = points.map((d) => String(d.year));
  const values = points.map((d) => d.count);
  const outlierCount = outliers.reduce((sum, d) => sum + d.count, 0);

  const chartData = {
    labels,
    datasets: [
      {
        label: locale === "vi" ? "Số công bố" : "Publications",
        data: values,
        backgroundColor: "#3A5FC3",
        borderRadius: 4,
        maxBarThickness: 36,
      },
    ],
  };

  const options: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) =>
            `${locale === "vi" ? "Số công bố" : "Publications"}: ${(ctx.parsed.y ?? 0).toLocaleString(
              locale === "vi" ? "vi-VN" : "en-US",
            )}`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: "#64748b", font: { size: 11 }, autoSkip: true, maxRotation: 45 },
      },
      y: {
        beginAtZero: true,
        ticks: {
          color: "#94a3b8",
          font: { size: 11 },
          precision: 0,
        },
        grid: { color: "#e2e8f0" },
      },
    },
  };

  const ariaLabel =
    locale === "vi"
      ? `Biểu đồ cột số công bố theo năm: ${points.map((d) => `${d.year} có ${d.count} công bố`).join(", ")}`
      : `Bar chart of publications by year: ${points.map((d) => `${d.year}: ${d.count}`).join(", ")}`;

  return (
    <div>
      <div style={{ position: "relative", height: 260 }}>
        <Bar
          data={chartData}
          options={options}
          aria-label={ariaLabel}
          role="img"
        />
      </div>
      {outlierCount > 0 && (
        <p className="mt-2 text-xs text-amber-700" data-testid="year-outliers-note">
          {locale === "vi"
            ? `${outlierCount.toLocaleString("vi-VN")} công bố có năm không hợp lệ (${outliers.map((d) => d.year).join(", ")}; hợp lệ: ${MIN_VALID_YEAR}–${MAX_VALID_YEAR}) nên không được vẽ trên trục năm.`
            : `${outlierCount.toLocaleString("en-US")} publications have an invalid year (${outliers.map((d) => d.year).join(", ")}; valid: ${MIN_VALID_YEAR}–${MAX_VALID_YEAR}) and are not plotted on the year axis.`}
        </p>
      )}
    </div>
  );
}
