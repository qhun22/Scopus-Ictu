import { useId } from "react";
import type { ScopusImportItem } from "../../api/lecturerImport";
import { useI18n } from "../../i18n";

export default function ScopusImportReview({ items, checked, reason, disabled, onChecked, onReason }: {
  items: ScopusImportItem[];
  checked: boolean;
  reason: string;
  disabled: boolean;
  onChecked: (value: boolean) => void;
  onReason: (value: string) => void;
}) {
  const { t } = useI18n();
  const s = t.lecturerImport;
  const reasonId = useId();
  if (!items.length) return null;
  const count = items.reduce((total, item) => total + item.scopus_ids.length, 0);
  return (
    <section className="space-y-3 rounded-[5px] border border-slate-200 bg-white p-4 text-sm">
      <h3 className="font-bold text-slate-800">{s.scopusReviewTitle}</h3>
      <p>{s.scopusReviewCount.replace("{count}", String(count)).replace("{lecturers}", String(items.length))}</p>
      <details>
        <summary className="cursor-pointer font-semibold">{t.common.viewDetails}</summary>
        <ul className="mt-2 max-h-64 space-y-2 overflow-y-auto">
          {items.map((item, index) => (
            <li key={index} className="rounded-[5px] border border-slate-200 px-3 py-2">
              <p className="font-semibold">{item.full_name} · {item.institutional_email}</p>
              <p className="break-words">{item.scopus_ids.join(", ")}</p>
              {item.primary_scopus_id && <p>{s.scopusReviewPrimary}: {item.primary_scopus_id}</p>}
            </li>
          ))}
        </ul>
      </details>
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChecked(e.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-slate-600" />
        <span>{s.scopusReviewConfirm}</span>
      </label>
      {checked && (
        <div className="space-y-1">
          <label htmlFor={reasonId} className="block font-semibold">{s.scopusReviewReason}</label>
          <input id={reasonId} value={reason} maxLength={4000} disabled={disabled} onChange={(e) => onReason(e.target.value)} className="h-9 w-full rounded-[5px] border border-slate-200 px-3" />
        </div>
      )}
    </section>
  );
}
