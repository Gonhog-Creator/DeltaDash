import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ConfirmModal } from '../components/ConfirmModal';
import { AnchorPointsTab } from '../components/AnchorPointsTab';
import Plot from 'react-plotly.js';

const API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://deltadash-backend-production.up.railway.app';

interface ProtocolThreatLevel {
  protocol_id: string;
  protocol_name: string;
  threat_levels: string[];
}

export function ModelTraining() {
  const { role } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  
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
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  
  // Model Health state - initialize from URL query param
  const searchParams = new URLSearchParams(location.search);
  const tabParam = searchParams.get('tab');
  const [activeTab, setActiveTab] = useState<'training' | 'health'>(tabParam === 'health' ? 'health' : 'training');
  const [selectedModelVersion, setSelectedModelVersion] = useState<string>('');
  const [selectedProtocol, setSelectedProtocol] = useState<string>('all');
  const [selectedVests, setSelectedVests] = useState<string[]>([]);
  const [selectedProtectionLevels, setSelectedProtectionLevels] = useState<string[]>([]);
  const [selectedCalibers, setSelectedCalibers] = useState<string[]>([]);
  const [colorGrouping, setColorGrouping] = useState<'vest' | 'protocol' | 'protection_level' | 'caliber' | 'none'>('none');
  const [healthData, setHealthData] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [showHealthSection, setShowHealthSection] = useState(true);
  const [protocols, setProtocols] = useState<string[]>([]);
  const [calculatingMetrics, setCalculatingMetrics] = useState(false);
  const [calculatingVersion, setCalculatingVersion] = useState<string | null>(null);
  const [showAnchorPointDetails, setShowAnchorPointDetails] = useState(false);
  const [showHealthModal, setShowHealthModal] = useState(false);
  const [protocolThreatLevels, setProtocolThreatLevels] = useState<ProtocolThreatLevel[]>([]);
  const [healthCheckStatus, setHealthCheckStatus] = useState<any>(null);
  const [useLogTransform, setUseLogTransform] = useState(true);
  
  // Mass delete state
  const [selectedVersions, setSelectedVersions] = useState<Set<string>>(new Set());
  const [showMassDeleteModal, setShowMassDeleteModal] = useState(false);
  const [isDeletingSelected, setIsDeletingSelected] = useState(false);

  // Advanced Training Controls
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ignoreAnchorPoints, setIgnoreAnchorPoints] = useState(false);
  const [hyperparameters, setHyperparameters] = useState({
    n_estimators: 800,
    max_depth: 6,
    learning_rate: 0.05,
    subsample: 0.9,
    colsample_bytree: 0.9,
    min_child_weight: 2,
    reg_lambda: 1.0,
    reg_alpha: 0.1,
    gamma: 0.0,
  });
  const [featureToggles, setFeatureToggles] = useState({
    // High impact - keep enabled
    shot_sequence: true,
    velocity_interactions: true,
    vest_type_interactions: true,
    is_female_features: true,
    // Low/negative impact - disable by default (can re-enable manually)
    kinetic_energy: false,
    composite_thickness: false,
    layer_density: false,
    caliber_features: false,
    areal_density: false,
    vest_composition: false,
    material_density: false,
  });

  // Custom Vest Prediction State
  const [useCustomVest, setUseCustomVest] = useState(false);
  const [customVest, setCustomVest] = useState({
    vest_type: 'soft',
    is_female: false,
    total_layers: 20,
    total_thickness_mm: 12.0,
    material_areal_density_g_m2: 250.0,
    panel_protects_front: true,
    panel_protects_back: true,
    panel_protects_sides: false,
  });

  // Feature Analysis state
  const [featureAnalysisLoading, setFeatureAnalysisLoading] = useState(false);
  const [featureAnalysisResults, setFeatureAnalysisResults] = useState<any>(null);
  const [showFeatureAnalysisResults, setShowFeatureAnalysisResults] = useState(false);

  // Hyperparameter Optimization state
  const [optimizationLoading, setOptimizationLoading] = useState(false);
  const [optimizationResults, setOptimizationResults] = useState<any>(null);
  const [showOptimizationResults, setShowOptimizationResults] = useState(false);
  const [showOptimizationModal, setShowOptimizationModal] = useState(false);
  const [trialResults, setTrialResults] = useState<Array<{trial: number, error: number}>>([]);

  // Fetch protocol threat levels on mount
  useEffect(() => {
    const fetchProtocolThreatLevels = async () => {
      try {
        const data = await apiClient.get<ProtocolThreatLevel[]>('/api/v1/protocols/threat-levels/grouped');
        setProtocolThreatLevels(data);
      } catch (err) {
        console.error('Failed to fetch protocol threat levels:', err);
      }
    };
    fetchProtocolThreatLevels();
  }, []);

  const handleTrain = async () => {
    setLoading(true);
    setError(null);
    setTrainingStatus(null);
    setTrainingWarnings([]);

    try {
      // Build request body with all training parameters
      const requestBody: any = {
        model_name: modelName || undefined,
        use_log_transform: useLogTransform,
        hyperparameters: hyperparameters,
        feature_toggles: featureToggles,
        ignore_anchor_points: ignoreAnchorPoints,
      };

      const result = await apiClient.post<any>('/api/v1/ballistic/train', requestBody);
      setTrainingStatus(result);
      setTrainingWarnings(result.warnings || []);
      setHealthCheckStatus(result.health_check);

      // Use cached health check results from training response
      if (result.metadata?.version) {
        setSelectedModelVersion(result.metadata.version);

        // Use health results already computed during training
        if (result.health_result) {
          setHealthData(result.health_result);
        }
      }

      setShowSuccessModal(true);
      setModelName(''); // Clear model name after training
      // Wait a moment for database transaction to commit before refreshing
      await new Promise(resolve => setTimeout(resolve, 500));
      handleListVersions(); // Refresh versions after training
    } catch (err: any) {
      // Network errors (e.g. proxy timeout) don't have .detail — the model may have saved
      if (!err.detail && (err.message === 'Failed to fetch' || err.name === 'TypeError')) {
        setError('Training request timed out, but the model may have been saved. Refreshing...');
        await new Promise(resolve => setTimeout(resolve, 2000));
        handleListVersions();
      } else {
        setError(err.detail || 'Training failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeFeatures = async () => {
    setFeatureAnalysisLoading(true);
    setError(null);
    try {
      const requestBody = {
        use_log_transform: useLogTransform,
        hyperparameters: hyperparameters,
      };
      const result = await apiClient.post<any>('/api/v1/ballistic/analyze-features', requestBody);
      setFeatureAnalysisResults(result);
      setShowFeatureAnalysisResults(true);
    } catch (err: any) {
      setError(err.detail || 'Feature analysis failed');
    } finally {
      setFeatureAnalysisLoading(false);
    }
  };

  const handleOptimizeHyperparameters = async () => {
    setOptimizationLoading(true);
    setShowOptimizationModal(true);
    setTrialResults([]);
    setError(null);
    try {
      const requestBody = {
        use_log_transform: useLogTransform,
        feature_toggles: featureToggles,
        ignore_anchor_points: ignoreAnchorPoints,
      };

      // Start polling for status
      const interval = setInterval(async () => {
        try {
          const status = await apiClient.get<any>('/api/v1/ballistic/optimization-status');
          if (status.trial_results) {
            setTrialResults(status.trial_results);
          }
          // Stop polling if optimization is no longer running
          if (!status.running) {
            clearInterval(interval);
          }
        } catch (err) {
          console.error('Failed to fetch optimization status:', err);
        }
      }, 1000);

      const result = await apiClient.post<any>('/api/v1/ballistic/optimize-hyperparameters', requestBody);
      setOptimizationResults(result);
      setShowOptimizationResults(true);

      // Auto-apply the best parameters
      if (result.best_hyperparameters) {
        setHyperparameters(result.best_hyperparameters);
      }

      clearInterval(interval);
    } catch (err: any) {
      setError(err.detail || 'Hyperparameter optimization failed');
    } finally {
      setOptimizationLoading(false);
      setShowOptimizationModal(false);
    }
  };

  const handleStopOptimization = async () => {
    try {
      await apiClient.post<any>('/api/v1/ballistic/stop-optimization');
      setShowOptimizationModal(false);
    } catch (err) {
      console.error('Failed to stop optimization:', err);
    }
  };

  const handleCheckHealthForVersion = async (version: string) => {
    setError(null);
    try {
      const result = await apiClient.get<any>(`/api/v1/ballistic/health/version/${version}`);
      setHealthStatus(result);
      setShowHealthModal(true);
      setShowHealthSection(false); // Hide the health status section when showing modal
    } catch (err: any) {
      setError(err.detail || 'Failed to load model details');
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
      const result = await apiClient.get<any>('/api/v1/ballistic/versions-with-metrics');
      setModelVersions(result.versions || []);
    } catch (err: any) {
      setError(err.detail || 'Failed to fetch versions');
    }
  };

  const handleCalculateMissingMetrics = async () => {
    setCalculatingMetrics(true);
    setError(null);
    try {
      const result = await apiClient.post<any>('/api/v1/ballistic/calculate-missing-metrics');
      await handleListVersions(); // Refresh versions list
      // Show success message with details
      if (result.updated_count > 0) {
        setError(`Recalculated metrics for ${result.updated_count} model versions`);
      } else {
        setError('No models found to recalculate');
      }
    } catch (err: any) {
      setError(err.detail || 'Failed to recalculate metrics');
    } finally {
      setCalculatingMetrics(false);
    }
  };

  const handleRecalculateVersionMetrics = async (version: string) => {
    setCalculatingVersion(version);
    setError(null);
    try {
      await apiClient.post<any>(`/api/v1/ballistic/recalculate-metrics/${version}`);
      await handleListVersions(); // Refresh versions list
      setError(`Recalculated metrics for version ${version}`);
    } catch (err: any) {
      setError(err.detail || `Failed to recalculate metrics for version ${version}`);
    } finally {
      setCalculatingVersion(null);
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

  const handleToggleVersionSelection = (version: string) => {
    setSelectedVersions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(version)) {
        newSet.delete(version);
      } else {
        newSet.add(version);
      }
      return newSet;
    });
  };

  const handleSelectAllVersions = () => {
    if (selectedVersions.size === modelVersions.length) {
      setSelectedVersions(new Set());
    } else {
      setSelectedVersions(new Set(modelVersions.map(v => v.version)));
    }
  };

  const handleMassDeleteConfirm = async () => {
    setIsDeletingSelected(true);
    setError(null);
    try {
      const deletePromises = Array.from(selectedVersions).map(version => 
        apiClient.delete<any>(`/api/v1/ballistic/versions/${version}`)
      );
      await Promise.all(deletePromises);
      setShowMassDeleteModal(false);
      setSelectedVersions(new Set());
      handleListVersions(); // Refresh versions list
      setError(`Deleted ${selectedVersions.size} model versions`);
    } catch (err: any) {
      setError(err.detail || 'Failed to delete selected versions');
    } finally {
      setIsDeletingSelected(false);
    }
  };

  const handleDownloadModel = async () => {
    if (!editVersion) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/ballistic/versions/${editVersion}/download`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `ballistic_model_${editVersion}.zip`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?(.+?)"?(;|$)/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(err.message || 'Failed to download model');
    }
  };

  const handleUploadModel = async () => {
    if (!uploadFile) return;

    setUploadLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);

      const response = await fetch(`${API_BASE_URL}/api/v1/ballistic/versions/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      setShowUploadModal(false);
      setUploadFile(null);
      handleListVersions(); // Refresh versions list
    } catch (err: any) {
      setError(err.message || 'Failed to upload model');
    } finally {
      setUploadLoading(false);
    }
  };

  // Load versions on mount
  useEffect(() => {
    handleListVersions();
  }, []);

  // Set default model version to most recent, or clear if selected version no longer exists
  useEffect(() => {
    if (modelVersions.length > 0) {
      // If selected version no longer exists in the list, clear it or select first available
      if (selectedModelVersion && !modelVersions.find(v => v.version === selectedModelVersion)) {
        setSelectedModelVersion(modelVersions[0].version);
      }
      // If no version is selected, select the first one
      else if (!selectedModelVersion) {
        setSelectedModelVersion(modelVersions[0].version);
      }
    } else {
      // If no versions exist, clear selection
      setSelectedModelVersion('');
    }
  }, [modelVersions, selectedModelVersion]);

  // Update URL when tab changes
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (activeTab === 'health') {
      params.set('tab', 'health');
    } else if (activeTab === 'anchor') {
      params.set('tab', 'anchor');
    } else {
      params.delete('tab');
    }
    navigate({ search: params.toString() }, { replace: true });
  }, [activeTab, navigate, location.search]);

  // Fetch protocols
  useEffect(() => {
    const fetchProtocols = async () => {
      try {
        const result = await apiClient.get<any>('/api/v1/test-sessions/protocols');
        setProtocols(result.protocols || []);
      } catch (err) {
        console.error('Failed to fetch protocols:', err);
      }
    };
    fetchProtocols();
  }, []);

  // Handle ESC key to close modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showEditModal) {
          setShowEditModal(false);
          setEditVersion(null);
          setEditName('');
        } else if (showUploadModal) {
          setShowUploadModal(false);
          setUploadFile(null);
        } else if (showDeleteModal) {
          setShowDeleteModal(false);
          setDeleteVersion(null);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showEditModal, showUploadModal, showDeleteModal]);

  // Clear cached health data on logout
  useEffect(() => {
    if (!role || role !== 'admin') {
      localStorage.removeItem('modelHealthData');
    }
  }, [role]);

  
  const handleFetchHealthData = async () => {
    setHealthLoading(true);
    setError(null);
    try {
      const url = selectedProtocol && selectedProtocol !== 'all' 
        ? `/api/v1/ballistic/model-health?version=${selectedModelVersion}&protocol=${selectedProtocol}`
        : `/api/v1/ballistic/model-health?version=${selectedModelVersion}`;
      const result = await apiClient.get<any>(url);
      setHealthData(result);
    } catch (err: any) {
      setError(err.detail || 'Failed to fetch model health data');
    } finally {
      setHealthLoading(false);
    }
  };

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

  const renderTrainingTab = () => (
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
          {/* Advanced Toggle Button */}
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
            >
              {showAdvanced ? 'Hide Advanced' : 'Advanced'} {showAdvanced ? '▲' : '▼'}
            </button>
          </div>

          {/* Advanced Section */}
          {showAdvanced && (
            <div className="border border-gray-200 rounded p-4 space-y-4 bg-gray-50">
              <h3 className="font-medium text-gray-700">Advanced Training Options</h3>

              {/* Log Transform */}
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="use_log_transform"
                  checked={useLogTransform}
                  onChange={(e) => setUseLogTransform(e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="use_log_transform" className="text-sm font-medium">
                  Use Log Transform for BFD
                </label>
              </div>

              {/* Ignore Anchor Points */}
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="ignore_anchor_points"
                  checked={ignoreAnchorPoints}
                  onChange={(e) => setIgnoreAnchorPoints(e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="ignore_anchor_points" className="text-sm font-medium">
                  Ignore Anchor Points (do not include in training)
                </label>
              </div>

              {/* Hyperparameters */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-600">XGBoost Hyperparameters</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-600">Trees (n_estimators)</label>
                    <input
                      type="number"
                      min={10}
                      max={10000}
                      value={hyperparameters.n_estimators}
                      onChange={(e) => setHyperparameters({...hyperparameters, n_estimators: parseInt(e.target.value)})}
                      className="w-full border rounded p-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600">Max Depth</label>
                    <input
                      type="number"
                      min={1}
                      max={30}
                      value={hyperparameters.max_depth}
                      onChange={(e) => setHyperparameters({...hyperparameters, max_depth: parseInt(e.target.value)})}
                      className="w-full border rounded p-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600">Learning Rate</label>
                    <input
                      type="number"
                      step={0.0001}
                      min={0.0001}
                      max={2.0}
                      value={hyperparameters.learning_rate}
                      onChange={(e) => setHyperparameters({...hyperparameters, learning_rate: parseFloat(e.target.value)})}
                      className="w-full border rounded p-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600">L2 Regularization (lambda)</label>
                    <input
                      type="number"
                      step={0.1}
                      min={0}
                      max={100}
                      value={hyperparameters.reg_lambda}
                      onChange={(e) => setHyperparameters({...hyperparameters, reg_lambda: parseFloat(e.target.value)})}
                      className="w-full border rounded p-1 text-sm"
                    />
                  </div>
                </div>
              </div>

              {/* Feature Toggles */}
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-gray-600">Feature Groups</h4>
                <div className="grid grid-cols-4 gap-3">
                  {Object.entries(featureToggles).map(([key, value]) => {
                    const featureInfo: Record<string, { name: string; formula: string }> = {
                      kinetic_energy: { name: 'Kinetic Energy', formula: '0.5 × mass × velocity²' },
                      composite_thickness: { name: 'Composite Thickness', formula: 'layer1×t1 + layer2×t2...' },
                      layer_density: { name: 'Layer Density', formula: 'total_layers / area' },
                      caliber_features: { name: 'Caliber Features', formula: 'diameter, length, area' },
                      areal_density: { name: 'Areal Density', formula: 'weight_g / 1000 / area' },
                      vest_composition: { name: 'Vest Composition', formula: 'material counts + sequence' },
                      vest_type_interactions: { name: 'Vest Type Interactions', formula: 'hard/soft × energy, thickness' },
                      is_female_features: { name: 'Female Vest Features', formula: 'is_female × panel, energy' },
                      shot_sequence: { name: 'Shot Sequence Effects', formula: 'is_first_shot, shot/layers' },
                      material_density: { name: 'Material Density', formula: 'areal_density / thickness' },
                      velocity_interactions: { name: 'Velocity Interactions', formula: 'velocity × layers, obliquity' },
                    };
                    const info = featureInfo[key] || { name: key, formula: '' };
                    return (
                      <label key={key} className="flex flex-col space-y-1 p-2 border border-gray-200 rounded cursor-pointer hover:bg-gray-50">
                        <div className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={value}
                            onChange={(e) => setFeatureToggles({...featureToggles, [key]: e.target.checked})}
                            className="rounded"
                          />
                          <span className="text-sm font-medium text-gray-700">{info.name}</span>
                        </div>
                        <span className="text-xs text-gray-500 font-mono pl-5">{info.formula}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Feature Analysis Button */}
              <div className="border-t border-gray-200 pt-4">
                <button
                  onClick={handleAnalyzeFeatures}
                  disabled={featureAnalysisLoading}
                  className="w-full bg-indigo-600 text-white py-2 px-4 rounded hover:bg-indigo-700 disabled:bg-gray-400"
                >
                  {featureAnalysisLoading ? 'Analyzing Features (trains 12 models)...' : 'Run Feature Importance Analysis'}
                </button>
                <p className="text-xs text-gray-500 mt-1">
                  Trains model with all features, then without each feature group. Higher MAE impact = more important feature.
                </p>
              </div>

              {/* Hyperparameter Optimization Button */}
              <div className="border-t border-gray-200 pt-4">
                <button
                  onClick={handleOptimizeHyperparameters}
                  disabled={optimizationLoading}
                  className="w-full bg-purple-600 text-white py-2 px-4 rounded hover:bg-purple-700 disabled:bg-gray-400"
                >
                  {optimizationLoading ? 'Optimizing Hyperparameters (trains 50 models)...' : 'Optimize Hyperparameters'}
                </button>
                <p className="text-xs text-gray-500 mt-1">
                  Uses Bayesian optimization to find best hyperparameters. Runs 50 trials and auto-applies the best parameters.
                </p>
              </div>
            </div>
          )}

          {/* Feature Analysis Results */}
          {featureAnalysisResults && showFeatureAnalysisResults && (
            <div className="border border-indigo-200 rounded p-4 bg-indigo-50">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <h4 className="font-semibold text-indigo-800">Feature Importance Results</h4>
                  <div className="group relative cursor-help">
                    <span className="text-indigo-400 hover:text-indigo-600">?</span>
                    <div className="absolute left-0 top-6 w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity z-10">
                      <p className="mb-1"><strong>Impact</strong> shows how much MAE changed when this feature was removed:</p>
                      <ul className="list-disc pl-4 space-y-1">
                        <li><span className="text-green-400">Green (positive)</span>: Feature helps reduce error - keep enabled</li>
                        <li><span className="text-red-400">Red (zero/negative)</span>: Feature doesn't help - consider disabling</li>
                      </ul>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setShowFeatureAnalysisResults(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              <div className="text-sm mb-2">
                <span className="font-medium">Baseline MAE: </span>
                <span className="font-mono">{featureAnalysisResults.baseline?.mae?.toFixed(4) || 'N/A'} mm</span>
              </div>
              <div className="space-y-1">
                {featureAnalysisResults.ranked_by_importance?.map((feature: string, idx: number) => {
                  const data = featureAnalysisResults.ablation[feature];
                  const impact = data?.mae_impact;
                  const displayNames: Record<string, string> = {
                    kinetic_energy: 'Kinetic Energy',
                    composite_thickness: 'Composite Thickness',
                    layer_density: 'Layer Density',
                    caliber_features: 'Caliber Features',
                    areal_density: 'Areal Density',
                    vest_composition: 'Vest Composition',
                    vest_type_interactions: 'Vest Type Interactions',
                    is_female_features: 'Female Vest Features',
                    shot_sequence: 'Shot Sequence Effects',
                    material_density: 'Material Density',
                    velocity_interactions: 'Velocity Interactions',
                  };
                  return (
                    <div key={feature} className="flex items-center justify-between text-sm py-1 border-b border-indigo-100 last:border-0">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium text-indigo-600 w-6">#{idx + 1}</span>
                        <span>{displayNames[feature] || feature}</span>
                      </div>
                      <div className="flex items-center space-x-4">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${featureToggles[feature] ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                          {featureToggles[feature] ? 'Active' : 'Inactive'}
                        </span>
                        <span className="text-gray-600">MAE: {data?.mae?.toFixed(4)}</span>
                        <span className={`font-mono font-medium ${impact > 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {impact > 0 ? '+' : ''}{impact?.toFixed(4)} mm
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Hyperparameter Optimization Results */}
          {optimizationResults && showOptimizationResults && (
            <div className="border border-purple-200 rounded p-4 bg-purple-50">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold text-purple-800">Hyperparameter Optimization Results</h4>
                <button
                  onClick={() => setShowOptimizationResults(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              <div className="text-sm mb-3">
                <span className="font-medium">Health Check Error: </span>
                <span className="font-mono">{optimizationResults.health_check_error?.toFixed(2) || 'N/A'}%</span>
                <span className="text-gray-600 ml-2">({optimizationResults.n_trials} trials)</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm mb-2">
                <div>
                  <span className="font-medium">Training MAE: </span>
                  <span className="font-mono">{optimizationResults.training_mae?.toFixed(4) || 'N/A'} mm</span>
                </div>
                <div>
                  <span className="font-medium">R²: </span>
                  <span className="font-mono">{optimizationResults.r2_score?.toFixed(4) || 'N/A'}</span>
                </div>
                <div>
                  <span className="font-medium">RMSE: </span>
                  <span className="font-mono">{optimizationResults.rmse?.toFixed(4) || 'N/A'} mm</span>
                </div>
              </div>
              <div className="text-xs text-gray-600 mb-2">
                Best parameters have been auto-applied to the hyperparameter inputs above.
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="font-medium">Trees:</span> {optimizationResults.best_hyperparameters?.n_estimators}</div>
                <div><span className="font-medium">Max Depth:</span> {optimizationResults.best_hyperparameters?.max_depth}</div>
                <div><span className="font-medium">Learning Rate:</span> {optimizationResults.best_hyperparameters?.learning_rate?.toFixed(4)}</div>
                <div><span className="font-medium">Subsample:</span> {optimizationResults.best_hyperparameters?.subsample?.toFixed(2)}</div>
                <div><span className="font-medium">Colsample:</span> {optimizationResults.best_hyperparameters?.colsample_bytree?.toFixed(2)}</div>
                <div><span className="font-medium">Min Child Weight:</span> {optimizationResults.best_hyperparameters?.min_child_weight}</div>
                <div><span className="font-medium">L2 (lambda):</span> {optimizationResults.best_hyperparameters?.reg_lambda?.toFixed(2)}</div>
                <div><span className="font-medium">L1 (alpha):</span> {optimizationResults.best_hyperparameters?.reg_alpha?.toFixed(2)}</div>
                <div><span className="font-medium">Gamma:</span> {optimizationResults.best_hyperparameters?.gamma?.toFixed(2)}</div>
              </div>
            </div>
          )}

          <button
            onClick={handleTrain}
            disabled={loading}
            className="w-full bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 disabled:bg-gray-400"
          >
            {loading ? 'Processing (Training + Health Check)...' : 'Train Model (From Database)'}
          </button>
        </div>
      </div>

      {/* Health Status */}
      {healthStatus && showHealthSection && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Model Health</h2>
            <button
              onClick={() => setShowHealthSection(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>
          <div className="space-y-2">
            <div><strong>Model Name:</strong> {healthStatus.model_name || 'N/A'}</div>
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
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Model Versions</h2>
          <div className="flex space-x-2">
            {selectedVersions.size > 0 && (
              <button
                onClick={() => setShowMassDeleteModal(true)}
                className="px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700"
              >
                Delete Selected ({selectedVersions.size})
              </button>
            )}
            <button
              onClick={handleCalculateMissingMetrics}
              disabled={calculatingMetrics}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-400"
            >
              {calculatingMetrics ? 'Recalculating...' : 'Force Recalculate ALL Metrics'}
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="px-4 py-2 bg-green-600 text-white text-sm rounded hover:bg-green-700"
            >
              Upload Model
            </button>
          </div>
        </div>
        {modelVersions.length === 0 ? (
          <p className="text-sm text-gray-600">No model versions available. Train a model to create the first version.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    <input
                      type="checkbox"
                      checked={selectedVersions.size === modelVersions.length && modelVersions.length > 0}
                      onChange={handleSelectAllVersions}
                      className="rounded"
                    />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Version</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trained At</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Training Points</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Error</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {modelVersions.map((version) => (
                  <tr key={version.version}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <input
                        type="checkbox"
                        checked={selectedVersions.has(version.version)}
                        onChange={() => handleToggleVersionSelection(version.version)}
                        className="rounded"
                      />
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 max-w-xs break-words">
                      {version.model_name || version.version}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{version.version}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {new Date(version.trained_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {version.training_row_count !== null ? version.training_row_count : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {version.training_avg_error !== null ? `${version.training_avg_error.toFixed(2)}%` : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleCheckHealthForVersion(version.version)}
                          className="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                        >
                          Details
                        </button>
                        <button
                          onClick={() => handleRecalculateVersionMetrics(version.version)}
                          disabled={calculatingVersion === version.version}
                          className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-400"
                        >
                          {calculatingVersion === version.version ? 'Recalculating...' : 'Recalc Metrics'}
                        </button>
                        <button
                          onClick={() => handleEditClick(version.version, version.model_name || version.version)}
                          className="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700"
                        >
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
  );

  const renderHealthTab = (showAnchorPointDetails: boolean, setShowAnchorPointDetails: (value: boolean) => void) => {
    // Get unique vests from health data
    const uniqueVests = healthData?.vest_averages?.map((v: any) => v.vest_code) || [];
    
    // Get protection levels and calibers from point data (show all that exist)
    const uniqueProtectionLevels = Array.from(new Set(healthData?.point_data?.map((p: any) => p.protection_level).filter((v: any) => v) || []));
    const uniqueCalibers = Array.from(new Set(healthData?.point_data?.map((p: any) => p.caliber).filter((v: any) => v) || []));
    
    // Filter point data based on selected vests, protection levels, and calibers
    const filteredPointData = healthData?.point_data?.filter((p: any) => {
      if (selectedVests.length > 0 && !selectedVests.includes(p.vest_code)) {
        return false;
      }
      if (selectedProtectionLevels.length > 0 && !selectedProtectionLevels.includes(p.protection_level)) {
        return false;
      }
      if (selectedCalibers.length > 0 && !selectedCalibers.includes(p.caliber)) {
        return false;
      }
      return true;
    }) || [];
    
    return (
      <div className="space-y-6">
        {/* Filters for running health check */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Health Check Configuration</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Model Version</label>
              <select
                value={selectedModelVersion}
                onChange={(e) => setSelectedModelVersion(e.target.value)}
                className="w-full border rounded p-2"
                disabled={modelVersions.length === 0}
              >
                {modelVersions.map((version) => (
                  <option key={version.version} value={version.version}>
                    {version.model_name || version.version}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Protocol Filter</label>
              <select
                value={selectedProtocol}
                onChange={(e) => setSelectedProtocol(e.target.value)}
                className="w-full border rounded p-2"
              >
                <option value="all">All Protocols</option>
                {protocols.map((protocol) => (
                  <option key={protocol} value={protocol}>{protocol}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <button
              onClick={handleFetchHealthData}
              disabled={healthLoading || !selectedModelVersion}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400"
            >
              {healthLoading ? 'Running Health Check...' : 'Run Health Check'}
            </button>
          </div>
        </div>

      {healthLoading && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center space-x-3">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <div>
              <p className="text-gray-900 font-medium">Running Model Health Check...</p>
              <p className="text-sm text-gray-600">
                Evaluating model on test session data using {selectedProtocol === 'all' ? 'all protocols' : selectedProtocol} protocol
              </p>
              <p className="text-xs text-gray-500 mt-1">This may take a moment depending on the number of test points</p>
            </div>
          </div>
        </div>
      )}

      {healthData && !healthLoading && (
        <>
          {/* Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Summary</h2>
            <div className="grid grid-cols-2 gap-4">
              <div><strong>Model Version:</strong> {healthData.model_version}</div>
              <div><strong>Model Name:</strong> {healthData.model_name}</div>
              <div><strong>Total Test Points:</strong> {healthData.total_points}</div>
              <div><strong>Vests Evaluated:</strong> {healthData.vest_averages?.length || 0}</div>
              <div><strong>Overall Average Error:</strong> {healthData.overall_average_error}%</div>
            </div>
          </div>

          {/* Vest Averages Table */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Average % Error by Vest</h2>
            {healthData.vest_averages && healthData.vest_averages.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vest Code</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Average % Error</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Number of Points</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {healthData.vest_averages
                      .filter((vest: any) => selectedVests.length === 0 || selectedVests.includes(vest.vest_code))
                      .map((vest: any) => (
                        <tr key={vest.vest_code}>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{vest.vest_code}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{vest.average_percent_error}%</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{vest.num_points}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-600">No vest data available.</p>
            )}
          </div>

          {/* Anchor Point Error */}
          {healthData.anchor_point_count !== undefined && healthData.anchor_point_count > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Anchor Point Error</h2>
                {healthData.anchor_point_material_errors && healthData.anchor_point_material_errors.length > 0 && (
                  <button
                    onClick={() => setShowAnchorPointDetails(!showAnchorPointDetails)}
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                  >
                    {showAnchorPointDetails ? 'Hide Details' : 'Show Details'}
                  </button>
                )}
              </div>
              <div className="space-y-2">
                <div><strong>Anchor Points Evaluated:</strong> {healthData.anchor_point_count}</div>
                <div><strong>Anchor Point Average Error:</strong> {healthData.anchor_point_average_error}%</div>
              </div>
              {showAnchorPointDetails && healthData.anchor_point_material_errors && healthData.anchor_point_material_errors.length > 0 && (
                <div className="mt-4 border-t pt-4">
                  <h3 className="text-lg font-medium mb-3">Error by Material Composition</h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Material Composition</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Average % Error</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Count</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {healthData.anchor_point_material_errors.map((material: any, index: number) => (
                          <tr key={index}>
                            <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{material.composition}</td>
                            <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{material.average_error}%</td>
                            <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{material.count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Filtering Options */}
          {healthData && (uniqueVests.length > 0 || uniqueProtectionLevels.length > 0 || uniqueCalibers.length > 0) && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Filtering Options</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Vest Filter</label>
                  <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-2">
                    {uniqueVests.map(vest => (
                      <label key={vest} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={selectedVests.includes(vest)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedVests([...selectedVests, vest]);
                            } else {
                              setSelectedVests(selectedVests.filter(v => v !== vest));
                            }
                          }}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm text-gray-700">{vest}</span>
                      </label>
                    ))}
                  </div>
                  {selectedVests.length > 0 && (
                    <button
                      onClick={() => setSelectedVests([])}
                      className="mt-2 text-sm text-indigo-600 hover:text-indigo-800"
                    >
                      Clear vest filter
                    </button>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Protection Level Filter</label>
                  <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-2">
                    {uniqueProtectionLevels.map(level => (
                      <label key={level} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={selectedProtectionLevels.includes(level)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedProtectionLevels([...selectedProtectionLevels, level]);
                            } else {
                              setSelectedProtectionLevels(selectedProtectionLevels.filter(l => l !== level));
                            }
                          }}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm text-gray-700">{level}</span>
                      </label>
                    ))}
                  </div>
                  {selectedProtectionLevels.length > 0 && (
                    <button
                      onClick={() => setSelectedProtectionLevels([])}
                      className="mt-2 text-sm text-indigo-600 hover:text-indigo-800"
                    >
                      Clear protection level filter
                    </button>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Caliber Filter</label>
                  <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-2">
                    {uniqueCalibers.map(caliber => (
                      <label key={caliber} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          checked={selectedCalibers.includes(caliber)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedCalibers([...selectedCalibers, caliber]);
                            } else {
                              setSelectedCalibers(selectedCalibers.filter(c => c !== caliber));
                            }
                          }}
                          className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm text-gray-700">{caliber}</span>
                      </label>
                    ))}
                  </div>
                  {selectedCalibers.length > 0 && (
                    <button
                      onClick={() => setSelectedCalibers([])}
                      className="mt-2 text-sm text-indigo-600 hover:text-indigo-800"
                    >
                      Clear caliber filter
                    </button>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Color Grouping</label>
                  <select
                    value={colorGrouping}
                    onChange={(e) => setColorGrouping(e.target.value as 'vest' | 'protocol' | 'protection_level' | 'caliber' | 'none')}
                    className="w-full border rounded p-2"
                  >
                    <option value="none">None</option>
                    <option value="vest">Vest</option>
                    <option value="protocol">Protocol</option>
                    <option value="protection_level">Protection Level</option>
                    <option value="caliber">Caliber</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Real vs Estimated Graph */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Real vs Estimated BFD</h2>
            {filteredPointData.length > 0 ? (() => {
              const maxActual = Math.max(...filteredPointData.map((p: any) => p.actual_bfd));
              const maxPredicted = Math.max(...filteredPointData.map((p: any) => p.predicted_bfd));
              const maxValue = Math.max(maxActual, maxPredicted) + 5;

              // Calculate linear regression (trend line)
              const n = filteredPointData.length;
              const sumX = filteredPointData.reduce((sum: number, p: any) => sum + p.actual_bfd, 0);
              const sumY = filteredPointData.reduce((sum: number, p: any) => sum + p.predicted_bfd, 0);
              const sumXY = filteredPointData.reduce((sum: number, p: any) => sum + (p.actual_bfd * p.predicted_bfd), 0);
              const sumX2 = filteredPointData.reduce((sum: number, p: any) => sum + (p.actual_bfd * p.actual_bfd), 0);

              const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
              const intercept = (sumY - slope * sumX) / n;

              const minX = Math.min(...filteredPointData.map((p: any) => p.actual_bfd));
              const maxX = Math.max(...filteredPointData.map((p: any) => p.actual_bfd));

              // Color palette for grouping
              const colors = ['#dc2626', '#2563eb', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#ca8a04', '#db2777'];

              // Group data by color grouping
              const groupedData = colorGrouping !== 'none'
                ? (() => {
                    const groups = new Map<string, any[]>();
                    filteredPointData.forEach(p => {
                      let key: string;
                      if (colorGrouping === 'vest') {
                        key = p.vest_code;
                      } else if (colorGrouping === 'protocol') {
                        key = p.protocol;
                      } else if (colorGrouping === 'protection_level') {
                        key = p.protection_level;
                      } else if (colorGrouping === 'caliber') {
                        key = p.caliber;
                      } else {
                        key = 'all';
                      }
                      if (!groups.has(key)) {
                        groups.set(key, []);
                      }
                      groups.get(key)!.push(p);
                    });
                    return Array.from(groups.entries());
                  })()
                : [['all', filteredPointData]];

              const plotlyData = [
                // Perfect prediction line (green dashed)
                {
                  x: [0, maxValue],
                  y: [0, maxValue],
                  mode: 'lines' as const,
                  type: 'scatter' as const,
                  line: { color: 'green', width: 2, dash: 'dash' },
                  name: 'Perfect Prediction',
                  hoverinfo: 'skip',
                },
                // Trend line (red)
                {
                  x: [minX, maxX],
                  y: [slope * minX + intercept, slope * maxX + intercept],
                  mode: 'lines' as const,
                  type: 'scatter' as const,
                  line: { color: 'red', width: 2 },
                  name: 'Trend Line',
                  hoverinfo: 'skip',
                },
                // Data points grouped by color
                ...groupedData.map(([groupName, points], index) => ({
                  x: points.map((p: any) => p.actual_bfd),
                  y: points.map((p: any) => p.predicted_bfd),
                  mode: 'markers' as const,
                  type: 'scatter' as const,
                  marker: { size: 8, color: colorGrouping === 'none' ? '#3b82f6' : colors[index % colors.length] },
                  name: String(groupName),
                  text: points.map((p: any) =>
                    `Vest: ${p.vest_code}<br>Protocol: ${p.protocol}<br>Actual: ${p.actual_bfd?.toFixed(2)} mm<br>Predicted: ${p.predicted_bfd?.toFixed(2)} mm<br>Error: ${p.percent_error?.toFixed(2)}%`
                  ),
                  hoverinfo: 'text',
                })),
              ];

              return (
                <div className="h-[500px]">
                  <Plot
                    data={plotlyData}
                    layout={{
                      autosize: true,
                      margin: { t: 40, r: 40, b: 60, l: 80 },
                      xaxis: {
                        title: 'Actual BFD (mm)',
                        gridcolor: '#e5e7eb',
                        zerolinecolor: '#9ca3af',
                        range: [0, maxValue],
                      },
                      yaxis: {
                        title: 'Predicted BFD (mm)',
                        gridcolor: '#e5e7eb',
                        zerolinecolor: '#9ca3af',
                        range: [0, maxValue],
                      },
                      hovermode: 'closest',
                      plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                      paper_bgcolor: 'white',
                      font: { family: 'Inter, sans-serif' },
                      showlegend: colorGrouping !== 'none',
                    }}
                    config={{
                      responsive: true,
                      displayModeBar: true,
                      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                      displaylogo: false,
                    }}
                    style={{ width: '100%', height: '100%' }}
                  />
                </div>
              );
            })() : (
              <p className="text-sm text-gray-600">No point data available for graphing.</p>
            )}
          </div>

          {/* Error vs Measured BFD Graph */}
          <div className="bg-white rounded-lg shadow p-6 mt-6">
            <h2 className="text-xl font-semibold mb-4">Error vs Measured BFD</h2>
            {filteredPointData.length > 0 ? (() => {
              const maxActual = Math.max(...filteredPointData.map((p: any) => p.actual_bfd));
              const maxError = Math.max(...filteredPointData.map((p: any) => p.percent_error));
              const minError = Math.min(...filteredPointData.map((p: any) => p.percent_error));

              // Color palette for grouping
              const colors = ['#dc2626', '#2563eb', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#ca8a04', '#db2777'];

              // Group data by color grouping
              const groupedData = colorGrouping !== 'none'
                ? (() => {
                    const groups = new Map<string, any[]>();
                    filteredPointData.forEach(p => {
                      let key: string;
                      if (colorGrouping === 'vest') {
                        key = p.vest_code;
                      } else if (colorGrouping === 'protocol') {
                        key = p.protocol;
                      } else if (colorGrouping === 'protection_level') {
                        key = p.protection_level;
                      } else if (colorGrouping === 'caliber') {
                        key = p.caliber;
                      } else {
                        key = 'all';
                      }
                      if (!groups.has(key)) {
                        groups.set(key, []);
                      }
                      groups.get(key)!.push(p);
                    });
                    return Array.from(groups.entries());
                  })()
                : [['all', filteredPointData]];

              const plotlyData = [
                // Zero error line (green dashed)
                {
                  x: [0, maxActual + 5],
                  y: [0, 0],
                  mode: 'lines' as const,
                  type: 'scatter' as const,
                  line: { color: 'green', width: 2, dash: 'dash' },
                  name: 'Zero Error',
                  hoverinfo: 'skip',
                },
                // Average error line (orange)
                {
                  x: [0, maxActual + 5],
                  y: [healthData?.overall_average_error || 0, healthData?.overall_average_error || 0],
                  mode: 'lines' as const,
                  type: 'scatter' as const,
                  line: { color: 'orange', width: 2, dash: 'dot' },
                  name: `Avg Error: ${healthData?.overall_average_error?.toFixed(1)}%`,
                  hoverinfo: 'skip',
                },
                // Data points grouped by color
                ...groupedData.map(([groupName, points], index) => ({
                  x: points.map((p: any) => p.actual_bfd),
                  y: points.map((p: any) => p.percent_error),
                  mode: 'markers' as const,
                  type: 'scatter' as const,
                  marker: { size: 8, color: colorGrouping === 'none' ? '#3b82f6' : colors[index % colors.length] },
                  name: String(groupName),
                  text: points.map((p: any) =>
                    `Vest: ${p.vest_code}<br>Protocol: ${p.protocol}<br>Measured: ${p.actual_bfd?.toFixed(2)} mm<br>Predicted: ${p.predicted_bfd?.toFixed(2)} mm<br>Error: ${p.percent_error?.toFixed(2)}%`
                  ),
                  hoverinfo: 'text',
                })),
              ];

              return (
                <div className="h-[500px]">
                  <Plot
                    data={plotlyData}
                    layout={{
                      autosize: true,
                      margin: { t: 40, r: 40, b: 60, l: 80 },
                      xaxis: {
                        title: 'Measured BFD (mm)',
                        gridcolor: '#e5e7eb',
                        zerolinecolor: '#9ca3af',
                        range: [0, maxActual + 5],
                      },
                      yaxis: {
                        title: 'Error (%)',
                        gridcolor: '#e5e7eb',
                        zerolinecolor: '#9ca3af',
                        range: [Math.max(0, minError - 5), maxError + 5],
                      },
                      hovermode: 'closest',
                      plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                      paper_bgcolor: 'white',
                      font: { family: 'Inter, sans-serif' },
                      showlegend: true,
                    }}
                    config={{
                      responsive: true,
                      displayModeBar: true,
                      modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                      displaylogo: false,
                    }}
                    style={{ width: '100%', height: '100%' }}
                  />
                </div>
              );
            })() : (
              <p className="text-sm text-gray-600">No point data available for graphing.</p>
            )}
          </div>
        </>
      )}

      {error && !healthLoading && (
        <div className="bg-red-50 border border-red-200 rounded p-4">
          <h3 className="font-semibold text-red-800 mb-2">Error</h3>
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}
    </div>
    );
  };

  const renderAnchorTab = () => {
    const handleAddLayer = () => {
      const newLayer = {
        material_id: '',
        layer_count: 1,
        layer_index: anchorForm.layers.length
      };
      setAnchorForm({
        ...anchorForm,
        layers: [...anchorForm.layers, newLayer]
      });
    };

    const handleRemoveLayer = (index: number) => {
      setAnchorForm({
        ...anchorForm,
        layers: anchorForm.layers.filter((_, i) => i !== index).map((l, i) => ({ ...l, layer_index: i }))
      });
    };

    const handleLayerChange = (index: number, field: string, value: any) => {
      setAnchorForm({
        ...anchorForm,
        layers: anchorForm.layers.map((l, i) => i === index ? { ...l, [field]: value } : l)
      });
    };

    const handleSaveAnchor = async () => {
      setAnchorLoading(true);
      setError(null);
      try {
        if (editingAnchor) {
          await apiClient.put<any>(`/api/v1/anchor-points/${editingAnchor.id}`, anchorForm);
        } else {
          await apiClient.post<any>('/api/v1/anchor-points', anchorForm);
        }
        setShowAnchorForm(false);
        setEditingAnchor(null);
        setAnchorForm({
          name: '',
          description: '',
          ammunition_scope: 'all',
          caliber_ids: [],
          expected_perforated: false,
          expected_bfd_mm: '',
          custom_velocity_mps: '',
          layers: []
        });
        // Refresh anchor points
        const result = await apiClient.get<any>('/api/v1/anchor-points');
        setAnchorPoints(result || []);
      } catch (err: any) {
        setError(err.detail || 'Failed to save anchor point');
      } finally {
        setAnchorLoading(false);
      }
    };

    const handleEditAnchor = (anchor: any) => {
      setEditingAnchor(anchor);
      setAnchorForm({
        name: anchor.name,
        description: anchor.description || '',
        ammunition_scope: anchor.ammunition_scope,
        caliber_ids: anchor.caliber_ids || [],
        expected_perforated: anchor.expected_perforated,
        expected_bfd_mm: anchor.expected_bfd_mm?.toString() || '',
        custom_velocity_mps: anchor.custom_velocity_mps?.toString() || '',
        layers: anchor.layers?.map((l: any) => ({
          material_id: l.material_id,
          layer_count: l.layer_count,
          layer_index: l.layer_index
        })) || []
      });
      setShowAnchorForm(true);
    };

    const handleDeleteAnchor = async (id: string) => {
      if (!confirm('Are you sure you want to delete this anchor point?')) return;
      setAnchorLoading(true);
      try {
        await apiClient.delete<any>(`/api/v1/anchor-points/${id}`);
        const result = await apiClient.get<any>('/api/v1/anchor-points');
        setAnchorPoints(result || []);
      } catch (err: any) {
        setError(err.detail || 'Failed to delete anchor point');
      } finally {
        setAnchorLoading(false);
      }
    };

    const handleCancelEdit = () => {
      setShowAnchorForm(false);
      setEditingAnchor(null);
      setAnchorForm({
        name: '',
        description: '',
        ammunition_scope: 'all',
        caliber_ids: [],
        expected_perforated: false,
        expected_bfd_mm: '',
        custom_velocity_mps: '',
        layers: []
      });
    };

    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Anchor Points</h2>
            <button
              onClick={() => setShowAnchorForm(true)}
              className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
            >
              Add Anchor Point
            </button>
          </div>
          <p className="text-sm text-gray-600">
            Anchor points are synthetic training data that represent known boundary conditions (e.g., 10,000 layers will stop any bullet).
            These are used for model training but do not appear in analytics.
          </p>
        </div>

        {/* Anchor Point Form */}
        {showAnchorForm && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">{editingAnchor ? 'Edit Anchor Point' : 'Add Anchor Point'}</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={anchorForm.name}
                  onChange={(e) => setAnchorForm({ ...anchorForm, name: e.target.value })}
                  className="w-full border rounded p-2"
                  placeholder="e.g., 10,000 layers absolute stop"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <textarea
                  value={anchorForm.description}
                  onChange={(e) => setAnchorForm({ ...anchorForm, description: e.target.value })}
                  className="w-full border rounded p-2"
                  rows={2}
                  placeholder="Optional description"
                />
              </div>

              {/* Ammunition Scope */}
              <div>
                <label className="block text-sm font-medium mb-1">Ammunition Scope</label>
                <div className="flex space-x-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="specific"
                      checked={anchorForm.ammunition_scope === 'specific'}
                      onChange={(e) => setAnchorForm({ ...anchorForm, ammunition_scope: e.target.value })}
                      className="mr-2"
                    />
                    Specific Ammunition
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="all"
                      checked={anchorForm.ammunition_scope === 'all'}
                      onChange={(e) => setAnchorForm({ ...anchorForm, ammunition_scope: e.target.value })}
                      className="mr-2"
                    />
                    All Ammunition of Caliber
                  </label>
                </div>
              </div>

              {/* Ammunition Selection */}
              {anchorForm.ammunition_scope === 'specific' && (
                <div>
                  <label className="block text-sm font-medium mb-1">Select Ammunition</label>
                  <div className="max-h-40 overflow-y-auto border rounded p-2 space-y-2">
                    {ammunition.map((ammo) => (
                      <label key={ammo.id} className="flex items-center">
                        <input
                          type="checkbox"
                          checked={anchorForm.ammunition_ids.includes(ammo.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setAnchorForm({ ...anchorForm, ammunition_ids: [...anchorForm.ammunition_ids, ammo.id] });
                            } else {
                              setAnchorForm({ ...anchorForm, ammunition_ids: anchorForm.ammunition_ids.filter(id => id !== ammo.id) });
                            }
                          }}
                          className="mr-2"
                        />
                        <span className="text-sm">{ammo.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Caliber Filter */}
              {anchorForm.ammunition_scope === 'all' && (
                <div>
                  <label className="block text-sm font-medium mb-1">Caliber Filter</label>
                  <input
                    type="text"
                    value={anchorForm.caliber_filter}
                    onChange={(e) => setAnchorForm({ ...anchorForm, caliber_filter: e.target.value })}
                    className="w-full border rounded p-2"
                    placeholder="e.g., 9mm, .44 MAG"
                  />
                </div>
              )}

              {/* Layers */}
              <div>
                <label className="block text-sm font-medium mb-1">Material Composition</label>
                <div className="space-y-2">
                  {anchorForm.layers.map((layer, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <select
                        value={layer.material_id}
                        onChange={(e) => handleLayerChange(index, 'material_id', e.target.value)}
                        className="flex-1 border rounded p-2"
                      >
                        <option value="">Select material</option>
                        {materials.map((mat) => (
                          <option key={mat.id} value={mat.id}>{mat.name}</option>
                        ))}
                      </select>
                      <input
                        type="number"
                        value={layer.layer_count}
                        onChange={(e) => handleLayerChange(index, 'layer_count', parseInt(e.target.value))}
                        className="w-24 border rounded p-2"
                        min="1"
                        placeholder="Layers"
                      />
                      <button
                        onClick={() => handleRemoveLayer(index)}
                        className="text-red-600 hover:text-red-800"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  <button
                    onClick={handleAddLayer}
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    + Add Material Layer
                  </button>
                </div>
              </div>

              {/* Expected Outcome */}
              <div>
                <label className="block text-sm font-medium mb-1">Expected Perforated</label>
                <select
                  value={anchorForm.expected_perforated.toString()}
                  onChange={(e) => setAnchorForm({ ...anchorForm, expected_perforated: e.target.value === 'true' })}
                  className="w-full border rounded p-2"
                >
                  <option value="false">No (Stopped)</option>
                  <option value="true">Yes (Penetrated)</option>
                </select>
              </div>

              {!anchorForm.expected_perforated && (
                <div>
                  <label className="block text-sm font-medium mb-1">Expected BFD (mm)</label>
                  <input
                    type="number"
                    value={anchorForm.expected_bfd_mm}
                    onChange={(e) => setAnchorForm({ ...anchorForm, expected_bfd_mm: e.target.value })}
                    className="w-full border rounded p-2"
                    placeholder="e.g., 0, 5, 10"
                  />
                </div>
              )}

              {/* Custom Velocity */}
              <div>
                <label className="block text-sm font-medium mb-1">Custom Velocity (m/s) - Optional</label>
                <input
                  type="number"
                  value={anchorForm.custom_velocity_mps}
                  onChange={(e) => setAnchorForm({ ...anchorForm, custom_velocity_mps: e.target.value })}
                  className="w-full border rounded p-2"
                  placeholder="Leave empty to use nominal velocity from ammunition"
                />
              </div>

              {/* Actions */}
              <div className="flex space-x-2">
                <button
                  onClick={handleSaveAnchor}
                  disabled={anchorLoading}
                  className="bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 disabled:bg-gray-400"
                >
                  {anchorLoading ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="bg-gray-600 text-white py-2 px-4 rounded hover:bg-gray-700"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Anchor Points List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Existing Anchor Points ({anchorPoints.length})</h3>
          {anchorPoints.length === 0 ? (
            <p className="text-sm text-gray-600">No anchor points defined yet.</p>
          ) : (
            <div className="space-y-4">
              {anchorPoints.map((anchor) => (
                <div key={anchor.id} className="border rounded p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium">{anchor.name}</h4>
                      {anchor.description && <p className="text-sm text-gray-600">{anchor.description}</p>}
                      <div className="mt-2 text-sm">
                        <div><strong>Scope:</strong> {anchor.ammunition_scope === 'all' ? `All ${anchor.caliber_filter}` : `Specific (${anchor.ammunition_names?.join(', ')})`}</div>
                        <div><strong>Composition:</strong> {anchor.layers?.map((l: any) => `${l.layer_count}x ${l.material_name}`).join(' + ')}</div>
                        <div><strong>Expected:</strong> {anchor.expected_perforated ? 'Penetrated' : `Stopped (${anchor.expected_bfd_mm}mm BFD)`}</div>
                        {anchor.custom_velocity_mps && <div><strong>Velocity:</strong> {anchor.custom_velocity_mps} m/s</div>}
                        <div className="text-xs text-gray-500">Created by {anchor.created_by_username}</div>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handleEditAnchor(anchor)}
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteAnchor(anchor.id)}
                        className="text-red-600 hover:text-red-800 text-sm"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <h3 className="font-semibold text-red-800 mb-2">Error</h3>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Model Training</h1>

      {/* Tabs */}
      <div className="mb-6">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('training')}
              className={`${
                activeTab === 'training'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Training
            </button>
            <button
              onClick={() => setActiveTab('health')}
              className={`${
                activeTab === 'health'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Model Health
            </button>
            <button
              onClick={() => setActiveTab('anchor')}
              className={`${
                activeTab === 'anchor'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
            >
              Anchor Points
            </button>
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'training' ? renderTrainingTab() : activeTab === 'health' ? renderHealthTab(showAnchorPointDetails, setShowAnchorPointDetails) : <AnchorPointsTab onError={setError} />}

      {/* Success Modal */}
      {showSuccessModal && (
        <ConfirmModal
          title="Training Complete"
          message={
            <div>
              <p>The ML model has been trained successfully using data from the database.</p>
              {healthCheckStatus && (
                <div className="mt-2">
                  {healthCheckStatus.health_check_passed ? (
                    <p className="text-green-600">Health check passed with {healthCheckStatus.training_avg_error}% average error.</p>
                  ) : (
                    <p className="text-red-600">Health check failed. Please run a manual health check for details.</p>
                  )}
                </div>
              )}
            </div>
          }
          confirmLabel="OK"
          cancelLabel={undefined}
          onConfirm={() => {
            setShowSuccessModal(false);
            setHealthCheckStatus(null);
          }}
          onCancel={() => {
            setShowSuccessModal(false);
            setHealthCheckStatus(null);
          }}
        />
      )}

      {/* Optimization Progress Modal */}
      {showOptimizationModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Hyperparameter Optimization in Progress</h3>
            <div>
              <p className="mb-4 text-sm text-gray-600">Running Bayesian optimization to find the best hyperparameters...</p>
              {trialResults.length > 0 && (
                <div className="mt-4">
                  <div className="flex justify-between text-sm mb-2">
                    <span className="font-medium">Trials completed: {trialResults.length}</span>
                    <span className="font-medium">Best error: {Math.min(...trialResults.map(r => r.error)).toFixed(2)}%</span>
                  </div>
                  <div className="h-48 bg-white border rounded p-2">
                    <svg width="100%" height="100%" viewBox="0 0 400 150" preserveAspectRatio="none">
                      {(() => {
                        const maxTrial = Math.max(...trialResults.map(r => r.trial), 1);
                        const maxError = Math.max(...trialResults.map(r => r.error), 1);
                        const minError = Math.min(...trialResults.map(r => r.error), 0);
                        const width = 400;
                        const height = 150;
                        const padding = 30;

                        const xScale = (trial: number) => padding + (trial / maxTrial) * (width - 2 * padding);
                        const yScale = (error: number) => height - padding - ((error - minError) / (maxError - minError || 1)) * (height - 2 * padding);

                        return (
                          <>
                            {/* Grid lines */}
                            {[0, 0.25, 0.5, 0.75, 1].map((p) => (
                              <line
                                key={p}
                                x1={padding}
                                y1={height - padding - p * (height - 2 * padding)}
                                x2={width - padding}
                                y2={height - padding - p * (height - 2 * padding)}
                                stroke="#e5e7eb"
                                strokeWidth="1"
                              />
                            ))}

                            {/* X axis */}
                            <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#374151" strokeWidth="1" />
                            <text x={padding} y={height - 10} fontSize="10" fill="#374151">0</text>
                            <text x={width - padding} y={height - 10} fontSize="10" fill="#374151">{maxTrial}</text>

                            {/* Y axis */}
                            <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#374151" strokeWidth="1" />
                            <text x={5} y={padding + 5} fontSize="10" fill="#374151">{maxError.toFixed(1)}%</text>
                            <text x={5} y={height - padding} fontSize="10" fill="#374151">{minError.toFixed(1)}%</text>

                            {/* Line */}
                            <polyline
                              points={trialResults.map(r => `${xScale(r.trial)},${yScale(r.error)}`).join(' ')}
                              fill="none"
                              stroke="#8b5cf6"
                              strokeWidth="2"
                            />

                            {/* Points */}
                            {trialResults.map((r, i) => (
                              <circle
                                key={i}
                                cx={xScale(r.trial)}
                                cy={yScale(r.error)}
                                r="3"
                                fill="#8b5cf6"
                              />
                            ))}
                          </>
                        );
                      })()}
                    </svg>
                  </div>
                </div>
              )}
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button
                type="button"
                onClick={handleStopOptimization}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-md text-sm text-white"
              >
                Stop Optimization
              </button>
            </div>
          </div>
        </div>
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

      {/* Mass Delete Confirmation Modal */}
      {showMassDeleteModal && (
        <ConfirmModal
          title="Delete Selected Models"
          message={`Are you sure you want to delete ${selectedVersions.size} selected model versions? This action cannot be undone.`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          variant="danger"
          onConfirm={handleMassDeleteConfirm}
          onCancel={() => setShowMassDeleteModal(false)}
        />
      )}

      {/* Edit Name Modal */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowEditModal(false)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Edit Model</h3>
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
            <div className="mb-4">
              <button
                type="button"
                onClick={handleDownloadModel}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
              >
                Download Model
              </button>
            </div>
            <div className="flex justify-between space-x-3">
              <button
                type="button"
                onClick={() => {
                  setDeleteVersion(editVersion);
                  setShowEditModal(false);
                  setShowDeleteModal(true);
                }}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700"
              >
                Delete Model
              </button>
              <div className="flex space-x-3">
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
        </div>
      )}

      {/* Details Modal */}
      {showHealthModal && healthStatus && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowHealthModal(false)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Model Details</h3>
            <div className="space-y-4">
              <div><strong>Model Name:</strong> {healthStatus.model_name || 'N/A'}</div>
              <div><strong>Status:</strong> {healthStatus.status}</div>
              <div><strong>Version:</strong> {healthStatus.version || 'N/A'}</div>
              <div><strong>Trained At:</strong> {healthStatus.trained_at ? new Date(healthStatus.trained_at).toLocaleString() : 'N/A'}</div>
              <div><strong>Feature Count:</strong> {healthStatus.feature_count}</div>
              <div><strong>Training Data Count:</strong> {healthStatus.shot_count}</div>
              <div><strong>Material Count:</strong> {healthStatus.material_count}</div>
              <div><strong>Regression Targets:</strong> {healthStatus.regression_targets?.join(', ') || 'None'}</div>
              <div><strong>Classification Targets:</strong> {healthStatus.classification_targets?.join(', ') || 'None'}</div>
              {healthStatus.data_health && (
                <div className="mt-4 pt-4 border-t">
                  <h4 className="font-medium mb-2">Data Health</h4>
                  <div className="text-sm text-gray-600">
                    <div>Total Data Points: {healthStatus.data_health.total_data_points}</div>
                  </div>
                </div>
              )}
              {healthStatus.hyperparameters && (
                <div className="mt-4 pt-4 border-t">
                  <h4 className="font-medium mb-2">Hyperparameters</h4>
                  <div className="text-sm text-gray-600 space-y-1">
                    {Object.entries(healthStatus.hyperparameters).map(([key, value]) => (
                      <div key={key}>
                        <span className="font-medium">{key}:</span> {typeof value === 'number' ? value.toFixed(4) : value}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setShowHealthModal(false)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Model Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setShowUploadModal(false)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Model</h3>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Select Model File</label>
              <input
                type="file"
                accept=".zip"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="w-full border rounded p-2"
              />
              <p className="text-xs text-gray-500 mt-1">Upload a .zip file containing the model files</p>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => {
                  setShowUploadModal(false);
                  setUploadFile(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleUploadModel}
                disabled={!uploadFile || uploadLoading}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploadLoading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
