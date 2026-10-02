import { useEffect, useState } from "react";
import { User } from "../../api/auth";
import { getUsers } from "../../api/users";
import { useToast } from "../../contexts/ToastContext";
import { useI18n } from "../../i18n";

export default function UsersPage() {
  const toast = useToast();
  const { t, getRoleLabel, locale } = useI18n();

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>("");
  const [roleFilter, setRoleFilter] = useState<string>("ALL");

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers();
      setUsers(data);
    } catch {
      toast.error(
        locale === "vi" ? "Lỗi" : "Error",
        locale === "vi" ? "Không thể tải danh sách người dùng." : "Unable to load users list.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.email.toLowerCase().includes(search.toLowerCase()) ||
      u.display_name.toLowerCase().includes(search.toLowerCase()) ||
      u.id.toLowerCase().includes(search.toLowerCase());

    const matchesRole =
      roleFilter === "ALL" || u.role.toUpperCase() === roleFilter.toUpperCase();

    return matchesSearch && matchesRole;
  });

  const countByRole = (roleName: string) =>
    users.filter((u) => u.role.toUpperCase() === roleName.toUpperCase()).length;

  const renderRoleBadge = (role: string) => {
    const r = role.toUpperCase();
    if (r === "ADMIN") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-[#3A5FC3]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#3A5FC3]" />
          {getRoleLabel(role)}
        </span>
      );
    }
    if (r === "REVIEWER") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-bold text-amber-700">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
          {getRoleLabel(role)}
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
        {getRoleLabel(role)}
      </span>
    );
  };

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      {/* Header Title Section */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800 sm:text-2xl">
            {t.users.title}
          </h1>
          <p className="text-xs text-slate-500 sm:text-sm">
            {t.users.subtitle}
          </p>
        </div>

        <button
          type="button"
          onClick={fetchUsers}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 disabled:opacity-50 cursor-pointer"
        >
          <svg
            className={`h-4 w-4 text-slate-500 ${loading ? "animate-spin" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span>{t.common.refresh}</span>
        </button>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-slate-500">{t.users.totalUsers}</span>
          <p className="mt-1 text-2xl font-black text-slate-800">{users.length}</p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-blue-600">{t.roles.ADMIN_WITH_CODE}</span>
          <p className="mt-1 text-2xl font-black text-[#3A5FC3]">{countByRole("ADMIN")}</p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-emerald-600">{t.roles.LECTURER_WITH_CODE}</span>
          <p className="mt-1 text-2xl font-black text-emerald-600">{countByRole("LECTURER")}</p>
        </div>

        <div className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs">
          <span className="text-xs font-medium text-amber-600">{t.roles.REVIEWER_WITH_CODE}</span>
          <p className="mt-1 text-2xl font-black text-amber-600">{countByRole("REVIEWER")}</p>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.users.searchPlaceholder}
            className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50/50 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#3A5FC3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 sm:text-sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-slate-500">{t.common.role}:</span>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 focus:border-[#3A5FC3] focus:outline-none focus:ring-2 focus:ring-[#3A5FC3]/20 cursor-pointer"
          >
            <option value="ALL">{t.roles.ALL}</option>
            <option value="ADMIN">{t.roles.ADMIN}</option>
            <option value="LECTURER">{t.roles.LECTURER}</option>
            <option value="REVIEWER">{t.roles.REVIEWER}</option>
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200/80 bg-slate-50/70 text-slate-600">
              <tr>
                <th className="px-4 py-3 font-semibold">{t.users.colUser}</th>
                <th className="px-4 py-3 font-semibold">{t.users.colEmail}</th>
                <th className="px-4 py-3 font-semibold">{t.users.colRole}</th>
                <th className="px-4 py-3 font-semibold">{t.users.colLecturerLink}</th>
                <th className="px-4 py-3 font-semibold">{t.users.colUserId}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3A5FC3]" />
                      <span>{t.common.loading}</span>
                    </div>
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400">
                    <div className="flex flex-col items-center gap-1">
                      <svg className="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span className="font-semibold text-slate-600">{t.common.noData}</span>
                      <span className="text-[11px] text-slate-400">{t.common.noDataSub}</span>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#3A5FC3] text-xs font-bold text-white shadow-xs">
                          {u.display_name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <span className="font-bold text-slate-800">{u.display_name}</span>
                          <span className="block text-[10px] text-slate-400">
                            {locale === "vi" ? "Tài khoản chính thức" : "Official account"}
                          </span>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3 font-medium text-slate-700">
                      {u.email}
                    </td>

                    <td className="px-4 py-3">
                      {renderRoleBadge(u.role)}
                    </td>

                    <td className="px-4 py-3 text-slate-600">
                      {u.lecturer_id ? (
                        <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700">
                          ID: {u.lecturer_id.slice(0, 8)}...
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">{t.users.notLinked}</span>
                      )}
                    </td>

                    <td className="px-4 py-3 font-mono text-[11px] text-slate-400">
                      {u.id}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/50 px-4 py-2.5 text-[11px] text-slate-500">
          <span>
            {t.common.showingCount} <strong>{filteredUsers.length}</strong> {t.common.of} {users.length} {t.common.users}
          </span>
          <span>Dữ liệu từ bảng quản trị <code>users</code></span>
        </div>
      </div>
    </div>
  );
}
