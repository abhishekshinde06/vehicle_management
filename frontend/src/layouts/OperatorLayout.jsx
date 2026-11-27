import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function OperatorLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navLinkClass = ({ isActive }) =>
    `flex-1 sm:flex-none text-center px-5 py-3 rounded-xl text-base font-bold transition-colors ${
      isActive
        ? 'bg-blue-600 text-white shadow-xs'
        : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
    }`;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
                Operator Tablet Portal
              </span>
              <h1 className="text-lg font-bold text-slate-900">
                {user?.full_name || user?.username}
              </h1>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="sm:hidden rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Logout
            </button>
          </div>

          <nav className="flex items-center gap-2.5">
            <NavLink to="/operator" end className={navLinkClass}>
              New Fuel Entry
            </NavLink>
            <NavLink to="/operator/history" className={navLinkClass}>
              My History
            </NavLink>
            <button
              type="button"
              onClick={handleLogout}
              className="hidden sm:inline-flex rounded-xl border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Logout
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
