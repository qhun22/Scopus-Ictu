/**
 * Định dạng ngày giờ thống nhất: HH:mm:ss dd/MM/yyyy (24 giờ, thứ tự quen thuộc của tiếng Việt), múi giờ của trình duyệt.
 * Không phụ thuộc locale mặc định của hệ điều hành (tránh "10/9/2026" bị hiểu nhầm là ngày 10 tháng 9).
 * Chỉ ảnh hưởng hiển thị; dữ liệu và timestamp trong database không đổi.
 */
const LOCALE_STORAGE_KEY = "locale";

function activeLocale(): string {
  try {
    return window.localStorage.getItem(LOCALE_STORAGE_KEY) === "en" ? "en-GB" : "vi-VN";
  } catch {
    return "vi-VN";
  }
}

export function formatTimestamp(raw: string | null | undefined): string {
  if (!raw) return "—";
  const d = new Date(raw);
  if (isNaN(d.getTime())) return raw;
  return new Intl.DateTimeFormat(activeLocale(), {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(d);
}
