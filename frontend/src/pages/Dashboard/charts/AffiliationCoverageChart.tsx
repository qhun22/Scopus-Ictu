import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, type ChartOptions } from "chart.js";
import type { AffiliationCoverage } from "../../../types/dashboard";
import { statusLabel } from "../../Publications/AuthorAffiliations";

ChartJS.register(ArcElement, Tooltip);

interface Props {
  data: AffiliationCoverage;
  locale: "vi" | "en";
}

export default function AffiliationCoverageChart({ data, locale }: Props) {
  const { total_author_positions, positions_with_affiliation, positions_without_affiliation, by_link_status } = data;
  const fmt = (v: number) => v.toLocaleString(locale === "vi" ? "vi-VN" : "en-US");
  const reconciled = by_link_status.VERIFIED + by_link_status.CORROBORATED + by_link_status.UNRESOLVED;
  const notReconciled = Math.max(0, total_author_positions - reconciled);

  const labels =
    locale === "vi"
      ? ["Có thông tin đơn vị", "Chưa có thông tin đơn vị"]
      : ["Has affiliation information", "No affiliation information"];
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
      ? `Biểu đồ tròn mức độ đầy đủ đơn vị tác giả: ${positions_with_affiliation} trên ${total_author_positions} vị trí tác giả có thông tin đơn vị, chiếm ${pctWith}%`
      : `Donut chart of affiliation coverage: ${positions_with_affiliation} of ${total_author_positions} author positions have affiliation information, ${pctWith}%`;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div
        style={{ position: "relative", height: 180, width: 180 }}
        className="shrink-0 mx-auto sm:mx-0"
      >
        <Doughnut data={chartData} options={options} aria-label={ariaLabel} role="img" />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-black text-slate-800">{pctWith}%</span>
          <span className="text-[10px] text-slate-400">{locale === "vi" ? "có thông tin" : "covered"}</span>
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
        <p className="mt-1 max-w-[260px] text-[11px] leading-relaxed text-slate-400">
          {locale === "vi"
            ? `${fmt(positions_with_affiliation)}/${fmt(total_author_positions)} vị trí tác giả có thông tin đơn vị ở mức Đã xác minh định danh hoặc Đã đối chiếu — chưa phải xác nhận đơn vị công tác. Mẫu số là số vị trí tác giả trên các công bố, không phải số tác giả Scopus duy nhất.`
            : `${fmt(positions_with_affiliation)}/${fmt(total_author_positions)} author positions have affiliation information at the Identity verified or Cross-checked level — not a confirmed employer. The denominator is author positions across publications, not unique Scopus authors.`}
        </p>
        <div className="mt-1 border-t border-line pt-2" data-testid="aff-link-status-breakdown">
          <p className="mb-1 text-[11px] font-semibold text-slate-500">
            {locale === "vi" ? "Mức đối chiếu theo vị trí tác giả" : "Reconciliation level per author position"}
          </p>
          {(["VERIFIED", "CORROBORATED", "UNRESOLVED"] as const).map((s) => (
            <div key={s} className="flex items-center gap-2 text-[11px]">
              <span className="text-slate-600">{statusLabel(s, locale)}</span>
              <span className="ml-auto font-semibold text-slate-800">{fmt(by_link_status[s])}</span>
            </div>
          ))}
          {notReconciled > 0 && (
            <div className="flex items-center gap-2 text-[11px]">
              <span className="text-slate-600">{statusLabel("NOT_RECONCILED", locale)}</span>
              <span className="ml-auto font-semibold text-slate-800">{fmt(notReconciled)}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
