import type { ApprovedScopusIdentity } from "../../types/lecturerScopus";

export function filterIdentities(identities: ApprovedScopusIdentity[], query: string, kind: string): ApprovedScopusIdentity[] {
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[đĐ]/g, "d").toLowerCase();
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);
  return identities.filter((identity) => {
    if (kind === "primary" && !identity.is_primary) return false;
    if (kind === "other" && identity.is_primary) return false;
    const text = normalize([identity.preferred_name, identity.scopus_id, ...identity.name_variants].join(" "));
    return words.every((word) => text.includes(word));
  });
}
