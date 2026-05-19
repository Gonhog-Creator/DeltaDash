import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { user, logout, isLoggingOut, isAdmin } = useAuth();
  const location = useLocation();
  const [version, setVersion] = useState<string>('0.1.0');

  const navItems = [
    { path: '/', label: 'Dashboard' },
    { path: '/test-sessions', label: 'Test Sessions' },
    { path: '/materials', label: 'Materials' },
    { path: '/vests', label: 'Vests' },
    { path: '/ammunition', label: 'Ammunition' },
    { path: '/analytics', label: 'Analytics' },
  ];

  const isActive = (path: string) => location.pathname === path;

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const data = await apiClient.get<{ version: string }>('/api/v1/admin/version');
        setVersion(data.version);
      } catch (error) {
        // Silent fail - version not critical
      }
    };

    fetchVersion();
  }, []);

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="h-16 flex items-center px-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-900">DeltaDash</h1>
          {isAdmin && (
            <span className="ml-2 px-2 py-0.5 text-xs font-medium bg-red-100 text-red-800 rounded-full">
              Admin
            </span>
          )}
        </div>
        <nav className="flex-1 py-4 overflow-y-auto">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-4 py-2.5 text-sm font-medium transition-colors ${
                isActive(item.path)
                  ? 'bg-indigo-50 text-indigo-700 border-r-2 border-indigo-500'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-200">
          <p className="text-xs text-gray-400">v{version}</p>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-end px-6">
          <span className="text-sm text-gray-700 mr-4">{user?.email}</span>
          <button
            onClick={() => logout()}
            disabled={isLoggingOut}
            className="text-sm text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            {isLoggingOut ? 'Logging out...' : 'Logout'}
          </button>
        </header>
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
