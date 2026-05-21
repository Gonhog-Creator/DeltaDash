import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';

interface ModelVersion {
  id: string;
  version: string;
  created_at: string;
  training_row_count: number;
  metrics: {
    rmse?: number;
    mae?: number;
    r2?: number;
    cv_rmse?: number;
    cv_rmse_std?: number;
  };
  artifact_path: string;
  is_current: boolean;
}

interface ValidationMetrics {
  model_run_id: string;
  validation_count: number;
  rmse?: number;
  mae?: number;
  max_error?: number;
  min_error?: number;
  within_2mm?: number;
  within_2mm_percent?: number;
  validation_date: string;
}

export function ModelTraining() {
  const { isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const [trainingParams, setTrainingParams] = useState({
    n_estimators: 100,
    max_depth: 6,
    learning_rate: 0.1,
    test_size: 0.2,
  });
  const [isTraining, setIsTraining] = useState(false);

  // Fetch model versions
  const { data: modelVersions, isLoading: isLoadingVersions } = useQuery({
    queryKey: ['ml', 'models', 'versions'],
    queryFn: async () => {
      const data = await apiClient.get<{ versions: ModelVersion[] }>('/api/v1/ml/models/versions');
      return data.versions;
    },
  });

  // Fetch current model
  const { data: currentModel, error: currentModelError } = useQuery({
    queryKey: ['ml', 'models', 'current'],
    queryFn: async () => {
      const data = await apiClient.get('/api/v1/ml/models/current');
      return data;
    },
    retry: false,
  });

  // Fetch validation metrics
  const { data: validationMetrics } = useQuery({
    queryKey: ['ml', 'validation'],
    queryFn: async () => {
      const data = await apiClient.get<ValidationMetrics>('/api/v1/ml/models/validate');
      return data;
    },
    enabled: !!currentModel && !currentModelError,
  });

  // Train model mutation
  const trainMutation = useMutation({
    mutationFn: async (params: typeof trainingParams) => {
      setIsTraining(true);
      const data = await apiClient.post('/api/v1/ml/models/train', params);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ml', 'models', 'versions'] });
      queryClient.invalidateQueries({ queryKey: ['ml', 'models', 'current'] });
      setIsTraining(false);
    },
    onError: () => {
      setIsTraining(false);
    },
  });

  const handleTrain = () => {
    if (isAdmin) {
      trainMutation.mutate(trainingParams);
    }
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">Admin access required</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Model Training</h1>
        <p className="text-sm text-gray-500 mt-1">
          Train and manage XGBoost models for BFD prediction
        </p>
      </div>

      {/* Training Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Train New Model</h2>
        
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Number of Estimators: {trainingParams.n_estimators}
            </label>
            <input
              type="range"
              min="50"
              max="500"
              step="50"
              value={trainingParams.n_estimators}
              onChange={(e) => setTrainingParams({ ...trainingParams, n_estimators: parseInt(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">Number of trees in the ensemble</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Depth: {trainingParams.max_depth}
            </label>
            <input
              type="range"
              min="3"
              max="12"
              step="1"
              value={trainingParams.max_depth}
              onChange={(e) => setTrainingParams({ ...trainingParams, max_depth: parseInt(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">Maximum depth of each tree</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Learning Rate: {trainingParams.learning_rate}
            </label>
            <input
              type="range"
              min="0.01"
              max="0.5"
              step="0.01"
              value={trainingParams.learning_rate}
              onChange={(e) => setTrainingParams({ ...trainingParams, learning_rate: parseFloat(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">Step size shrinkage</p>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Test Size: {trainingParams.test_size}
            </label>
            <input
              type="range"
              min="0.1"
              max="0.4"
              step="0.05"
              value={trainingParams.test_size}
              onChange={(e) => setTrainingParams({ ...trainingParams, test_size: parseFloat(e.target.value) })}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-1">Proportion for testing</p>
          </div>
        </div>

        <button
          onClick={handleTrain}
          disabled={isTraining}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {isTraining ? 'Training...' : 'Train Model'}
        </button>

        {trainMutation.data && (
          <div className="mt-4 p-4 bg-green-50 rounded-md">
            <p className="text-sm text-green-800 font-medium">Training completed successfully!</p>
            <div className="mt-2 text-sm text-green-700">
              <p>RMSE: {trainMutation.data.rmse?.toFixed(4)}</p>
              <p>MAE: {trainMutation.data.mae?.toFixed(4)}</p>
              <p>R²: {trainMutation.data.r2?.toFixed(4)}</p>
              <p>Training samples: {trainMutation.data.training_samples}</p>
            </div>
          </div>
        )}

        {trainMutation.error && (
          <div className="mt-4 p-4 bg-red-50 rounded-md">
            <p className="text-sm text-red-800 font-medium">Training failed</p>
            <p className="text-sm text-red-700 mt-1">
              {trainMutation.error instanceof Error ? trainMutation.error.message : 'Please try again.'}
            </p>
            <p className="text-xs text-red-600 mt-2">
              Make sure you have shot data with BFD measurements in the database.
            </p>
          </div>
        )}
      </div>

      {/* Current Model Info */}
      {currentModel && !currentModelError && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Current Model</h2>
          <div className="space-y-2">
            <p><span className="font-medium">Version:</span> {currentModel.version}</p>
            <p><span className="font-medium">Created:</span> {new Date(currentModel.created_at).toLocaleString()}</p>
            <p><span className="font-medium">Training samples:</span> {currentModel.training_row_count}</p>
            {currentModel.metrics && (
              <div className="mt-2">
                <p className="font-medium">Metrics:</p>
                <p>RMSE: {currentModel.metrics.rmse?.toFixed(4)}</p>
                <p>MAE: {currentModel.metrics.mae?.toFixed(4)}</p>
                <p>R²: {currentModel.metrics.r2?.toFixed(4)}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {!currentModel && !currentModelError && (
        <div className="bg-yellow-50 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-yellow-900 mb-2">No Model Trained Yet</h2>
          <p className="text-sm text-yellow-800">
            Train your first model using the controls above. You need shot data with BFD measurements in the database.
          </p>
        </div>
      )}

      {/* Model Versions */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Model Versions</h2>
        {isLoadingVersions ? (
          <p className="text-gray-500">Loading...</p>
        ) : modelVersions && modelVersions.length > 0 ? (
          <div className="space-y-2">
            {modelVersions.map((version) => (
              <div
                key={version.id}
                className={`p-3 rounded-md border ${
                  version.is_current ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-medium">
                      {version.version}
                      {version.is_current && (
                        <span className="ml-2 px-2 py-0.5 text-xs bg-indigo-100 text-indigo-800 rounded">
                          Current
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-gray-500">
                      {new Date(version.created_at).toLocaleString()}
                    </p>
                    <p className="text-sm text-gray-500">
                      Training samples: {version.training_row_count}
                    </p>
                  </div>
                  {version.metrics && (
                    <div className="text-sm text-right">
                      <p>RMSE: {version.metrics.rmse?.toFixed(4)}</p>
                      <p>R²: {version.metrics.r2?.toFixed(4)}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">No models trained yet</p>
        )}
      </div>

      {/* Validation Metrics */}
      {validationMetrics && validationMetrics.validation_count > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Validation Metrics</h2>
          <div className="space-y-2">
            <p><span className="font-medium">Validation count:</span> {validationMetrics.validation_count}</p>
            <p><span className="font-medium">RMSE:</span> {validationMetrics.rmse?.toFixed(4)}</p>
            <p><span className="font-medium">MAE:</span> {validationMetrics.mae?.toFixed(4)}</p>
            <p><span className="font-medium">Max error:</span> {validationMetrics.max_error?.toFixed(4)}</p>
            <p><span className="font-medium">Within 2mm:</span> {validationMetrics.within_2mm_percent?.toFixed(1)}%</p>
            <p className="text-sm text-gray-500 mt-2">
              Validated on: {new Date(validationMetrics.validation_date).toLocaleString()}
            </p>
          </div>
        </div>
      )}

      {/* Training Time Info */}
      <div className="bg-blue-50 rounded-lg p-4">
        <h3 className="font-medium text-blue-900 mb-2">Training Time Information</h3>
        <p className="text-sm text-blue-800">
          XGBoost training typically takes 10-60 seconds depending on:
        </p>
        <ul className="text-sm text-blue-800 list-disc list-inside mt-2">
          <li>Number of training samples in database</li>
          <li>Number of estimators (trees)</li>
          <li>Max depth of trees</li>
          <li>Server hardware</li>
        </ul>
        <p className="text-sm text-blue-800 mt-2">
          With typical ballistic test data (hundreds to thousands of shots), expect 20-40 seconds.
        </p>
      </div>
    </div>
  );
}
