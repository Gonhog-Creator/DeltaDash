import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useMaterials } from '../hooks/useMaterials';
import { Material } from '../api/materials';
import Plot from 'react-plotly.js';

interface BallisticInput {
  number_of_layers: number;
  vest_composition: string;
  ammunition_used: string;
  threat_level?: string;
  shot_number: number;
  impact_velocity_mps?: number;
  impact_angle_deg?: number;
  bullet_mass_g?: number;
  temperature_c?: number;
  humidity_pct?: number;
  condition?: string;
  panel_side?: string;
}

interface VestLayer {
  material_id: string | null;
  layer_count: number;
  notes?: string;
}

interface ShotPrediction {
  shot_number: number;
  predicted_backface_deformation_mm?: number;
  lower_95_ci_mm?: number;
  upper_95_ci_mm?: number;
  perforation_probability?: number;
}

interface VelocityCurvePoint {
  velocity_mps: number;
  predicted_bfd_mm: number;
}

interface PredictionResponse {
  shot_predictions: ShotPrediction[];
  velocity_curves: Record<number, VelocityCurvePoint[]>;
  training_data_count: number | string;
}

export function BallisticTesting() {
  const { data: materials } = useMaterials();

  // Initialize state with saved values from localStorage
  const getSavedInput = (): BallisticInput => {
    const savedInput = localStorage.getItem('ballisticTestingInput');
    if (savedInput) {
      return JSON.parse(savedInput);
    }
    return {
      number_of_layers: 48,
      vest_composition: '',
      ammunition_used: '.44 MAG',
      threat_level: 'RB3',
      shot_number: 1,
      impact_velocity_mps: 434.6,
      impact_angle_deg: 0,
      temperature_c: 22,
      humidity_pct: 50,
      condition: 'Ambient',
      panel_side: 'Front',
    };
  };

  const getSavedLayers = (): VestLayer[] => {
    const savedLayers = localStorage.getItem('ballisticTestingLayers');
    if (savedLayers) {
      return JSON.parse(savedLayers);
    }
    return [];
  };

  const getSavedVersion = (): string => {
    const savedVersion = localStorage.getItem('ballisticTestingVersion');
    return savedVersion || '';
  };

  const [input, setInput] = useState<BallisticInput>(getSavedInput);
  const [layers, setLayers] = useState<VestLayer[]>(getSavedLayers);
  const [selectedVersion, setSelectedVersion] = useState<string>(getSavedVersion);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [modelVersions, setModelVersions] = useState<any[]>([]);
  const [showVestModal, setShowVestModal] = useState(false);
  const [vests, setVests] = useState<any[]>([]);
  const [importedVestName, setImportedVestName] = useState<string | null>(null);

  // Save state to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('ballisticTestingInput', JSON.stringify(input));
  }, [input]);

  useEffect(() => {
    localStorage.setItem('ballisticTestingLayers', JSON.stringify(layers));
  }, [layers]);

  useEffect(() => {
    localStorage.setItem('ballisticTestingVersion', selectedVersion);
  }, [selectedVersion]);

  const fetchVests = async () => {
    try {
      const result = await apiClient.get<any>('/api/v1/vests/');
      setVests(result || []);
    } catch (err: any) {
      console.error('Failed to fetch vests:', err);
    }
  };

  const importVest = async (vestId: string) => {
    try {
      const result = await apiClient.get<any>(`/api/v1/vests/${vestId}`);
      const vest = result;

      console.log('Importing vest:', vest);

      // Calculate total layers from vest layers
      const vestLayers = vest.layers || [];
      const totalLayers = vestLayers.reduce((sum: number, vl: any) => sum + (vl.layer_count || 1), 0);

      // Convert vest layers to BallisticTesting layers format
      const newLayers = vestLayers.map((vl: any) => ({
        material_id: vl.material_id,
        layer_count: vl.layer_count || 1,
        notes: vl.notes || undefined,
      }));

      setInput({ ...input, number_of_layers: totalLayers });
      setLayers(newLayers);
      setImportedVestName(vest.vest_code || vest.name || null);
      setShowVestModal(false);
    } catch (err: any) {
      console.error('Failed to import vest:', err);
    }
  };

  const handleOpenVestModal = () => {
    fetchVests();
    setShowVestModal(true);
  };

  const fetchModelVersions = async () => {
    try {
      const result = await apiClient.get<any>('/api/v1/ballistic/versions');
      const versions = result.versions || [];
      setModelVersions(versions);
      // Default to latest version (first in list, sorted by date)
      if (versions.length > 0 && !selectedVersion) {
        setSelectedVersion(versions[0].version);
      }
    } catch (err: any) {
      console.error('Failed to fetch model versions:', err);
    }
  };

  const addLayer = () => {
    setLayers([...layers, { material_id: null, layer_count: 1 }]);
  };

  const removeLayer = (index: number) => {
    setLayers(layers.filter((_, i) => i !== index));
  };

  const updateLayer = (index: number, field: keyof VestLayer, value: any) => {
    const updatedLayers = [...layers];
    updatedLayers[index] = { ...updatedLayers[index], [field]: value };
    setLayers(updatedLayers);
  };

  const buildCompositionString = (): string => {
    if (!materials || layers.length === 0) return '';
    
    const parts = layers.map(layer => {
      const material = materials.find(m => m.id === layer.material_id);
      if (!material) return '';
      return `${layer.layer_count} ${material.name}`;
    }).filter(part => part !== '');
    
    return parts.join(' + ');
  };

  const handlePredict = async () => {
    // Validate layer count
    const totalLayerCount = layers.reduce((sum, layer) => sum + (layer.layer_count || 0), 0);
    if (totalLayerCount !== input.number_of_layers) {
      setValidationError(`Total layers (${totalLayerCount}) must match specified number of layers (${input.number_of_layers})`);
      return;
    }

    // Build composition string from layers
    const composition = buildCompositionString();
    if (!composition) {
      setValidationError('Please add at least one layer with a material');
      return;
    }

    setLoading(true);
    setError(null);
    setPrediction(null);
    setValidationError(null);

    try {
      const url = `/api/v1/ballistic/predict?version=${selectedVersion || modelVersions[0]?.version || ''}`;
      const result = await apiClient.post<PredictionResponse>(url, {
        ...input,
        vest_composition: composition,
      });
      setPrediction(result);
    } catch (err: any) {
      const errorMessage = err.detail || 'Prediction failed';
      // Check if it's a material validation error
      if (errorMessage.includes('Unknown material')) {
        setModalError(errorMessage);
        setShowErrorModal(true);
      } else {
        setError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelVersions();
  }, []);

  const formatPercent = (val?: number) => {
    if (val === undefined || val === null) return 'N/A';
    return `${(val * 100).toFixed(1)}%`;
  };

  const formatMM = (val?: number) => {
    if (val === undefined || val === null) return 'N/A';
    return `${val.toFixed(2)} mm`;
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Ballistic Testing Prediction</h1>

      <div className="space-y-6">
        {/* Input Form - Two Columns */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Input Parameters</h2>

          {/* Model Version Selector */}
          {modelVersions.length > 0 && (
            <div className="mb-4 pb-4 border-b">
              <label className="block text-sm font-medium mb-1">Model Version</label>
              <select
                value={selectedVersion || modelVersions[0]?.version || ''}
                onChange={(e) => setSelectedVersion(e.target.value || null)}
                className="w-full border rounded p-2"
              >
                {modelVersions.map((version) => (
                  <option key={version.version} value={version.version}>
                    {version.model_name || version.version}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Column - Layers */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Total Number of Layers</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    className="flex-1 border rounded p-2"
                    value={input.number_of_layers}
                    onChange={(e) => setInput({ ...input, number_of_layers: e.target.value === '' ? '' : parseInt(e.target.value) })}
                  />
                  <button
                    type="button"
                    onClick={handleOpenVestModal}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Import Vest
                  </button>
                </div>
                {importedVestName && (
                  <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded">
                    <p className="text-sm text-blue-800">
                      Imported Vest: <strong>{importedVestName}</strong>
                    </p>
                  </div>
                )}
              </div>

              <div className="border-t pt-4 mt-4">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-md font-medium text-gray-900">Layers</h3>
                  <button
                    type="button"
                    onClick={addLayer}
                    className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
                  >
                    Add Layer
                  </button>
                </div>
                {layers.map((layer, index) => (
                  <div key={index} className="bg-gray-50 p-4 rounded-md mb-3">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium text-gray-700">Layer {index + 1}</span>
                      <button
                        type="button"
                        onClick={() => removeLayer(index)}
                        className="text-red-600 hover:text-red-900 text-sm"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="grid grid-cols-1 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-700">Material</label>
                        <select
                          value={layer.material_id || ''}
                          onChange={(e) => updateLayer(index, 'material_id', e.target.value || null)}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                        >
                          <option value="">Select material...</option>
                          {materials?.map((material) => (
                            <option key={material.id} value={material.id}>
                              {material.name} ({material.material_class || 'N/A'}) {material.ply_count ? `- ${material.ply_count} ply` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700">Layer Count</label>
                        <input
                          type="number"
                          min="1"
                          value={layer.layer_count}
                          onChange={(e) => updateLayer(index, 'layer_count', e.target.value === '' ? '' : parseInt(e.target.value))}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                        />
                      </div>
                    </div>
                  </div>
                ))}
                {layers.length > 0 && (
                  <div className="text-sm text-gray-600 mt-2">
                    Total layers from builder: {layers.reduce((sum, layer) => sum + (layer.layer_count || 0), 0)}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column - Other Parameters */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Ammunition Used</label>
                <input
                  type="text"
                  className="w-full border rounded p-2"
                  value={input.ammunition_used}
                  onChange={(e) => setInput({ ...input, ammunition_used: e.target.value })}
                  placeholder="e.g., .44 MAG"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Threat Level</label>
                <input
                  type="text"
                  className="w-full border rounded p-2"
                  value={input.threat_level || ''}
                  onChange={(e) => setInput({ ...input, threat_level: e.target.value })}
                  placeholder="e.g., RB3"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Velocity (m/s)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full border rounded p-2"
                    value={input.impact_velocity_mps || ''}
                    onChange={(e) => setInput({ ...input, impact_velocity_mps: e.target.value === '' ? undefined : parseFloat(e.target.value) })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Impact Angle (deg)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full border rounded p-2"
                    value={input.impact_angle_deg || ''}
                    onChange={(e) => setInput({ ...input, impact_angle_deg: e.target.value === '' ? undefined : parseFloat(e.target.value) })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Temperature (°C)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full border rounded p-2"
                    value={input.temperature_c || ''}
                    onChange={(e) => setInput({ ...input, temperature_c: e.target.value === '' ? undefined : parseFloat(e.target.value) })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Humidity (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    className="w-full border rounded p-2"
                    value={input.humidity_pct || ''}
                    onChange={(e) => setInput({ ...input, humidity_pct: e.target.value === '' ? undefined : parseFloat(e.target.value) })}
                  />
                </div>
              </div>


              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Condition</label>
                  <select
                    className="w-full border rounded p-2"
                    value={input.condition || ''}
                    onChange={(e) => setInput({ ...input, condition: e.target.value || undefined })}
                  >
                    <option value="">Select condition...</option>
                    <option value="Ambient">Ambient (Seco/Dry)</option>
                    <option value="Humid">Humid (Humedo/Wet)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Panel Side</label>
                  <div className="flex gap-4 mt-2">
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="panel_side"
                        value="front"
                        checked={input.panel_side === 'front'}
                        onChange={(e) => setInput({ ...input, panel_side: e.target.value })}
                        className="mr-2"
                      />
                      Front
                    </label>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="panel_side"
                        value="back"
                        checked={input.panel_side === 'back'}
                        onChange={(e) => setInput({ ...input, panel_side: e.target.value })}
                        className="mr-2"
                      />
                      Back
                    </label>
                  </div>
                </div>
              </div>

              <button
                onClick={handlePredict}
                disabled={loading}
                className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {loading ? 'Predicting...' : 'Predict'}
              </button>
            </div>
          </div>
        </div>

        {/* Prediction Results - Full Width Below */}
        {prediction && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Prediction Results</h2>
            <p className="text-sm text-gray-600 mb-4">Model trained on {prediction.training_data_count} data points</p>

            {/* 6-Shot Predictions Table */}
            <div className="mb-6">
              <h3 className="font-semibold text-blue-800 mb-2">6-Shot Predictions</h3>
              <table className="min-w-full border border-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Shot #</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Predicted BFD (mm)</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">95% CI (mm)</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Perforation Prob</th>
                  </tr>
                </thead>
                <tbody>
                  {prediction.shot_predictions.map((shot) => (
                    <tr key={shot.shot_number} className="border-b">
                      <td className="px-4 py-2 text-sm">{shot.shot_number}</td>
                      <td className="px-4 py-2 text-sm font-medium">{formatMM(shot.predicted_backface_deformation_mm)}</td>
                      <td className="px-4 py-2 text-sm">{formatMM(shot.lower_95_ci_mm)} - {formatMM(shot.upper_95_ci_mm)}</td>
                      <td className="px-4 py-2 text-sm">{formatPercent(shot.perforation_probability)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* BFD vs Velocity Chart */}
            <div className="mb-6">
              <h3 className="font-semibold text-blue-800 mb-2">BFD vs Velocity Curve (All 6 Shots)</h3>
              <div className="border border-gray-200 rounded p-4">
                <Plot
                  data={Object.entries(prediction.velocity_curves).map(([shotNum, curve]) => ({
                    x: curve.map(p => p.velocity_mps),
                    y: curve.map(p => p.predicted_bfd_mm),
                    type: 'scatter',
                    mode: 'lines+markers',
                    marker: { size: 6 },
                    line: { width: 2 },
                    name: `Shot ${shotNum}`,
                  }))}
                  layout={{
                    width: undefined,
                    height: 400,
                    margin: { t: 20, r: 20, b: 50, l: 60 },
                    xaxis: {
                      title: 'Velocity (m/s)',
                      titlefont: { size: 14 },
                      tickfont: { size: 12 },
                    },
                    yaxis: {
                      title: 'Predicted BFD (mm)',
                      titlefont: { size: 14 },
                      tickfont: { size: 12 },
                    },
                    hovermode: 'closest',
                    legend: {
                      x: 0,
                      y: 1,
                      bgcolor: 'rgba(255,255,255,0.8)',
                    },
                  }}
                  config={{ responsive: true, displayModeBar: false }}
                />
              </div>
            </div>
          </div>
        )}

        {validationError && (
          <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
            <h3 className="font-semibold text-yellow-800 mb-2">Validation Error</h3>
            <p className="text-sm text-yellow-600">{validationError}</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <h3 className="font-semibold text-red-800 mb-2">Error</h3>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}
      </div>

      {/* Error Modal */}
      {showErrorModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-semibold text-red-800 mb-4">Material Not Found</h3>
            <p className="text-sm text-gray-700 mb-6">{modalError}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowErrorModal(false)}
                className="bg-red-600 text-white py-2 px-4 rounded hover:bg-red-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Vest Import Modal */}
      {showVestModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <h3 className="text-xl font-semibold mb-4">Import Vest</h3>
            <p className="text-sm text-gray-600 mb-4">Select a vest to import its composition as layers.</p>
            
            {vests.length === 0 ? (
              <p className="text-sm text-gray-500 mb-4">No vests found.</p>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {vests.map((vest: any) => (
                  <div
                    key={vest.id}
                    className="border border-gray-200 rounded p-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => importVest(vest.id)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-medium text-gray-900">{vest.vest_code || vest.name || vest.id || 'Unnamed Vest'}</h4>
                        <p className="text-sm text-gray-600">
                          Type: {vest.vest_type || 'N/A'} | 
                          Threat Level: {vest.threat_level || 'N/A'}
                        </p>
                      </div>
                      <button className="text-blue-600 hover:text-blue-700 text-sm font-medium">
                        Import
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            <div className="flex justify-end mt-6">
              <button
                onClick={() => setShowVestModal(false)}
                className="bg-gray-600 text-white py-2 px-4 rounded hover:bg-gray-700"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
