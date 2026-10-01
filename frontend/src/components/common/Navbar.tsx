import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link to="/home" className="text-lg font-semibold">
          Scopus-Ictu
        </Link>
        <span className="text-sm text-gray-500">M0 skeleton</span>
      </div>
    </header>
  );
}
