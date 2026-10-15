import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, type ChartOptions } from "chart.js";
import type { PublicationsByDocumentTypeItem } from "../../../types/dashboard";

ChartJS.register(ArcElement, Tooltip);

// Cove categorical palette, fixed order — never cycled/generated.
const PALETTE = ["#3A5FC3", "#D85A30", "#1D9E75", "#BA7517", "#D4537E", "#5F5E5A", "#888780"];

// Scopus "Document Type" values are not consistently cased in source CSVs
// (observed both "Conference paper" and "Conference Paper"), so lookup is
// case-insensitive to avoid silently falling back to the raw English string.
const DOC_TYPE_LABELS_VI: Record<string, string> = {
  article: "Bài báo tạp chí",
  "conference paper": "Bài báo hội nghị",
  review: "Bài tổng quan",
  "book chapter": "Chương sách",
  book: "Sách",
  note: "Ghi chú khoa học",
  letter: "Thư khoa học",
  erratum: "Đính chính",
  editorial: "Bài xã luận",
  "short survey": "Khảo sát ngắn",
  unspecified: "Chưa phân loại",
};

interface Props {
  data: PublicationsByDocumentTypeItem[];
  locale: "vi" | "en";
}

function displayLabel(docType: string, locale: "vi" | "en"): string {
  if (locale === "vi") {
    return DOC_TYPE_LABELS_VI[docType.toLowerCase()] ?? docType;
  }
  return docType === "UNSPECIFIED" ? "Unspecified" : docType;
}

export default function DocumentTypeDonutChart({ data, locale }: Props) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  const labels = data.map((d) => displayLabel(d.document_type, locale));
  const values = data.map((d) => d.count);
  const colors = data.map((_, i) => PALETTE[i % PALETTE.length]);

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
    cutout: "62%",
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const value = ctx.parsed as number;
            const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0";
            return ` ${ctx.label}: ${value.toLocaleString(locale === "vi" ? "vi-VN" : "en-US")} (${pct}%)`;
          },
        },
      },
    },
  };

  const ariaLabel =
    locale === "vi"
      ? `Biểu đồ tròn cơ cấu loại công bố: ${data.map((d) => `${displayLabel(d.document_type, locale)} ${d.count}`).join(", ")}`
      : `Donut chart of document type breakdown: ${data.map((d) => `${displayLabel(d.document_type, locale)}: ${d.count}`).join(", ")}`;

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <div style={{ position: "relative", height: 220, width: 220 }} className="shrink-0 mx-auto sm:mx-0">
        <Doughnut data={chartData} options={options} aria-label={ariaLabel} role="img" />
      </div>
      <div className="flex flex-col gap-1.5 text-xs">
        {data.map((item, i) => {
          const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : "0";
          return (
            <div key={item.document_type} className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
                style={{ backgroundColor: colors[i] }}
                aria-hidden="true"
              />
              <span className="text-slate-600">{displayLabel(item.document_type, locale)}</span>
              <span className="ml-auto font-semibold text-slate-800">
                {item.count.toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}
              </span>
              <span className="text-slate-400 w-12 text-right">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
