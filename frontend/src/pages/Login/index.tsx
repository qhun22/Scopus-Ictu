import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleNotice, setGoogleNotice] = useState(false);
  const [logoSrc, setLogoSrc] = useState("/logoictu.png");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!form.email || !form.password) return;

    setLoading(true);
    // Chuẩn bị điều hướng đến /home khi hoàn thành xác thực
    setTimeout(() => {
      setLoading(false);
      navigate("/home");
    }, 500);
  };

  const handleGoogleClick = () => {
    setGoogleNotice(true);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#ffffff] px-4 py-8 sm:px-6">
      <div className="w-full max-w-[880px] overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_20px_50px_rgba(15,23,42,0.06)]">
        <div className="grid grid-cols-1 md:grid-cols-2">
          {/* Cột trái: Branding ICTU */}
          <section className="flex flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100/70 p-8 text-center md:border-r md:border-slate-200/80 md:p-12">
            <div className="relative flex items-center justify-center">
              <img
                src={logoSrc}
                alt="Logo Đại học Công nghệ Thông tin & Truyền thông"
                onError={() => {
                  if (logoSrc === "/logoictu.png") {
                    setLogoSrc("/assets/logoictu.png");
                  } else if (logoSrc === "/assets/logoictu.png") {
                    setLogoSrc("/assets/ictu.png");
                  }
                }}
                className="h-24 w-24 rounded-full bg-white object-contain shadow-md ring-4 ring-white"
              />
            </div>

            <p className="mt-6 text-xs font-semibold uppercase leading-relaxed tracking-wider text-[#334155] sm:text-sm sm:tracking-widest">
              ĐẠI HỌC CÔNG NGHỆ THÔNG TIN & TRUYỀN THÔNG THÁI NGUYÊN
            </p>

            <h1 className="mt-2 text-lg font-black uppercase tracking-wide text-[#3A5FC3] md:text-xl">
              CỔNG THÔNG TIN SCOPUS ICTU
            </h1>
          </section>

          {/* Cột phải: Form Đăng nhập */}
          <section className="flex flex-col justify-center bg-white p-8 md:p-10">
            <h2 className="text-center text-2xl font-bold uppercase tracking-tight text-slate-800">
              ĐĂNG NHẬP TÀI KHOẢN
            </h2>

            {googleNotice && (
              <div className="mt-4 flex items-center justify-between rounded-lg border border-blue-100 bg-blue-50/80 px-4 py-3 text-xs text-blue-800">
                <span>Tính năng Đăng nhập bằng Google sẽ khả dụng trong phiên bản M2.2.</span>
                <button
                  type="button"
                  onClick={() => setGoogleNotice(false)}
                  className="ml-2 font-bold text-blue-600 hover:text-blue-800"
                  aria-label="Đóng thông báo"
                >
                  ✕
                </button>
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {/* Trường 1: Email ICTU */}
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-sm font-medium text-slate-700"
                >
                  Email ICTU
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                    {/* User Icon */}
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.8"
                        d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                      />
                    </svg>
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    value={form.email}
                    onChange={handleChange}
                    placeholder="youname@ictu.edu.vn"
                    className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-4 text-sm text-slate-800 placeholder:text-slate-400 transition-all focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                </div>
              </div>

              {/* Trường 2: Mật khẩu */}
              <div>
                <label
                  htmlFor="password"
                  className="mb-1.5 block text-sm font-medium text-slate-700"
                >
                  Mật khẩu
                </label>
                <div className="relative">
                  <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                    {/* Lock Icon */}
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="1.8"
                        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                      />
                    </svg>
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    value={form.password}
                    onChange={handleChange}
                    placeholder="Nhập mật khẩu"
                    className="h-11 w-full rounded-lg border border-slate-200 bg-white pl-10 pr-11 text-sm text-slate-800 placeholder:text-slate-400 transition-all focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 transition-colors hover:text-slate-600 focus:outline-none"
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  >
                    {showPassword ? (
                      /* Eye Off Icon */
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="1.8"
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                        />
                      </svg>
                    ) : (
                      /* Eye Icon */
                      <svg
                        className="h-5 w-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="1.8"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="1.8"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Nút Đăng nhập */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="flex h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-[#3A5FC3] text-sm font-bold text-white shadow-sm transition-all duration-200 hover:bg-[#2f4ea6] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/40 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {loading && (
                    <svg
                      className="h-5 w-5 animate-spin text-white"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                  )}
                  <span>{loading ? "Đang xử lý..." : "Đăng nhập"}</span>
                </button>
              </div>

              {/* Phân cách "HOẶC" */}
              <div className="relative my-4 flex items-center justify-center">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200" />
                </div>
                <div className="relative bg-white px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
                  HOẶC
                </div>
              </div>

              {/* Nút Đăng nhập bằng Google */}
              <button
                type="button"
                onClick={handleGoogleClick}
                className="flex h-11 w-full cursor-pointer items-center justify-center gap-3 rounded-lg border border-slate-200 bg-white text-sm font-medium text-slate-700 shadow-sm transition-all duration-200 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-200"
              >
                {/* Google Multi-Color SVG Icon */}
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span>Đăng nhập bằng Google</span>
              </button>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
