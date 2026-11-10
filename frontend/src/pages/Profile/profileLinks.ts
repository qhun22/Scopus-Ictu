/** Only render external profile links with web URL protocols. */
export function webProfileUrl(value: string | null | undefined): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export function orcidProfileUrl(value: string | null | undefined): string | null {
  const identifier = value?.trim().replace(/^https?:\/\/(?:www\.)?orcid\.org\//i, "").replace(/\/$/, "");
  return identifier && /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/i.test(identifier)
    ? `https://orcid.org/${identifier.toUpperCase()}`
    : null;
}
