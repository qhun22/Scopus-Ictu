import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <section className="w-full max-w-xl rounded-2xl bg-white p-8 text-center shadow-lg shadow-slate-200/70">
        <img
          src="/assets/ictu.png"
          alt="Logo ICTU"
          className="mx-auto h-20 w-20 rounded-full object-contain"
        />
        <h1 className="mt-5 text-2xl font-bold text-slate-900">Trang chủ Scopus ICTU</h1>
        <p className="mt-3 text-slate-500">
          Khu vực này sẽ được hoàn thiện trong các milestone tiếp theo.
        </p>
        <Link
          to="/login"
          className="mt-6 inline-flex rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white hover:bg-blue-700"
        >
          Quay lại đăng nhập
        </Link>
      </section>
    </main>
  );
}
