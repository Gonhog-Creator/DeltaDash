import { Link } from 'react-router-dom';
import { useMaterials } from '../hooks/useMaterials';
import { useShots } from '../hooks/useShots';
import { usePanels } from '../hooks/usePanels';
import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ConfirmModal } from '../components/ConfirmModal';

export function Dashboard() {
  const { data: materials } = useMaterials();
  const { data: shots } = useShots();
  const { data: panels } = usePanels();
  const { isAdmin } = useAuth();
  const [stats, setStats] = useState({ test_session_count: 0, total_shots: 0 });
  const [isSyncing, setIsSyncing] = useState(false);
  const [showSyncSuccessModal, setShowSyncSuccessModal] = useState(false);
  const [syncResults, setSyncResults] = useState<any>(null);
  const [showBackupModal, setShowBackupModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [backupConfirmText, setBackupConfirmText] = useState('');
  const [restoreConfirmText, setRestoreConfirmText] = useState('');
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [version, setVersion] = useState<string>('unknown');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
        console.log('Stats data:', data);
        setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      }
    };

    const fetchVersion = async () => {
      try {
        const data = await apiClient.get<{ version: string }>('/api/v1/admin/version');
        setVersion(data.version);
      } catch (error) {
        console.error('Failed to fetch version:', error);
      }
    };

    fetchStats();
    fetchVersion();
  }, []);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const result = await apiClient.post('/api/v1/admin/sync-database');
      setSyncResults(result);
      setShowSyncSuccessModal(true);
      // Refresh stats after sync
      const data = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
      setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
    } catch (error) {
      console.error('Failed to sync database:', error);
      alert('Failed to sync database. Check console for details.');
    } finally {
      setIsSyncing(false);
    }
  };

  const handleBackup = async () => {
    setIsBackingUp(true);
    try {
      const response = await fetch('/api/v1/admin/backup', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      
      if (!response.ok) {
        throw new Error('Backup failed');
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `deltadash_backup_${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      setShowBackupModal(false);
      setBackupConfirmText('');
    } catch (error) {
      console.error('Failed to create backup:', error);
      alert('Failed to create backup. Check console for details.');
    } finally {
      setIsBackingUp(false);
    }
  };

  const handleRestore = async () => {
    if (!restoreFile) {
      alert('Please select a backup file');
      return;
    }
    
    setIsRestoring(true);
    try {
      const formData = new FormData();
      formData.append('backup_file', restoreFile);
      
      const response = await fetch('/api/v1/admin/restore', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error('Restore failed');
      }
      
      alert('Backup restored successfully. The page will now reload.');
      window.location.reload();
    } catch (error) {
      console.error('Failed to restore backup:', error);
      alert('Failed to restore backup. Check console for details.');
    } finally {
      setIsRestoring(false);
      setShowRestoreModal(false);
      setRestoreConfirmText('');
      setRestoreFile(null);
    }
  };

  const dashboardStats = [
    { label: 'Total Materials', value: materials?.length || 0, color: 'bg-blue-500' },
    { label: 'Total Shots', value: stats.total_shots || 0, color: 'bg-purple-500' },
    { label: 'Total Products', value: panels?.length || 0, color: 'bg-green-500' },
    { label: 'Test Sessions', value: stats.test_session_count || 0, color: 'bg-orange-500' },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">DeltaDash</h1>
        {isAdmin && (
          <div className="flex space-x-3">
            <button
              onClick={handleSync}
              disabled={isSyncing}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSyncing ? 'Syncing...' : 'Sync Database (Pull)'}
            </button>
            <button
              onClick={() => setShowBackupModal(true)}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              Download Backup
            </button>
            <button
              onClick={() => setShowRestoreModal(true)}
              className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700"
            >
              Restore Backup
            </button>
          </div>
        )}
      </div>
      
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

      {showSyncSuccessModal && syncResults && (
        <ConfirmModal
          title="Database Sync Complete"
          message={
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Database sync completed successfully. Records synced:</p>
              <div className="bg-gray-50 p-3 rounded-md">
                {Object.entries(syncResults.synced_records).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-gray-700 capitalize">{key}:</span>
                    <span className="font-medium text-gray-900">{value as number}</span>
                  </div>
                ))}
              </div>
            </div>
          }
          confirmLabel="Close"
          variant="default"
          onConfirm={() => setShowSyncSuccessModal(false)}
          onCancel={() => setShowSyncSuccessModal(false)}
        />
      )}
      {showBackupModal && (
        <ConfirmModal
          title="Download Backup"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600">This will create a backup of the database and all storage files. Type "confirm" to proceed.</p>
              <input
                type="text"
                value={backupConfirmText}
                onChange={(e) => setBackupConfirmText(e.target.value)}
                placeholder="Type 'confirm'"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          }
          confirmLabel="Download"
          variant="danger"
          onConfirm={handleBackup}
          onCancel={() => {
            setShowBackupModal(false);
            setBackupConfirmText('');
          }}
          disabled={backupConfirmText !== 'confirm' || isBackingUp}
        />
      )}
      {showRestoreModal && (
        <ConfirmModal
          title="Restore Backup"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600">This will replace the current database and storage files with the backup. Type "confirm" to proceed.</p>
              <input
                type="file"
                onChange={(e) => setRestoreFile(e.target.files?.[0] || null)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <input
                type="text"
                value={restoreConfirmText}
                onChange={(e) => setRestoreConfirmText(e.target.value)}
                placeholder="Type 'confirm'"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>
          }
          confirmLabel="Restore"
          variant="danger"
          onConfirm={handleRestore}
          onCancel={() => {
            setShowRestoreModal(false);
            setRestoreConfirmText('');
            setRestoreFile(null);
          }}
          disabled={restoreConfirmText !== 'confirm' || !restoreFile || isRestoring}
        />
      )}
    </div>
  );
}
