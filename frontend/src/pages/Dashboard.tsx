import { Link } from 'react-router-dom';
import { useMaterials } from '../hooks/useMaterials';
import { useShots } from '../hooks/useShots';
import { usePanels } from '../hooks/usePanels';
import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

export function Dashboard() {
  const { data: materials } = useMaterials();
  const { data: shots } = useShots();
  const { data: panels } = usePanels();
  const [stats, setStats] = useState({ test_session_count: 0, total_shots: 0 });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
        console.log('Stats response status:', response.status);
        if (response.ok) {
          const data = await response.json();
          console.log('Stats data:', data);
          setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
        } else {
          console.error('Stats response not ok:', response.statusText);
        }
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      }
    };
    fetchStats();
  }, []);

  const dashboardStats = [
    { label: 'Total Materials', value: materials?.length || 0, color: 'bg-blue-500' },
    { label: 'Total Shots', value: stats.total_shots || 0, color: 'bg-purple-500' },
    { label: 'Total Products', value: panels?.length || 0, color: 'bg-green-500' },
    { label: 'Test Sessions', value: stats.test_session_count || 0, color: 'bg-orange-500' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">DeltaDash</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {dashboardStats.map((stat) => (
          <div key={stat.label} className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center">
              <div className={`${stat.color} rounded-md p-3`}>
                <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-500">{stat.label}</p>
                <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Materials</h2>
          {materials && materials.length > 0 ? (
            <ul className="divide-y divide-gray-200">
              {materials.slice(0, 5).map((material) => (
                <li key={material.id} className="py-3 flex justify-between">
                  <span className="text-sm text-gray-900">{material.name}</span>
                  <span className="text-sm text-gray-500">{material.material_class || 'Unknown'}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No materials yet. Add your first material to get started.</p>
          )}
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Pages</h2>
          <div className="space-y-3">
            <Link to="/materials" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Materials
            </Link>
            <Link to="/ammunition" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Ammunition
            </Link>
            <Link to="/test-sessions" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Test Sessions
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
