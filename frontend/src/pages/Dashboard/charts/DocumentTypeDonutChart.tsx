import { Doughnut } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, type ChartOptions } from "chart.js";
import type { PublicationsByDocumentTypeItem } from "../../../types/dashboard";

ChartJS.register(ArcElement, Tooltip);

// Colour is bound to the document type (not to its rank in the data), so a type keeps its colour as counts change.
// The first seven keep the colours already shown on the Dashboard; the rest are distinct additions.
const TYPE_COLOR: Record<string, string> = {
  "conference paper": "#3A5FC3",
  article: "#D85A30",
  "book chapter": "#1D9E75",
  review: "#BA7517",
  erratum: "#D4537E",
  retracted: "#5F5E5A",
  note: "#888780",
  editorial: "#6D28D9",
  book: "#0E7490",
  letter: "#4338CA",
  "short survey": "#A16207",
  "conference review": "#0F766E",
  "data paper": "#9F1239",
  unspecified: "#CBD5E1",
};
const FALLBACK_COLORS = ["#334155", "#7C3AED", "#0369A1", "#B91C1C", "#15803D"];

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
  retracted: "Bài đã bị rút lại",
  "conference review": "Tổng quan hội nghị",
  "data paper": "Bài báo dữ liệu",
  editorial: "Bài xã luận",
  "short survey": "Khảo sát ngắn",
  unspecified: "Chưa phân loại",
};

const DOC_TYPE_LABELS_EN: Record<string, string> = {
  article: "Article",
  "conference paper": "Conference paper",
  review: "Review",
  "book chapter": "Book chapter",
  book: "Book",
  note: "Note",
  letter: "Letter",
  erratum: "Erratum",
  retracted: "Retracted",
  "conference review": "Conference review",
  "data paper": "Data paper",
  editorial: "Editorial",
  "short survey": "Short survey",
  unspecified: "Unspecified",
};

interface Props {
  data: PublicationsByDocumentTypeItem[];
  locale: "vi" | "en";
}

function displayLabel(docType: string, locale: "vi" | "en"): string {
  if (locale === "vi") {
    return DOC_TYPE_LABELS_VI[docType.toLowerCase()] ?? docType;
  }
  return DOC_TYPE_LABELS_EN[docType.toLowerCase()] ?? docType;
}

export default function DocumentTypeDonutChart({ data, locale }: Props) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  const labels = data.map((d) => displayLabel(d.document_type, locale));
  const values = data.map((d) => d.count);
  let unknownIndex = 0;
  const colors = data.map(
    (d) => TYPE_COLOR[d.document_type.toLowerCase()] ?? FALLBACK_COLORS[unknownIndex++ % FALLBACK_COLORS.length],
  );

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
