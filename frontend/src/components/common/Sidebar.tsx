import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/lecturers", label: "Lecturers" },
  { to: "/imports", label: "Imports" },
  { to: "/publications", label: "Publications" },
  { to: "/approval-queue", label: "Approval Queue" },
  { to: "/audit-logs", label: "Audit Logs" },
];

export default function Sidebar() {
  return (
    <aside className="hidden w-56 border-r border-gray-200 bg-gray-50 md:block">
      <nav className="flex flex-col p-3">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === "/"}
            className={({ isActive }) =>
              `mb-1 rounded px-3 py-2 text-sm ${
                isActive ? "bg-blue-100 text-blue-700" : "text-gray-700 hover:bg-gray-100"
              }`
            }
          >
            {l.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}