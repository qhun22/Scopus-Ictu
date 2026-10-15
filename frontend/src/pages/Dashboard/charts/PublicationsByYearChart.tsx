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

export default function PublicationsByYearChart({ data, locale }: Props) {
  const labels = data.map((d) => String(d.year));
  const values = data.map((d) => d.count);

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
        ticks: { color: "#64748b", font: { size: 11 }, autoSkip: false, maxRotation: 45 },
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
      ? `Biểu đồ cột số công bố theo năm: ${data.map((d) => `${d.year} có ${d.count} công bố`).join(", ")}`
      : `Bar chart of publications by year: ${data.map((d) => `${d.year}: ${d.count}`).join(", ")}`;

  return (
    <div style={{ position: "relative", height: 260 }}>
      <Bar
        data={chartData}
        options={options}
        aria-label={ariaLabel}
        role="img"
      />
    </div>
  );
}
