import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { to: '/owner', label: 'Fuel Entries', end: true },
  { to: '/owner/vehicles', label: 'Vehicles' },
  { to: '/owner/petrol-pumps', label: 'Petrol Pumps' },
  { to: '/owner/operators', label: 'Operators' },
];

export default function OwnerLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navClass = ({ isActive }) =>
    `whitespace-nowrap px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors ${
      isActive
        ? 'bg-blue-600 text-white'
        : 'text-slate-700 hover:bg-slate-100'
    }`;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-600 text-white font-bold text-sm flex items-center justify-center">
                FF
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-blue-600">
                  Owner Portal
                </p>
                <p className="text-sm font-bold text-slate-900">
                  {user?.full_name || user?.username}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={handleLogout}
              className="md:hidden rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Logout
            </button>
          </div>

          <div className="flex items-center justify-between gap-4 overflow-x-auto pb-1 md:pb-0">
            <nav className="flex items-center gap-1.5" aria-label="Owner Navigation">
              {NAV_ITEMS.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={navClass}>
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <button
              type="button"
              onClick={handleLogout}
              className="hidden md:inline-flex rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
