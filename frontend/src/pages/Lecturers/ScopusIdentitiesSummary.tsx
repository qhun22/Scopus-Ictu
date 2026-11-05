import { useEffect, useState } from "react";
import { getLecturerScopusIdentities } from "../../api/lecturerScopus";
import { ApiError } from "../../api/client";
import { ApprovedScopusIdentity } from "../../types/lecturerScopus";

type Locale = "vi" | "en";

/**
 * Read-only list of a lecturer's APPROVED Scopus IDs, for the admin-only lecturer
 * detail view. Setting the main ID among several is done in the review queue
 * (PrimaryIdPanel); this component only shows what already exists.
 */
export default function ScopusIdentitiesSummary({
  lecturerId,
  locale,
}: {
  lecturerId: string;
  locale: Locale;
}) {
  const vi = locale === "vi";
  const [identities, setIdentities] = useState<ApprovedScopusIdentity[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIdentities(null);
    setError(null);
    getLecturerScopusIdentities(lecturerId)
      .then((rows) => { if (!cancelled) setIdentities(rows); })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.detail || e.message : (vi ? "Không tải được." : "Failed to load."));
      });
    return () => { cancelled = true; };
  }, [lecturerId, vi]);

  return (
    <div className="mt-3">
      <span className="font-semibold text-slate-600 block mb-1">
        {vi ? "ID Scopus đã duyệt:" : "Approved Scopus IDs:"}
      </span>
      {error && <p className="text-[11px] text-rose-600">{error}</p>}
      {!error && identities === null && (
        <p className="text-[11px] text-slate-400">{vi ? "Đang tải dữ liệu..." : "Loading…"}</p>
      )}
      {!error && identities !== null && identities.length === 0 && (
        <p className="text-[11px] text-slate-400">
          {vi ? "Chưa có ID Scopus nào được duyệt cho giảng viên này." : "No approved Scopus ID for this lecturer yet."}
        </p>
      )}
      {!error && identities !== null && identities.length > 0 && (
        <ul className="space-y-1.5" data-testid="lecturer-scopus-identities">
          {identities.map((identity) => (
            <li
              key={identity.identity_id}
              className="flex flex-wrap items-center gap-2 rounded-[5px] border border-slate-200 bg-slate-50/60 px-2.5 py-1.5"
            >
              <a
                href={`https://www.scopus.com/authid/detail.uri?authorId=${encodeURIComponent(identity.scopus_id)}`}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-xs font-semibold text-[#3A5FC3] hover:underline"
              >
                {identity.scopus_id}
              </a>
              <span className="text-xs text-slate-600">{identity.preferred_name}</span>
              <span className="text-[11px] text-slate-400">
                {identity.publication_count ?? 0} {vi ? "công bố" : "publications"}
              </span>
              {identity.is_primary && (
                <span className="inline-flex h-badge items-center rounded-[5px] border border-emerald-200 bg-emerald-50 px-2 text-[10px] font-bold text-emerald-700">
                  {vi ? "ID chính" : "Main ID"}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
