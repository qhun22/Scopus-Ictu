import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, type ChartOptions } from "chart.js";
import type { AffiliationCoverage } from "../../../types/dashboard";

ChartJS.register(ArcElement, Tooltip);

interface Props {
  data: AffiliationCoverage;
  locale: "vi" | "en";
}

export default function AffiliationCoverageChart({ data, locale }: Props) {
  const { total_author_positions, positions_with_affiliation, positions_without_affiliation } = data;

  const labels =
    locale === "vi"
      ? ["Có đơn vị công tác", "Chưa có đơn vị công tác"]
      : ["Has affiliation", "Missing affiliation"];
  const values = [positions_with_affiliation, positions_without_affiliation];
  const colors = ["#1D9E75", "#E2E8F0"];

  const chartData = {
    labels,
    datasets: [
      {
        data: values,
        backgroundColor: colors,
        borderColor: "#fff",
        borderWidth: 2,
      },
    ],
  };

  const options: ChartOptions<"doughnut"> = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "68%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const value = ctx.parsed as number;
            const pct =
              total_author_positions > 0 ? ((value / total_author_positions) * 100).toFixed(1) : "0";
            return ` ${ctx.label}: ${value.toLocaleString(locale === "vi" ? "vi-VN" : "en-US")} (${pct}%)`;
          },
        },
      },
    },
  };

  const pctWith =
    total_author_positions > 0
      ? Math.round((positions_with_affiliation / total_author_positions) * 100)
      : 0;

  const ariaLabel =
    locale === "vi"
      ? `Biểu đồ tròn mức độ đầy đủ đơn vị tác giả: ${positions_with_affiliation} trên ${total_author_positions} vị trí tác giả có đơn vị công tác, chiếm ${pctWith}%`
      : `Donut chart of affiliation coverage: ${positions_with_affiliation} of ${total_author_positions} author positions have an affiliation, ${pctWith}%`;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div
        style={{ position: "relative", height: 180, width: 180 }}
        className="shrink-0 mx-auto sm:mx-0"
      >
        <Doughnut data={chartData} options={options} aria-label={ariaLabel} role="img" />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-black text-slate-800">{pctWith}%</span>
          <span className="text-[10px] text-slate-400">{locale === "vi" ? "có đơn vị" : "covered"}</span>
        </div>
      </div>
      <div className="flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: colors[0] }} aria-hidden="true" />
          <span className="text-slate-600">{labels[0]}</span>
          <span className="ml-auto font-semibold text-slate-800">
            {positions_with_affiliation.toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: colors[1] }} aria-hidden="true" />
          <span className="text-slate-600">{labels[1]}</span>
          <span className="ml-auto font-semibold text-slate-800">
            {positions_without_affiliation.toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}
          </span>
        </div>
        <p className="mt-1 max-w-[220px] text-[11px] leading-relaxed text-slate-400">
          {locale === "vi"
            ? `${positions_with_affiliation.toLocaleString("vi-VN")}/${total_author_positions.toLocaleString("vi-VN")} vị trí tác giả có ít nhất một đơn vị công tác được ghi nhận. Mẫu số là số vị trí tác giả trên các công bố, không phải số tác giả Scopus duy nhất.`
            : `${positions_with_affiliation.toLocaleString("en-US")}/${total_author_positions.toLocaleString("en-US")} author positions have at least one recorded affiliation. The denominator is author positions across publications, not unique Scopus authors.`}
        </p>
      </div>
    </div>
  );
}
