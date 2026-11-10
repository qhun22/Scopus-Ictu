import { Link, useNavigate } from "react-router-dom";
import { SearchX, ArrowLeft, Home } from "lucide-react";
import { useI18n } from "../../i18n";

export default function NotFoundPage() {
  const { locale } = useI18n();
  const navigate = useNavigate();
  const vi = locale === "vi";

  return (
    <div className="flex min-h-[calc(100vh-10rem)] items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-md rounded-[5px] border border-slate-200/80 bg-white p-8 text-center shadow-sm sm:p-10">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#EBEFF9] text-[#3A5FC3]">
          <SearchX className="h-8 w-8" strokeWidth={1.8} />
        </div>

        <p className="mt-5 text-xs font-bold uppercase tracking-[0.2em] text-slate-400">
          404
        </p>
        <h1 className="mt-1.5 text-xl font-bold text-slate-800 sm:text-2xl">
          {vi ? "Không tìm thấy trang" : "Page not found"}
        </h1>
        <p className="mx-auto mt-2.5 max-w-sm text-sm text-slate-500">
          {vi
            ? "Đường dẫn này không tồn tại hoặc đã được thay đổi. Kiểm tra lại địa chỉ, hoặc quay về trang chủ."
            : "This address doesn't exist or has moved. Check the URL, or head back to the home page."}
        </p>

        <div className="mt-7 flex flex-col-reverse items-center justify-center gap-2.5 sm:flex-row">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-[5px] border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-xs transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200 sm:w-auto"
          >
            <ArrowLeft className="h-4 w-4" strokeWidth={1.8} />
            {vi ? "Quay lại" : "Go back"}
          </button>
          <Link
            to="/home"
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-[5px] bg-[#3A5FC3] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#2f4ea6] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/30 sm:w-auto"
          >
            <Home className="h-4 w-4" strokeWidth={1.8} />
            {vi ? "Về trang chủ" : "Back to home"}
          </Link>
        </div>
      </div>
    </div>
  );
}
