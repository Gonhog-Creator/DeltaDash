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
  const { data: materials, refetch: refetchMaterials } = useMaterials();
  const { data: shots, refetch: refetchShots } = useShots();
  const { data: vests, refetch: refetchVests } = useVests();
  const { isAdmin, role } = useAuth();
  const [stats, setStats] = useState({ test_session_count: 0, total_shots: 0 });
  const [isSyncing, setIsSyncing] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [showSyncSuccessModal, setShowSyncSuccessModal] = useState(false);
  const [syncResults, setSyncResults] = useState<any>(null);
  const [showSyncPreviewModal, setShowSyncPreviewModal] = useState(false);
  const [syncPreview, setSyncPreview] = useState<any>(null);
  const [selectedChanges, setSelectedChanges] = useState<Record<string, Record<string, string[]>>>({});
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [showResetConfirmModal, setShowResetConfirmModal] = useState(false);
  const [showSyncErrorModal, setShowSyncErrorModal] = useState(false);
  const [syncErrorMessage, setSyncErrorMessage] = useState('');
  const [selectedResetEntities, setSelectedResetEntities] = useState<string[]>([]);
  const [showBackupModal, setShowBackupModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [showBackupSuccessModal, setShowBackupSuccessModal] = useState(false);
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
  const [showAlembicModal, setShowAlembicModal] = useState(false);
  const [alembicStatus, setAlembicStatus] = useState<any>(null);
  const [loadingAlembic, setLoadingAlembic] = useState(false);
  const [targetVersion, setTargetVersion] = useState<string>('');
  const [sqlQuery, setSqlQuery] = useState<string>('');

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
    setIsPreviewLoading(true);
    try {
      const preview = await apiClient.get('/api/v1/admin/preview-sync');
      setSyncPreview(preview);
      
      // Initialize selected changes with all changes selected by default
      const initialSelection: Record<string, Record<string, string[]>> = {};
      preview.changes.forEach((entity: any) => {
        initialSelection[entity.entity_name] = {
          new: entity.new_records.map((r: any) => String(r.id)),
          updated: entity.updated_records.map((r: any) => String(r.id)),
          deleted: entity.deleted_records.map((r: any) => String(r.id))
        };
      });
      setSelectedChanges(initialSelection);
      
      setShowSyncPreviewModal(true);
    } catch (error) {
      console.error('Failed to preview sync:', error);
      alert('Failed to preview sync. Check console for details.');
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const handleToggleChange = (entityName: string, changeType: string, recordId: string) => {
    setSelectedChanges(prev => {
      const newSelection = { ...prev };
      if (!newSelection[entityName]) {
        newSelection[entityName] = { new: [], updated: [], deleted: [] };
      }
      const currentList = newSelection[entityName][changeType] || [];
      if (currentList.includes(recordId)) {
        newSelection[entityName][changeType] = currentList.filter(id => id !== recordId);
      } else {
        newSelection[entityName][changeType] = [...currentList, recordId];
      }
      return newSelection;
    });
  };

  const handleToggleEntity = (entityName: string, changeType: string, selectAll: boolean) => {
    setSelectedChanges(prev => {
      const newSelection = { ...prev };
      if (!newSelection[entityName]) {
        newSelection[entityName] = { new: [], updated: [], deleted: [] };
      }
      
      if (syncPreview) {
        const entity = syncPreview.changes.find((e: any) => e.entity_name === entityName);
        if (entity) {
          newSelection[entityName][changeType] = selectAll 
            ? entity[`${changeType}_records`].map((r: any) => String(r.id))
            : [];
        }
      }
      return newSelection;
    });
  };

  const handleApplySync = async () => {
    setShowSyncPreviewModal(false);
    setIsSyncing(true);
    try {
      const result = await apiClient.post('/api/v1/admin/sync-database', {
        confirmed_changes: selectedChanges
      });
      setSyncResults(result);
      setShowSyncSuccessModal(true);
      // Refresh stats after sync
      const data = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
      setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
      // Refetch all data after sync to show updated records
      refetchVests();
      refetchMaterials();
      refetchShots();
    } catch (error: any) {
      console.error('Failed to sync database:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to sync database. Check console for details.';
      setSyncErrorMessage(errorMessage);
      setShowSyncErrorModal(true);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleReset = async () => {
    setIsResetting(true);
    setShowResetConfirmModal(false);
    try {
      const result = await apiClient.post('/api/v1/admin/reset-database', {
        entities: selectedResetEntities.length > 0 ? selectedResetEntities : undefined
      });
      setSyncResults(result);
      setShowSyncSuccessModal(true);
      // Refresh stats after reset
      const data = await apiClient.get<{ test_session_count: number; total_shots: number }>('/api/v1/test-sessions/stats');
      setStats({ test_session_count: data.test_session_count, total_shots: data.total_shots });
      // Reset selection
      setSelectedResetEntities([]);
    } catch (error: any) {
      console.error('Failed to reset database:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to reset database. Check console for details.';
      setSyncErrorMessage(errorMessage);
      setShowSyncErrorModal(true);
    } finally {
      setIsResetting(false);
    }
  };

  const handleToggleResetEntity = (entity: string) => {
    setSelectedResetEntities(prev => 
      prev.includes(entity) 
        ? prev.filter(e => e !== entity)
        : [...prev, entity]
    );
  };

  const resetEntities = [
    { id: 'ammunition', label: 'Ammunition' },
    { id: 'materials', label: 'Materials' },
    { id: 'vests', label: 'Vests' },
    { id: 'vest_layers', label: 'Vest Layers' },
    { id: 'test_sessions', label: 'Test Sessions' },
    { id: 'shot_data', label: 'Shot Data' },
    { id: 'model_runs', label: 'Models' },
    { id: 'protocols', label: 'Protocols' },
    { id: 'locations', label: 'Locations' },
    { id: 'anchor_points', label: 'Anchor Points' },
    { id: 'anchor_point_layers', label: 'Anchor Point Layers' },
  ];

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
      setShowBackupSuccessModal(true);
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

  const handleFetchAlembicStatus = async () => {
    setLoadingAlembic(true);
    try {
      const status = await apiClient.get('/api/v1/admin/alembic/status');
      setAlembicStatus(status);
      if (status.current_versions.length > 0) {
        setTargetVersion(status.current_versions[0]);
      }
    } catch (error) {
      console.error('Failed to fetch alembic status:', error);
      alert('Failed to fetch alembic status');
    } finally {
      setLoadingAlembic(false);
    }
  };

  const handleFixAlembicHeads = async () => {
    if (!targetVersion) {
      alert('Please select a target version');
      return;
    }

    if (!confirm(`This will set the alembic version to ${targetVersion}. Continue?`)) {
      return;
    }

    try {
      await apiClient.post('/api/v1/admin/alembic/fix-heads', { target_version: targetVersion });
      alert('Alembic heads fixed successfully');
      setShowAlembicModal(false);
      setAlembicStatus(null);
    } catch (error) {
      console.error('Failed to fix alembic heads:', error);
      alert('Failed to fix alembic heads');
    }
  };

  const handleRunMigration = async () => {
    if (!confirm('This will run all pending alembic migrations. Continue?')) {
      return;
    }

    try {
      const response = await apiClient.post('/api/v1/admin/alembic/upgrade');
      alert(`Migration successful: ${response.message}`);
      setShowAlembicModal(false);
      setAlembicStatus(null);
      window.location.reload();
    } catch (error) {
      console.error('Failed to run migration:', error);
      alert('Failed to run migration');
    }
  };

  const handleExecuteSql = async () => {
    if (!sqlQuery.trim()) {
      alert('Please enter a SQL query');
      return;
    }

    if (!confirm('This will execute the SQL directly against the database. This can be dangerous. Continue?')) {
      return;
    }

    try {
      const response = await apiClient.post('/api/v1/admin/alembic/execute-sql', { sql: sqlQuery });
      alert(`SQL executed: ${response.message}`);
      setSqlQuery('');
    } catch (error) {
      console.error('Failed to execute SQL:', error);
      alert('Failed to execute SQL');
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
              disabled={isSyncing || isPreviewLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSyncing ? 'Syncing...' : isPreviewLoading ? 'Loading Preview...' : 'Preview & Sync Database'}
            </button>
            <button
              onClick={() => setShowResetConfirmModal(true)}
              disabled={isResetting}
              className="px-4 py-2 bg-red-700 text-white rounded-md hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isResetting ? 'Resetting...' : 'Reset Database'}
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
            <button
              onClick={() => {
                setShowAlembicModal(true);
                handleFetchAlembicStatus();
              }}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
            >
              Alembic Management
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

      {showSyncSuccessModal && syncResults && syncResults.applied_changes && (
        <ConfirmModal
          title="Database Sync Complete"
          message={
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Database sync completed successfully. Applied changes:</p>
              <div className="bg-gray-50 p-3 rounded-md">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">New records:</span>
                  <span className="font-medium text-green-600">{syncResults.applied_changes.new}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">Updated records:</span>
                  <span className="font-medium text-blue-600">{syncResults.applied_changes.updated}</span>
                </div>
              </div>
            </div>
          }
          confirmLabel="Close"
          variant="default"
          onConfirm={() => setShowSyncSuccessModal(false)}
          onCancel={() => setShowSyncSuccessModal(false)}
        />
      )}
      {showSyncErrorModal && (
        <ConfirmModal
          title="Sync Failed"
          message={
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Failed to sync database:</p>
              <div className="bg-red-50 border border-red-200 p-3 rounded-md">
                <p className="text-sm text-red-800 font-mono break-all">{syncErrorMessage}</p>
              </div>
            </div>
          }
          confirmLabel="Close"
          variant="danger"
          onConfirm={() => setShowSyncErrorModal(false)}
          onCancel={() => setShowSyncErrorModal(false)}
        />
      )}
      {showSyncPreviewModal && syncPreview && (
        <ConfirmModal
          title="Preview Database Sync Changes"
          message={
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                <p className="text-sm text-blue-800">
                  Summary: <span className="font-semibold">{syncPreview.summary.new}</span> new, 
                  <span className="font-semibold"> {syncPreview.summary.updated}</span> updated, 
                  <span className="font-semibold"> {syncPreview.summary.deleted}</span> deleted
                </p>
              </div>
              
              {syncPreview.changes.length === 0 ? (
                <p className="text-sm text-gray-600">No changes detected.</p>
              ) : (
                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {syncPreview.changes.map((entity: any) => (
                    <div key={entity.entity_name} className="border rounded-md p-3">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold text-gray-900 capitalize">{normalizeString(entity.entity_name)}</h3>
                      </div>
                      
                      {entity.new_records.length > 0 && (
                        <div className="mb-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-green-700">New Records ({entity.new_records.length})</span>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'new', true)}
                              className="text-xs text-blue-600 hover:text-blue-800"
                            >
                              Select All
                            </button>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'new', false)}
                              className="text-xs text-red-600 hover:text-red-800"
                            >
                              Deselect All
                            </button>
                          </div>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {entity.new_records.map((record: any) => (
                              <div key={record.id} className="flex items-start gap-2 text-xs p-1 hover:bg-gray-50 rounded">
                                <input
                                  type="checkbox"
                                  checked={selectedChanges[entity.entity_name]?.new?.includes(String(record.id)) || false}
                                  onChange={() => handleToggleChange(entity.entity_name, 'new', String(record.id))}
                                  className="mt-0.5"
                                />
                                <div className="flex-1">
                                  <span className="font-medium text-green-600">NEW:</span> {record.record_data?.name || record.id}
                                  {record.record_data && (
                                    <div className="ml-4 text-gray-500">
                                      {Object.entries(record.record_data).slice(0, 3).map(([key, value]) => (
                                        <div key={key}>{key}: {String(value).slice(0, 30)}</div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {entity.updated_records.length > 0 && (
                        <div className="mb-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-blue-700">Updated Records ({entity.updated_records.length})</span>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'updated', true)}
                              className="text-xs text-blue-600 hover:text-blue-800"
                            >
                              Select All
                            </button>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'updated', false)}
                              className="text-xs text-red-600 hover:text-red-800"
                            >
                              Deselect All
                            </button>
                          </div>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {entity.updated_records.map((record: any) => (
                              <div key={record.id} className="flex items-start gap-2 text-xs p-1 hover:bg-gray-50 rounded">
                                <input
                                  type="checkbox"
                                  checked={selectedChanges[entity.entity_name]?.updated?.includes(String(record.id)) || false}
                                  onChange={() => handleToggleChange(entity.entity_name, 'updated', String(record.id))}
                                  className="mt-0.5"
                                />
                                <div className="flex-1">
                                  <span className="font-medium text-blue-600">UPDATE:</span> {record.record_data?.name || record.id}
                                  {record.changes && (
                                    <div className="ml-4 text-gray-600">
                                      {record.changes.map((change: any, idx: number) => (
                                        <div key={idx} className="text-red-600">
                                          {change.field}: {String(change.old_value).slice(0, 20)} → {String(change.new_value).slice(0, 20)}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {entity.deleted_records.length > 0 && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-red-700">Deleted Records ({entity.deleted_records.length})</span>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'deleted', true)}
                              className="text-xs text-blue-600 hover:text-blue-800"
                            >
                              Select All
                            </button>
                            <button
                              onClick={() => handleToggleEntity(entity.entity_name, 'deleted', false)}
                              className="text-xs text-red-600 hover:text-red-800"
                            >
                              Deselect All
                            </button>
                          </div>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {entity.deleted_records.map((record: any) => (
                              <div key={record.id} className="flex items-start gap-2 text-xs p-1 hover:bg-gray-50 rounded">
                                <input
                                  type="checkbox"
                                  checked={selectedChanges[entity.entity_name]?.deleted?.includes(String(record.id)) || false}
                                  onChange={() => handleToggleChange(entity.entity_name, 'deleted', String(record.id))}
                                  className="mt-0.5"
                                />
                                <div className="flex-1">
                                  <span className="font-medium text-red-600">DELETE:</span> {record.id}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          }
          confirmLabel="Apply Selected Changes"
          variant="default"
          onConfirm={handleApplySync}
          onCancel={() => {
            setShowSyncPreviewModal(false);
            setSyncPreview(null);
            setSelectedChanges({});
          }}
          disabled={isPreviewLoading}
        />
      )}
      {showResetConfirmModal && (
        <ConfirmModal
          title="Reset Database"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600 font-medium text-red-700">WARNING: This will delete selected local data and replace it with data from the remote database.</p>
              <p className="text-sm text-gray-600">This action cannot be undone. All local changes will be lost.</p>
              <div className="border-t pt-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-medium text-gray-700">Select entities to reset:</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedResetEntities(resetEntities.map(e => e.id))}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Select All
                    </button>
                    <button
                      onClick={() => setSelectedResetEntities([])}
                      className="text-xs text-red-600 hover:text-red-800"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto">
                  {resetEntities.map((entity) => (
                    <div key={entity.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded">
                      <input
                        type="checkbox"
                        id={`reset-${entity.id}`}
                        checked={selectedResetEntities.includes(entity.id)}
                        onChange={() => handleToggleResetEntity(entity.id)}
                        className="rounded border-gray-300"
                      />
                      <label htmlFor={`reset-${entity.id}`} className="text-sm text-gray-700 cursor-pointer">
                        {entity.label}
                      </label>
                    </div>
                  ))}
                </div>
                {selectedResetEntities.length === 0 && (
                  <p className="text-xs text-yellow-600 mt-2">No entities selected - all entities will be reset</p>
                )}
              </div>
            </div>
          }
          confirmLabel="Reset Database"
          variant="danger"
          onConfirm={handleReset}
          onCancel={() => {
            setShowResetConfirmModal(false);
            setSelectedResetEntities([]);
          }}
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
      {showBackupSuccessModal && (
        <ConfirmModal
          title="Backup Successful"
          message={
            <div className="space-y-2">
              <p className="text-sm text-gray-600">Database backup created and downloaded successfully.</p>
            </div>
          }
          confirmLabel="Close"
          variant="default"
          onConfirm={() => setShowBackupSuccessModal(false)}
          onCancel={() => setShowBackupSuccessModal(false)}
        />
      )}
      {showAlembicModal && (
        <ConfirmModal
          title="Alembic Migration Management"
          message={
            <div className="space-y-4">
              {loadingAlembic ? (
                <p className="text-sm text-gray-600">Loading alembic status...</p>
              ) : alembicStatus ? (
                <div className="space-y-3">
                  <div className={`p-3 rounded-md ${alembicStatus.multiple_heads ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
                    <p className="text-sm font-medium mb-2">
                      {alembicStatus.multiple_heads ? 'Multiple Heads Detected' : 'Single Head (OK)'}
                    </p>
                    <p className="text-xs text-gray-600 mb-1">Current Versions:</p>
                    <ul className="text-xs text-gray-700 list-disc list-inside">
                      {alembicStatus.current_versions.map((v: string) => <li key={v}>{v}</li>)}
                    </ul>
                  </div>
                  {alembicStatus.multiple_heads && (
                    <div>
                      <p className="text-sm font-medium text-gray-700 mb-2">Fix Multiple Heads</p>
                      <p className="text-xs text-gray-500 mb-2">Select the target version to set as the single head:</p>
                      <select
                        value={targetVersion}
                        onChange={(e) => setTargetVersion(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                      >
                        {alembicStatus.current_versions.map((v: string) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                      <button
                        onClick={handleFixAlembicHeads}
                        className="mt-3 w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
                      >
                        Fix Heads
                      </button>
                    </div>
                  )}
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-sm font-medium text-gray-700 mb-2">Run Pending Migrations</p>
                    <p className="text-xs text-gray-500 mb-2">This will run all pending alembic migrations to update the database schema:</p>
                    <button
                      onClick={handleRunMigration}
                      className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                    >
                      Run Migrations
                    </button>
                  </div>
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-sm font-medium text-gray-700 mb-2">Execute Custom SQL</p>
                    <p className="text-xs text-gray-500 mb-2">For manual schema fixes (dangerous - use with caution):</p>
                    <textarea
                      value={sqlQuery}
                      onChange={(e) => setSqlQuery(e.target.value)}
                      placeholder="ALTER TABLE materials ADD COLUMN fabric_composition_ids JSONB;"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-mono"
                      rows={3}
                    />
                    <button
                      onClick={handleExecuteSql}
                      className="mt-2 w-full px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 text-sm"
                    >
                      Execute SQL
                    </button>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Available Migration Files:</p>
                    <ul className="text-xs text-gray-600 list-disc list-inside max-h-40 overflow-y-auto">
                      {alembicStatus.migration_files.map((f: string) => <li key={f}>{f}</li>)}
                    </ul>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-600">No alembic status available</p>
              )}
            </div>
          }
          confirmLabel="Close"
          variant="default"
          onConfirm={() => {
            setShowAlembicModal(false);
            setAlembicStatus(null);
            setTargetVersion('');
          }}
          onCancel={() => {
            setShowAlembicModal(false);
            setAlembicStatus(null);
            setTargetVersion('');
          }}
        />
      )}
    </div>
  );
}
