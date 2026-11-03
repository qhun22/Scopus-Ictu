import { useEffect, useState } from "react";
import { getNormalizationCompare, NormalizationCompare } from "../../api/publications";

type Locale = "vi" | "en";

const FIELD_LABEL: Record<string, Record<Locale, string>> = {
  eid: { vi: "EID", en: "EID" },
  doi: { vi: "DOI", en: "DOI" },
  title: { vi: "Tên công bố", en: "Title" },
  source_title: { vi: "Nguồn xuất bản", en: "Source title" },
  year: { vi: "Năm xuất bản", en: "Year" },
  document_type: { vi: "Loại tài liệu", en: "Document type" },
  cited_by_count: { vi: "Số trích dẫn", en: "Cited by" },
};

const STATUS: Record<string, { label: Record<Locale, string>; style: string }> = {
  SAME: { label: { vi: "Đã giữ nguyên", en: "Unchanged" }, style: "border-slate-300 text-slate-600" },
  CLEANED: { label: { vi: "Có dạng chuẩn", en: "Canonical form" }, style: "border-[#3A5FC3] text-[#3A5FC3]" },
  CHANGED: { label: { vi: "Đã thay đổi", en: "Changed" }, style: "border-amber-300 text-amber-700" },
  MISSING: { label: { vi: "Không có dữ liệu", en: "No data" }, style: "border-slate-300 text-slate-400" },
};

const Cell = ({ value }: { value: string | null }) =>
  value ? <span className="break-words text-slate-800">{value}</span> : <span className="text-slate-300">—</span>;

/**
 * Raw CSV value ↔ stored value ↔ canonical form, field by field. Read-only: the imported row is
 * immutable, so the original is always available for review.
 */
export default function NormalizationCompareCard({ eid, locale }: { eid: string; locale: Locale }) {
  const vi = locale === "vi";
  const [data, setData] = useState<NormalizationCompare | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(false);
    getNormalizationCompare(eid)
      .then((res) => !cancelled && setData(res))
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
  }, [eid]);

  if (error) return null;
  if (!data) return null;

  return (
    <section className="rounded-[5px] border border-slate-200/80 bg-white p-5 shadow-xs" data-testid="normalization-compare">
      <h2 className="mb-1 border-b border-slate-100 pb-3 text-base font-bold text-slate-800">
        {vi ? "So sánh trước / sau chuẩn hóa" : "Before / after normalisation"}
      </h2>
      <p className="mb-3 mt-2 text-sm text-slate-500">
        {vi
          ? "Giá trị gốc nằm nguyên trong dòng CSV đã nhập và không bao giờ bị sửa, nên luôn có thể xem lại. \"Dạng chuẩn\" là dạng hệ thống dùng để loại trùng và đối sánh."
          : "The original value stays untouched in the imported CSV row, so it can always be reviewed. The canonical form is what the system uses to de-duplicate and match."}
      </p>
      {data.sources.length > 0 && (
        <p className="mb-3 text-xs text-slate-500">
          {vi ? "Nguồn: " : "Source: "}
          {data.sources.map((s) => `${s.file_name} · ${vi ? "dòng" : "row"} ${s.row_number}`).join("; ")}
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-200 bg-slate-50/70 text-xs text-slate-600">
            <tr>
              <th className="px-3 py-2 font-semibold">{vi ? "Trường" : "Field"}</th>
              <th className="px-3 py-2 font-semibold">{vi ? "Giá trị gốc (CSV)" : "Raw (CSV)"}</th>
              <th className="px-3 py-2 font-semibold">{vi ? "Giá trị đang lưu" : "Stored"}</th>
              <th className="px-3 py-2 font-semibold">{vi ? "Dạng chuẩn" : "Canonical form"}</th>
              <th className="px-3 py-2 text-center font-semibold">{vi ? "Kết quả" : "Result"}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.fields.map((f) => {
              const status = STATUS[f.status] ?? STATUS.SAME;
              return (
                <tr key={f.field}>
                  <td className="px-3 py-2 text-xs font-semibold text-slate-700">{FIELD_LABEL[f.field]?.[locale] ?? f.field}</td>
                  <td className="px-3 py-2"><Cell value={f.raw} /></td>
                  <td className="px-3 py-2"><Cell value={f.stored} /></td>
                  <td className="px-3 py-2"><Cell value={f.canonical} /></td>
                  <td className="px-3 py-2 text-center">
                    <span
                      className={`inline-flex h-badge w-32 items-center justify-center whitespace-nowrap rounded-[5px] border bg-white px-2 text-xs font-bold leading-none ${status.style}`}
                    >
                      {status.label[locale]}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
