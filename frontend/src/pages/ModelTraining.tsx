import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ConfirmModal } from '../components/ConfirmModal';

export function ModelTraining() {
  const { role } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<any>(null);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [modelVersions, setModelVersions] = useState<any[]>([]);
  const [modelName, setModelName] = useState<string>('');
  const [trainingWarnings, setTrainingWarnings] = useState<string[]>([]);
  const [deleteVersion, setDeleteVersion] = useState<string | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editVersion, setEditVersion] = useState<string | null>(null);
  const [editName, setEditName] = useState<string>('');
  const [showEditModal, setShowEditModal] = useState(false);

  const handleTrain = async () => {
    setLoading(true);
    setError(null);
    setTrainingStatus(null);
    setTrainingWarnings([]);

    try {
      const url = modelName ? `/api/v1/ballistic/train?model_name=${encodeURIComponent(modelName)}` : '/api/v1/ballistic/train';
      const result = await apiClient.post<any>(url);
      setTrainingStatus(result);
      setTrainingWarnings(result.warnings || []);
      setShowSuccessModal(true);
      setModelName(''); // Clear model name after training
      handleListVersions(); // Refresh versions after training
    } catch (err: any) {
      setError(err.detail || 'Training failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckHealthForVersion = async (version: string) => {
  try {
    const result = await apiClient.get<any>(`/api/v1/ballistic/health/version/${version}`);
    setHealthStatus(result);
  } catch (err: any) {
    setError(err.detail || 'Health check failed');
  }
};

  const handleGetMetrics = async () => {
    try {
      const result = await apiClient.get<any>('/api/v1/ballistic/metrics');
      setTrainingStatus(result);
    } catch (err: any) {
      setError(err.detail || 'Failed to fetch metrics');
    }
  };

  const handleListVersions = async () => {
    try {
      const result = await apiClient.get<any>('/api/v1/ballistic/versions');
      setModelVersions(result.versions || []);
    } catch (err: any) {
      setError(err.detail || 'Failed to fetch versions');
    }
  };

  const handleDeleteClick = (version: string) => {
    setDeleteVersion(version);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteVersion) return;

    console.log('Deleting version:', deleteVersion);
    console.log('Full version object:', modelVersions.find(v => v.version === deleteVersion));

    try {
      await apiClient.delete<any>(`/api/v1/ballistic/versions/${deleteVersion}`);
      setShowDeleteModal(false);
      setDeleteVersion(null);
      handleListVersions(); // Refresh versions list
    } catch (err: any) {
      setError(err.detail || 'Failed to delete version');
    }
  };

  const handleEditClick = (version: string, currentName: string) => {
    setEditVersion(version);
    setEditName(currentName);
    setShowEditModal(true);
  };

  const handleEditConfirm = async () => {
    if (!editVersion || !editName.trim()) return;

    try {
      await apiClient.put<any>(`/api/v1/ballistic/versions/${editVersion}/name?new_name=${encodeURIComponent(editName)}`);
      setShowEditModal(false);
      setEditVersion(null);
      setEditName('');
      handleListVersions(); // Refresh versions list
    } catch (err: any) {
      setError(err.detail || 'Failed to update model name');
    }
  };

  // Load versions on mount
  useEffect(() => {
    handleListVersions();
  }, []);

  if (role !== 'admin') {
    return (
      <div className="p-6">
        <h1 className="text-3xl font-bold mb-6">Model Training</h1>
        <div className="bg-red-50 border border-red-200 rounded p-4">
          <p className="text-red-800">Access denied. Admin only.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Model Training</h1>

      <div className="space-y-6">
        {/* Controls */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Model Controls</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">Model Name (Optional)</label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="e.g., March 2025 1.1"
                className="w-full border rounded p-2"
              />
            </div>
            <button
              onClick={handleTrain}
              disabled={loading}
              className="w-full bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 disabled:bg-gray-400"
            >
              {loading ? 'Training...' : 'Train Model (From Database)'}
            </button>
                      </div>
        </div>

        {/* Health Status */}
        {healthStatus && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Model Health</h2>
            <div className="space-y-2">
              <div><strong>Status:</strong> {healthStatus.status}</div>
              <div><strong>Version:</strong> {healthStatus.version || 'N/A'}</div>
              <div><strong>Trained At:</strong> {healthStatus.trained_at || 'N/A'}</div>
              <div><strong>Regression Targets:</strong> {healthStatus.regression_targets?.join(', ') || 'None'}</div>
              <div><strong>Classification Targets:</strong> {healthStatus.classification_targets?.join(', ') || 'None'}</div>
              <div><strong>Feature Count:</strong> {healthStatus.feature_count}</div>
              <div><strong>Material Count:</strong> {healthStatus.material_count}</div>
              <div className="border-t pt-2 mt-2">
                <div className="font-semibold mb-2">Database Counts:</div>
                <div><strong>Shots:</strong> {healthStatus.shot_count}</div>
                <div><strong>Vests:</strong> {healthStatus.vest_count}</div>
                <div><strong>Vest Layers:</strong> {healthStatus.vest_layer_count}</div>
              </div>
              {healthStatus.data_health && (
                <div className="border-t pt-2 mt-2">
                  <div className="font-semibold mb-2">Data Health Statistics:</div>
                  <div className="text-sm space-y-1">
                    <div><strong>Total Data Points:</strong> {healthStatus.data_health.total_data_points}</div>
                    {healthStatus.data_health.material_distribution && (
                      <div>
                        <strong>Material Distribution:</strong>
                        <div className="ml-4 text-xs">
                          {Object.entries(healthStatus.data_health.material_distribution).map(([material, count]) => (
                            <div key={material}>{material}: {count}</div>
                          ))}
                        </div>
                      </div>
                    )}
                    {healthStatus.data_health.ammunition_distribution && (
                      <div>
                        <strong>Ammunition Distribution:</strong>
                        <div className="ml-4 text-xs">
                          {Object.entries(healthStatus.data_health.ammunition_distribution).map(([ammo, count]) => (
                            <div key={ammo}>{ammo}: {count}</div>
                          ))}
                        </div>
                      </div>
                    )}
                    {healthStatus.data_health.protection_level_distribution && (
                      <div>
                        <strong>Protection Level Distribution:</strong>
                        <div className="ml-4 text-xs">
                          {Object.entries(healthStatus.data_health.protection_level_distribution).map(([level, count]) => (
                            <div key={level}>{level}: {count}</div>
                          ))}
                        </div>
                      </div>
                    )}
                    {healthStatus.data_health.velocity_stats && (
                      <div>
                        <strong>Velocity Stats:</strong>
                        <div className="ml-4 text-xs">
                          Min: {healthStatus.data_health.velocity_stats.min?.toFixed(1)} m/s, 
                          Max: {healthStatus.data_health.velocity_stats.max?.toFixed(1)} m/s, 
                          Mean: {healthStatus.data_health.velocity_stats.mean?.toFixed(1)} m/s
                        </div>
                      </div>
                    )}
                    {healthStatus.data_health.bfd_stats && (
                      <div>
                        <strong>BFD Stats:</strong>
                        <div className="ml-4 text-xs">
                          Min: {healthStatus.data_health.bfd_stats.min?.toFixed(1)} mm, 
                          Max: {healthStatus.data_health.bfd_stats.max?.toFixed(1)} mm, 
                          Mean: {healthStatus.data_health.bfd_stats.mean?.toFixed(1)} mm
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Model Versions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Model Versions</h2>
          {modelVersions.length === 0 ? (
            <p className="text-sm text-gray-600">No model versions available. Train a model to create the first version.</p>
          ) : (
            <div className="space-y-2">
              {modelVersions.map((version) => (
                <div key={version.version} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                  <div>
                    <div className="font-medium">{version.model_name || version.version}</div>
                    <div className="text-xs text-gray-600">{new Date(version.trained_at).toLocaleString()}</div>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleCheckHealthForVersion(version.version)}
                      className="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                    >
                      Health
                    </button>
                    <button
                      onClick={() => handleEditClick(version.version, version.model_name || version.version)}
                      className="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteClick(version.version)}
                      className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Training Status/Metrics */}
        {trainingStatus && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Training Status</h2>

            {/* Warnings */}
            {trainingWarnings.length > 0 && (
              <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded p-4">
                <h3 className="font-semibold text-yellow-800 mb-2">Warnings</h3>
                <ul className="text-sm text-yellow-700 list-disc list-inside">
                  {trainingWarnings.map((warning, index) => (
                    <li key={index}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            <pre className="text-xs overflow-auto bg-gray-100 p-4 rounded">
              {JSON.stringify(trainingStatus, null, 2)}
            </pre>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <h3 className="font-semibold text-red-800 mb-2">Error</h3>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
      </div>

      {/* Success Modal */}
      {showSuccessModal && (
        <ConfirmModal
          title="Training Complete"
          message="The ML model has been trained successfully using data from the database."
          confirmLabel="OK"
          onConfirm={() => setShowSuccessModal(false)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <ConfirmModal
          title="Delete Model"
          message={`Are you sure you want to delete model version "${deleteVersion}"? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => {
            setShowDeleteModal(false);
            setDeleteVersion(null);
          }}
        />
      )}

      {/* Edit Name Modal */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowEditModal(false)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Edit Model Name</h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Name</label>
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full border rounded p-2"
                autoFocus
              />
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setShowEditModal(false);
                  setEditVersion(null);
                  setEditName('');
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleEditConfirm}
                disabled={!editName.trim()}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
