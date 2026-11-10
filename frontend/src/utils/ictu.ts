/** True when an affiliation string names ICTU (Vietnamese or English), ignoring case and diacritics. */
export function isIctuUnit(text: string | null | undefined): boolean {
  if (!text) return false;
  const plain = text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase();
  return (
    (plain.includes("cong nghe thong tin") && plain.includes("truyen thong")) ||
    (plain.includes("information and communication technology") && plain.includes("thai nguyen")) ||
    /ictu/.test(plain)
  );
}
