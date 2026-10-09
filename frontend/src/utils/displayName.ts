/**
 * Display-name repair for one KNOWN corruption: the ADMIN label "Quản trị viên"
 * that was stored/echoed as "Qu?n tr? vi?n" (non-ASCII letters replaced by "?").
 * Only that exact pattern (or a name made solely of "?" and spaces) is treated
 * as corrupted; any other name that legitimately contains "?" is left untouched.
 */
const CORRUPTED_ADMIN = /^qu\?n tr\? vi\?n$/i;
const ONLY_PLACEHOLDERS = /^[\s?]+$/;

export function isCorruptedName(name: string | null | undefined): boolean {
  if (!name) return false;
  const trimmed = name.trim();
  return CORRUPTED_ADMIN.test(trimmed) || ONLY_PLACEHOLDERS.test(trimmed);
}

export function adminLabel(locale: "vi" | "en" = "vi"): string {
  return locale === "vi" ? "Quản trị viên" : "Administrator";
}

/** Returns a safe display name; `fallback` is used when the name is empty/corrupted for non-ADMIN users. */
export function safeDisplayName(
  name: string | null | undefined,
  role: string | null | undefined,
  options: { locale?: "vi" | "en"; fallback?: string } = {},
): string {
  const { locale = "vi", fallback } = options;
  const isAdmin = role?.toUpperCase() === "ADMIN";
  if (name && !isCorruptedName(name)) return name;
  if (isAdmin) return adminLabel(locale);
  return fallback ?? (locale === "vi" ? "Người dùng" : "User");
}
