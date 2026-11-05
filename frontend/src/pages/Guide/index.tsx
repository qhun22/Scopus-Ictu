import { useMemo } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useI18n } from "../../i18n";
import { PageHeader } from "../../components/ui/PageHeader";
import { GUIDE_CONTENT, GuideBlock, GuideRole } from "./guideContent";

const copy = {
  vi: {
    title: "Hướng dẫn sử dụng",
    subtitle: "Cách dùng hệ thống theo vai trò của bạn.",
    toc: "Mục lục",
    viewing: "Đang xem theo vai trò",
    roles: { GUEST: "Khách", LECTURER: "Giảng viên", REVIEWER: "Người duyệt", ADMIN: "Quản trị" } as Record<GuideRole, string>,
  },
  en: {
    title: "User guide",
    subtitle: "How to use the system for your role.",
    toc: "Contents",
    viewing: "Showing the guide for",
    roles: { GUEST: "Guest", LECTURER: "Lecturer", REVIEWER: "Reviewer", ADMIN: "Administrator" } as Record<GuideRole, string>,
  },
};

function toGuideRole(role: string | undefined): GuideRole {
  const upper = role?.toUpperCase();
  return upper === "ADMIN" || upper === "REVIEWER" || upper === "LECTURER" ? upper : "GUEST";
}

function Block({ block }: { block: GuideBlock }) {
  switch (block.kind) {
    case "p":
      return <p className="text-sm leading-relaxed text-slate-700">{block.text}</p>;
    case "list":
      return (
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700">
          {block.items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      );
    case "steps":
      return (
        <ol className="space-y-2.5">
          {block.items.map((item, index) => (
            <li key={item} className="flex gap-3 text-sm leading-relaxed text-slate-700">
              <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#3A5FC3]/10 text-xs font-bold text-[#3A5FC3]">
                {index + 1}
              </span>
              <span className="min-w-0">{item}</span>
            </li>
          ))}
        </ol>
      );
    case "table":
      return (
        <div className="overflow-x-auto rounded-[5px] border border-slate-200">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
              <tr>{block.head.map((cell) => <th key={cell} className="px-3 py-2">{cell}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {block.rows.map((row) => (
                <tr key={row[0]} className="align-top">
                  {row.map((cell, index) => (
                    <td key={index} className={`px-3 py-2 leading-relaxed ${index === 0 ? "font-semibold text-slate-800" : ""}`}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "code":
      return (
        <pre className="overflow-x-auto rounded-[5px] bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
          <code>{block.text}</code>
        </pre>
      );
    case "note":
      return (
        <div
          className={`rounded-[5px] border px-3.5 py-2.5 text-sm leading-relaxed ${
            block.tone === "warn"
              ? "border-amber-300 bg-amber-50 text-amber-900"
              : "border-sky-200 bg-sky-50 text-sky-900"
          }`}
        >
          {block.text}
        </div>
      );
  }
}

export default function GuidePage() {
  const { locale } = useI18n();
  const { user } = useAuth();
  const text = locale === "vi" ? copy.vi : copy.en;
  const role = toGuideRole(user?.role);
  const sections = useMemo(
    () => GUIDE_CONTENT[locale === "vi" ? "vi" : "en"].filter((section) => section.roles.includes(role)),
    [locale, role],
  );

  const goTo = (id: string) => {
    document.getElementById(`guide-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader title={text.title} subtitle={`${text.subtitle} ${text.viewing}: ${text.roles[role]}.`} />

      <nav aria-label={text.toc} className="rounded-[5px] border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-widest text-slate-400">{text.toc}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => goTo(section.id)}
              className="rounded-[5px] border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:border-[#3A5FC3]/40 hover:bg-[#3A5FC3]/10 hover:text-[#3A5FC3]"
            >
              {section.title}
            </button>
          ))}
        </div>
      </nav>

      {sections.map((section) => (
        <section
          key={section.id}
          id={`guide-${section.id}`}
          className="scroll-mt-20 space-y-3 rounded-[5px] border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
        >
          <h2 className="text-base font-bold text-slate-900 sm:text-lg">{section.title}</h2>
          {section.blocks.map((block, index) => <Block key={index} block={block} />)}
        </section>
      ))}
    </main>
  );
}
