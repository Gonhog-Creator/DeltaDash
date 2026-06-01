import { Link } from 'react-router-dom';
import { useMaterials } from '../hooks/useMaterials';
import { useShots } from '../hooks/useShots';
import { useVests } from '../hooks/useVests';
import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ConfirmModal } from '../components/ConfirmModal';
import { normalizeString } from '../utils/string';

export function Dashboard() {
  const { data: materials } = useMaterials();
  const { data: shots } = useShots();
  const { data: vests } = useVests();
  const { isAdmin, role } = useAuth();
  const [stats, setStats] = useState({ test_session_count: 0, total_shots: 0 });
  const [isSyncing, setIsSyncing] = useState(false);
  const [showSyncSuccessModal, setShowSyncSuccessModal] = useState(false);
  const [syncResults, setSyncResults] = useState<any>(null);
  const [showBackupModal, setShowBackupModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [backupConfirmText, setBackupConfirmText] = useState('');
  const [restoreConfirmText, setRestoreConfirmText] = useState('');
  const [selectedBackup, setSelectedBackup] = useState<string | null>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [restoreTaskId, setRestoreTaskId] = useState<string | null>(null);
  const [restoreProgress, setRestoreProgress] = useState<{status: string, progress: number, message: string} | null>(null);
  const [version, setVersion] = useState<string>('unknown');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
        setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
      } catch (error) {
        // Silent fail - stats not critical
      }
    };

    const fetchVersion = async () => {
      try {
        const data = await apiClient.get<{ version: string }>('/api/v1/admin/version');
        setVersion(data.version);
      } catch (error) {
        // Silent fail - version not critical
      }
    };

    fetchStats();
    fetchVersion();
  }, []);

  useEffect(() => {
    if (showRestoreModal) {
      fetchBackups();
    }
  }, [showRestoreModal]);

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
      const response = await apiClient.post<{ message: string; filename: string }>('/api/v1/admin/backup');

      // Download the backup file
      const downloadResponse = await fetch(`/api/v1/admin/backups/${response.filename}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!downloadResponse.ok) {
        throw new Error('Failed to download backup');
      }

      const blob = await downloadResponse.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = response.filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setShowBackupModal(false);
      setBackupConfirmText('');
      alert('Backup created successfully');
    } catch (error) {
      console.error('Failed to create backup:', error);
      alert('Failed to create backup. Check console for details.');
    } finally {
      setIsBackingUp(false);
    }
  };

  const fetchBackups = async () => {
    try {
      const response = await apiClient.get<{ backups: any[] }>('/api/v1/admin/backups');
      setBackups(response.backups);
    } catch (error) {
      console.error('Failed to fetch backups:', error);
    }
  };

  const handleDownloadBackup = async (filename: string) => {
    try {
      const response = await fetch(`/api/v1/admin/backups/${filename}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to download backup');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Failed to download backup:', error);
      alert('Failed to download backup');
    }
  };

  const handleDeleteBackup = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) {
      return;
    }

    try {
      await apiClient.delete(`/api/v1/admin/backups/${filename}`);
      await fetchBackups();
    } catch (error) {
      console.error('Failed to delete backup:', error);
      alert('Failed to delete backup');
    }
  };

  const handleUploadBackup = async (file: File) => {
    setIsUploading(true);
    try {
      // Convert file to base64
      const reader = new FileReader();
      const base64Promise = new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const result = reader.result as string;
          // Remove data URL prefix
          const base64 = result.split(',')[1];
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      const base64Content = await base64Promise;

      const response = await apiClient.post<{ message: string; filename: string }>('/api/v1/admin/backups/upload-base64', {
        filename: file.name,
        content: base64Content
      });

      await fetchBackups();
      alert('Backup uploaded successfully');
    } catch (error) {
      console.error('Failed to upload backup:', error);
      alert('Failed to upload backup. Check console for details.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedBackup) {
      alert('Please select a backup to restore');
      return;
    }

    setIsRestoring(true);
    setRestoreProgress(null);
    try {
      const response = await apiClient.post<{ task_id: string; message: string }>('/api/v1/admin/restore', {
        filename: selectedBackup
      });

      setRestoreTaskId(response.task_id);

      // Poll for progress
      const pollInterval = setInterval(async () => {
        try {
          const progressResponse = await fetch(`/api/v1/admin/restore/progress/${response.task_id}`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          });

          if (!progressResponse.ok) {
            clearInterval(pollInterval);
            throw new Error('Failed to get progress');
          }

          const progress = await progressResponse.json();
          setRestoreProgress(progress);

          if (progress.status === 'completed') {
            clearInterval(pollInterval);
            setIsRestoring(false);
            setShowRestoreModal(false);
            setRestoreConfirmText('');
            setSelectedBackup(null);
            setRestoreTaskId(null);
            setRestoreProgress(null);
            alert('Backup restored successfully. The page will now reload.');
            window.location.reload();
          } else if (progress.status === 'error') {
            clearInterval(pollInterval);
            setIsRestoring(false);
            setRestoreTaskId(null);
            setRestoreProgress(null);
            alert(`Restore failed: ${progress.message}`);
          }
        } catch (error) {
          clearInterval(pollInterval);
          setIsRestoring(false);
          setRestoreTaskId(null);
          setRestoreProgress(null);
          console.error('Failed to get progress:', error);
        }
      }, 1000);

    } catch (error) {
      console.error('Failed to restore backup:', error);
      alert('Failed to restore backup. Check console for details.');
      setIsRestoring(false);
    }
  };

  const dashboardStats = [
    { label: 'Total Vests', value: vests?.length || 0, color: 'bg-green-500' },
    { label: 'Total Materials', value: materials?.length || 0, color: 'bg-blue-500' },
    { label: 'Test Sessions', value: stats.test_session_count || 0, color: 'bg-orange-500' },
    { label: 'Total Shots', value: stats.total_shots || 0, color: 'bg-purple-500' },
  ];

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">DeltaDash</h1>
        {isAdmin && role !== 'viewer' && (
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
                  <span className="text-sm text-gray-500">{normalizeString(material.material_class) || 'Unknown'}</span>
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
            <Link to="/vests" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Vests
            </Link>
            <Link to="/analytics" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Analytics
            </Link>
            <Link to="/predictions" className="block w-full text-left px-4 py-2 bg-gray-50 hover:bg-gray-100 rounded-md text-sm text-gray-700">
              Predictions
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
                    <span className="text-gray-700">{normalizeString(key)}:</span>
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
              <p className="text-sm text-gray-600">This will replace the current database and storage files with the selected backup.</p>
              <div className="border-t pt-4">
                <p className="text-sm font-medium text-gray-700 mb-2">Upload a backup file</p>
                <input
                  type="file"
                  id="backup-upload"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      handleUploadBackup(file);
                    }
                  }}
                />
                <label
                  htmlFor="backup-upload"
                  className={`inline-flex items-center px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 cursor-pointer ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  {isUploading ? 'Uploading...' : 'Choose file to upload'}
                </label>
              </div>
              {backups.length === 0 ? (
                <p className="text-sm text-gray-500">No backups available. Upload a backup file above.</p>
              ) : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {backups.map((backup) => (
                    <div
                      key={backup.filename}
                      className={`p-3 border rounded-md cursor-pointer ${
                        selectedBackup === backup.filename ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
                      }`}
                      onClick={() => setSelectedBackup(backup.filename)}
                    >
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{backup.filename}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(backup.created).toLocaleString()} • {(backup.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadBackup(backup.filename);
                            }}
                            className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                          >
                            Download
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteBackup(backup.filename);
                            }}
                            className="text-xs px-2 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <input
                type="text"
                value={restoreConfirmText}
                onChange={(e) => setRestoreConfirmText(e.target.value)}
                placeholder="Type 'confirm'"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              {isRestoring && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-blue-800">
                      {restoreProgress?.message || 'Starting restore...'}
                    </p>
                    <p className="text-sm text-blue-600">{restoreProgress?.progress || 0}%</p>
                  </div>
                  <div className="w-full bg-blue-200 rounded-full h-2.5">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${restoreProgress?.progress || 0}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          }
          confirmLabel={isRestoring ? "Restoring..." : "Restore"}
          variant="danger"
          onConfirm={handleRestore}
          onCancel={() => {
            if (!isRestoring) {
              setShowRestoreModal(false);
              setRestoreConfirmText('');
              setSelectedBackup(null);
            }
          }}
          disabled={restoreConfirmText !== 'confirm' || !selectedBackup || isRestoring}
        />
      )}
    </div>
  );
}
