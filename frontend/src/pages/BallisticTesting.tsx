import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useMaterials } from '../hooks/useMaterials';
import { useProtocols } from '../hooks/useProtocols';
import { useVests } from '../hooks/useVests';
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
  side: string;
  conditioning: string;
  ammunition_id: string;
  ammunition_name: string;
  reference_velocity_m_s: number;
  predicted_bfd_mm: number;
  confidence_interval_low_mm: number;
  confidence_interval_high_mm: number;
  comparable_shot_count: number;
  extrapolation_warning: boolean;
}

interface VelocityCurvePoint {
  velocity_mps: number;
  predicted_bfd_mm: number;
}

interface PredictionResponse {
  protocol_id: string;
  protocol_name: string;
  vest_id: string;
  vest_code: string;
  total_shots: number;
  predictions: ShotPrediction[];
  summary: {
    mean_bfd_mm: number;
    max_bfd_mm: number;
    min_bfd_mm: number;
    std_bfd_mm: number;
  };
  model_version: string;
  velocity_curves?: Record<string, VelocityCurvePoint[]>;
}

export function BallisticTesting() {
  const { data: materials } = useMaterials();
  const { data: protocols } = useProtocols();
  const { data: vests } = useVests();

  const [selectedVestId, setSelectedVestId] = useState<string>('');
  const [selectedProtocolId, setSelectedProtocolId] = useState<string>('');
  const [selectedLevelIndex, setSelectedLevelIndex] = useState<number>(-1);
  const [selectedVersion, setSelectedVersion] = useState<string>('');
  const [modelVersions, setModelVersions] = useState<any[]>([]);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Custom Vest State
  const [useCustomVest, setUseCustomVest] = useState(false);
  const [customVestLayers, setCustomVestLayers] = useState<Array<{material_id: string; layer_count: number; notes?: string}>>([]);
  const [customVestBase, setCustomVestBase] = useState({
    vest_type: 'soft' as 'soft' | 'hard' | 'hybrid',
    is_female: false,
    panel_protects_front: true,
    panel_protects_back: true,
    panel_protects_sides: false,
  });

  // Calculate derived values from layers
  const calculatedThickness = customVestLayers.reduce((sum, layer) => {
    const material = materials?.find(m => m.id === layer.material_id);
    if (material?.thickness_mm && layer.layer_count) {
      return sum + (material.thickness_mm * layer.layer_count);
    }
    return sum;
  }, 0);

  const calculatedTotalLayers = customVestLayers.reduce((sum, layer) => sum + (layer.layer_count || 0), 0);

  const calculatedArealDensity = customVestLayers.reduce((sum, layer) => {
    const material = materials?.find(m => m.id === layer.material_id);
    if (material?.areal_density_g_m2 && layer.layer_count) {
      return sum + (material.areal_density_g_m2 * layer.layer_count);
    }
    return sum;
  }, 0);

  const addCustomLayer = () => {
    setCustomVestLayers([...customVestLayers, { material_id: '', layer_count: 1 }]);
  };

  const removeCustomLayer = (index: number) => {
    setCustomVestLayers(customVestLayers.filter((_, i) => i !== index));
  };

  const updateCustomLayer = (index: number, field: string, value: any) => {
    const updated = [...customVestLayers];
    updated[index] = { ...updated[index], [field]: value };
    setCustomVestLayers(updated);
  };

  // Fetch model versions on mount
  useEffect(() => {
    const fetchModelVersions = async () => {
      try {
        const result = await apiClient.get<any>('/api/v1/ballistic/versions');
        const versions = result.versions || [];
        setModelVersions(versions);
        if (versions.length > 0) {
          setSelectedVersion(versions[0].version);
        }
      } catch (err) {
        console.error('Failed to fetch model versions:', err);
      }
    };
    fetchModelVersions();
  }, []);

  // Reset level selection when protocol changes
  const handleProtocolChange = (protocolId: string) => {
    setSelectedProtocolId(protocolId);
    setSelectedLevelIndex(-1);
  };

  const handlePredict = async () => {
    if (!useCustomVest && !selectedVestId) {
      setValidationError('Please select a vest');
      return;
    }
    if (!selectedProtocolId) {
      setValidationError('Please select a protocol');
      return;
    }
    if (selectedLevelIndex === -1) {
      setValidationError('Please select a protocol level');
      return;
    }

    setLoading(true);
    setError(null);
    setPrediction(null);
    setValidationError(null);

    try {
      const requestBody: any = {
        protocol_id: selectedProtocolId,
        level_index: selectedLevelIndex,
      };

      if (useCustomVest) {
        requestBody.custom_vest = {
          ...customVestBase,
          total_layers: calculatedTotalLayers,
          total_thickness_mm: calculatedThickness,
          material_areal_density_g_m2: calculatedArealDensity,
          layers: customVestLayers,
        };
      } else {
        requestBody.vest_id = selectedVestId;
      }

      const result = await apiClient.post<PredictionResponse>(
        `/api/v1/ballistic/predict-protocol?version=${selectedVersion}`,
        requestBody
      );
      setPrediction(result);
    } catch (err: any) {
      let errorMessage = 'Prediction failed';
      if (err.detail) {
        if (typeof err.detail === 'string') {
          errorMessage = err.detail;
        } else if (Array.isArray(err.detail)) {
          errorMessage = err.detail.map((e: any) => e.msg || e).join(', ');
        } else if (typeof err.detail === 'object') {
          errorMessage = err.detail.msg || JSON.stringify(err.detail);
        }
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

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
        {/* Input Form */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Input Parameters</h2>

          {/* Model Version Selector */}
          {modelVersions.length > 0 && (
            <div className="mb-4 pb-4 border-b">
              <label className="block text-sm font-medium mb-1">Model Version</label>
              <select
                value={selectedVersion}
                onChange={(e) => setSelectedVersion(e.target.value)}
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

          {/* Vest Selection Toggle */}
          <div className="mb-4 flex items-center space-x-4">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                checked={!useCustomVest}
                onChange={() => setUseCustomVest(false)}
                className="rounded-full"
              />
              <span className="font-medium">Select Prebuilt Vest</span>
            </label>
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="radio"
                checked={useCustomVest}
                onChange={() => setUseCustomVest(true)}
                className="rounded-full"
              />
              <span className="font-medium">Build Custom Vest</span>
            </label>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Prebuilt Vest Selection */}
            {!useCustomVest && (
              <div>
                <label className="block text-sm font-medium mb-1">Vest</label>
                <select
                  value={selectedVestId}
                  onChange={(e) => setSelectedVestId(e.target.value)}
                  className="w-full border rounded p-2"
                >
                  <option value="">Select vest...</option>
                  {vests?.sort((a, b) => (a.vest_code || a.name).localeCompare(b.vest_code || b.name)).map((vest) => (
                    <option key={vest.id} value={vest.id}>
                      {vest.vest_code || vest.name} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Custom Vest Form */}
            {useCustomVest && (
              <div className="lg:col-span-2 space-y-4">
                {/* Basic Vest Properties */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Vest Type</label>
                    <select
                      value={customVestBase.vest_type}
                      onChange={(e) => setCustomVestBase({...customVestBase, vest_type: e.target.value as 'soft' | 'hard' | 'hybrid'})}
                      className="w-full border rounded p-2"
                    >
                      <option value="soft">Soft Armor</option>
                      <option value="hard">Hard Armor</option>
                      <option value="hybrid">Hybrid</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Gender</label>
                    <select
                      value={customVestBase.is_female ? 'female' : 'male'}
                      onChange={(e) => setCustomVestBase({...customVestBase, is_female: e.target.value === 'female'})}
                      className="w-full border rounded p-2"
                    >
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-2">Panel Protection</label>
                    <div className="flex space-x-3 text-sm">
                      <label className="flex items-center space-x-1">
                        <input
                          type="checkbox"
                          checked={customVestBase.panel_protects_front}
                          onChange={(e) => setCustomVestBase({...customVestBase, panel_protects_front: e.target.checked})}
                          className="rounded"
                        />
                        <span>Front</span>
                      </label>
                      <label className="flex items-center space-x-1">
                        <input
                          type="checkbox"
                          checked={customVestBase.panel_protects_back}
                          onChange={(e) => setCustomVestBase({...customVestBase, panel_protects_back: e.target.checked})}
                          className="rounded"
                        />
                        <span>Back</span>
                      </label>
                    </div>
                  </div>
                </div>

                {/* Layer Builder */}
                <div className="border rounded p-4 bg-gray-50">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-medium text-gray-800">Vest Layers</h4>
                    <button
                      type="button"
                      onClick={addCustomLayer}
                      className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                    >
                      Add Layer
                    </button>
                  </div>

                  {customVestLayers.length === 0 && (
                    <p className="text-sm text-gray-500 italic mb-3">No layers added yet. Click "Add Layer" to start building your vest.</p>
                  )}

                  {customVestLayers.map((layer, index) => (
                    <div key={index} className="bg-white p-3 rounded mb-2 border">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700">Layer {index + 1}</span>
                        <button
                          type="button"
                          onClick={() => removeCustomLayer(index)}
                          className="text-red-600 hover:text-red-900 text-sm"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">Material</label>
                          <select
                            value={layer.material_id || ''}
                            onChange={(e) => updateCustomLayer(index, 'material_id', e.target.value || null)}
                            className="w-full border rounded p-2 text-sm"
                          >
                            <option value="">Select material...</option>
                            {materials?.map((material) => (
                              <option key={material.id} value={material.id}>
                                {material.name} ({material.material_class || 'N/A'})
                                {material.ply_count ? ` - ${material.ply_count} ply` : ''}
                                {material.thickness_mm ? ` - ${material.thickness_mm}mm` : ''}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-600 mb-1">Layer Count</label>
                          <input
                            type="number"
                            value={layer.layer_count || ''}
                            onChange={(e) => updateCustomLayer(index, 'layer_count', e.target.value === '' ? '' : parseInt(e.target.value))}
                            className="w-full border rounded p-2 text-sm"
                            min={1}
                            placeholder="Enter count"
                          />
                        </div>
                      </div>
                    </div>
                  ))}

                  {/* Calculated Totals */}
                  {customVestLayers.length > 0 && (
                    <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-200">
                      <h5 className="text-sm font-medium text-blue-800 mb-2">Calculated Totals</h5>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-gray-600">Total Layers:</span>
                          <span className="font-medium ml-1">{calculatedTotalLayers}</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Total Thickness:</span>
                          <span className="font-medium ml-1">{calculatedThickness.toFixed(2)} mm</span>
                        </div>
                        <div>
                          <span className="text-gray-600">Areal Density:</span>
                          <span className="font-medium ml-1">{calculatedArealDensity.toFixed(0)} g/m²</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Protocol Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">Protocol</label>
              <select
                value={selectedProtocolId}
                onChange={(e) => handleProtocolChange(e.target.value)}
                className="w-full border rounded p-2"
              >
                <option value="">Select protocol...</option>
                {protocols?.map((protocol) => (
                  <option key={protocol.id} value={protocol.id}>
                    {protocol.name} {protocol.description ? `- ${protocol.description}` : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Level Selection (only shown when protocol is selected) */}
            {selectedProtocolId && (
              <div className="lg:col-span-2">
                <label className="block text-sm font-medium mb-1">Protocol Level</label>
                <select
                  value={selectedLevelIndex}
                  onChange={(e) => setSelectedLevelIndex(parseInt(e.target.value))}
                  className="w-full border rounded p-2"
                >
                  <option value="-1">Select level...</option>
                  {protocols?.find(p => p.id === selectedProtocolId)?.levels_config?.map((level, index) => (
                    <option key={index} value={index}>
                      {level.level_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="mt-6">
            <button
              onClick={handlePredict}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? 'Predicting...' : 'Predict'}
            </button>
          </div>
        </div>

        {/* Prediction Results */}
        {prediction && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Prediction Results</h2>
            <p className="text-sm text-gray-600 mb-4">
              Protocol: <strong>{prediction.protocol_name}</strong> | 
              Vest: <strong>{prediction.vest_code}</strong> | 
              Total Shots: <strong>{prediction.total_shots}</strong> | 
              Model Version: <strong>{prediction.model_version}</strong>
            </p>

            {/* Summary Statistics */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
              <h3 className="font-semibold text-blue-800 mb-2">Summary Statistics</h3>
              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Mean BFD (first 3):</span>
                  <span className="ml-2 font-medium">{prediction.summary.mean_bfd_mm !== null ? prediction.summary.mean_bfd_mm.toFixed(2) + ' mm' : 'N/A (all perforated)'}</span>
                </div>
                <div>
                  <span className="text-gray-600">Max BFD:</span>
                  <span className="ml-2 font-medium">{prediction.summary.max_bfd_mm !== null ? prediction.summary.max_bfd_mm.toFixed(2) + ' mm' : 'N/A (all perforated)'}</span>
                </div>
                <div>
                  <span className="text-gray-600">Min BFD:</span>
                  <span className="ml-2 font-medium">{prediction.summary.min_bfd_mm !== null ? prediction.summary.min_bfd_mm.toFixed(2) + ' mm' : 'N/A (all perforated)'}</span>
                </div>
                <div>
                  <span className="text-gray-600">Std Dev:</span>
                  <span className="ml-2 font-medium">{prediction.summary.std_bfd_mm !== null ? prediction.summary.std_bfd_mm.toFixed(2) + ' mm' : 'N/A (all perforated)'}</span>
                </div>
              </div>
            </div>

            {/* Detailed Predictions Table */}
            <div className="mb-6">
              <h3 className="font-semibold text-blue-800 mb-2">Detailed Predictions</h3>
              <div className="overflow-x-auto">
                {(() => {
                  // Group predictions by ammunition, then by side, then by shot number
                  const groupedByAmmo = prediction.predictions.reduce((acc, shot) => {
                    if (!acc[shot.ammunition_name]) {
                      acc[shot.ammunition_name] = {};
                    }
                    if (!acc[shot.ammunition_name][shot.side]) {
                      acc[shot.ammunition_name][shot.side] = {};
                    }
                    if (!acc[shot.ammunition_name][shot.side][shot.shot_number]) {
                      acc[shot.ammunition_name][shot.side][shot.shot_number] = [];
                    }
                    acc[shot.ammunition_name][shot.side][shot.shot_number].push(shot);
                    return acc;
                  }, {} as Record<string, Record<string, Record<number, typeof prediction.predictions>>>);

                  return Object.entries(groupedByAmmo).map(([ammoName, sides]) => (
                    <div key={ammoName} className="mb-6">
                      <h4 className="text-md font-medium text-gray-800 mb-3 bg-gray-100 px-3 py-2 rounded">{ammoName}</h4>
                      {Object.entries(sides).map(([side, shotsByNumber]) => (
                        <div key={side} className="mb-4">
                          <h5 className="text-sm font-medium text-gray-700 mb-2 ml-2 capitalize">{side}</h5>
                          <table className="min-w-full border border-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Shot #</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Conditioning</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Velocity (m/s)</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Min BFD (mm)</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Target BFD (mm)</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Max BFD (mm)</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Perf. Prob.</th>
                                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">95% CI (mm)</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(() => {
                                // Flatten all shots for this side
                                const allShots = Object.entries(shotsByNumber).flatMap(([shotNum, velocityVariants]) => {
                                  const byConditioning = velocityVariants.reduce((acc, shot) => {
                                    if (!acc[shot.conditioning]) {
                                      acc[shot.conditioning] = [];
                                    }
                                    acc[shot.conditioning].push(shot);
                                    return acc;
                                  }, {} as Record<string, typeof velocityVariants>);

                                  return Object.entries(byConditioning).map(([conditioning, condVariants]) => ({
                                    shotNum,
                                    conditioning,
                                    condVariants,
                                  }));
                                });

                                // Sort by conditioning (dry first), then by shot number
                                allShots.sort((a, b) => {
                                  if (a.conditioning !== b.conditioning) {
                                    return a.conditioning === 'dry' ? -1 : 1;
                                  }
                                  return parseInt(a.shotNum) - parseInt(b.shotNum);
                                });

                                return allShots.map(({ shotNum, conditioning, condVariants }) => {
                                  const minShot = condVariants.find(s => s.velocity_label === 'min') || condVariants[0];
                                  const targetShot = condVariants.find(s => s.velocity_label === 'target') || condVariants[0];
                                  const maxShot = condVariants.find(s => s.velocity_label === 'max') || condVariants[0];
                                  const validBfdValues = condVariants.map(s => s.predicted_bfd_mm).filter(v => v !== null);
                                  const maxBfd = validBfdValues.length > 0 ? Math.max(...validBfdValues) : null;
                                  const tolerance = targetShot.velocity_m_s - minShot.velocity_m_s;

                                  return (
                                    <tr key={`${shotNum}-${conditioning}`} className="border-b">
                                      <td className="px-4 py-2 text-sm">{shotNum}</td>
                                      <td className={`px-4 py-2 text-sm capitalize ${conditioning === 'dry' ? 'bg-orange-50' : 'bg-blue-50'}`}>
                                        {conditioning}
                                      </td>
                                      <td className="px-4 py-2 text-sm text-xs text-gray-500">
                                        {Math.round(targetShot.velocity_m_s)} ± {tolerance > 0 ? Math.round(tolerance) : 0}
                                      </td>
                                      <td className={`px-4 py-2 text-sm font-medium ${minShot.predicted_bfd_mm !== null && minShot.predicted_bfd_mm === maxBfd ? 'font-black' : ''}`}>
                                        {minShot.predicted_bfd_mm !== null ? minShot.predicted_bfd_mm.toFixed(2) : 'PERFORATED'}
                                      </td>
                                      <td className={`px-4 py-2 text-sm font-medium ${targetShot.predicted_bfd_mm !== null && targetShot.predicted_bfd_mm === maxBfd ? 'font-black' : ''}`}>
                                        {targetShot.predicted_bfd_mm !== null ? targetShot.predicted_bfd_mm.toFixed(2) : 'PERFORATED'}
                                      </td>
                                      <td className={`px-4 py-2 text-sm font-medium ${maxShot.predicted_bfd_mm !== null && maxShot.predicted_bfd_mm === maxBfd ? 'font-black' : ''}`}>
                                        {maxShot.predicted_bfd_mm !== null ? maxShot.predicted_bfd_mm.toFixed(2) : 'PERFORATED'}
                                      </td>
                                      <td className="px-4 py-2 text-sm">
                                        {targetShot.perforation_probability !== null && targetShot.perforation_probability !== undefined
                                          ? `${(targetShot.perforation_probability * 100).toFixed(1)}%`
                                          : 'N/A'}
                                      </td>
                                      <td className="px-4 py-2 text-sm">
                                        {targetShot.confidence_interval_low_mm !== null && targetShot.confidence_interval_high_mm !== null
                                          ? `${targetShot.confidence_interval_low_mm.toFixed(2)} - ${targetShot.confidence_interval_high_mm.toFixed(2)}`
                                            : 'N/A'}
                                      </td>
                                    </tr>
                                  );
                                });
                              })()}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </div>
                  ));
                })()}
              </div>
            </div>

            {/* BFD vs Velocity Chart */}
            {prediction.velocity_curves && (() => {
              // Group velocity curves by ammunition
              const curvesByAmmo: Record<string, Record<string, any[]>> = {};
              Object.entries(prediction.velocity_curves).forEach(([shotNum, curve]) => {
                if (curve.length > 0 && curve[0].ammunition_name) {
                  const ammoName = curve[0].ammunition_name;
                  if (!curvesByAmmo[ammoName]) {
                    curvesByAmmo[ammoName] = {};
                  }
                  curvesByAmmo[ammoName][shotNum] = curve;
                }
              });

              const ammoGraphs: JSX.Element[] = [];
              Object.entries(curvesByAmmo).forEach(([ammoName, shots]) => {
                ammoGraphs.push(
                  <div key={ammoName} className="mb-6">
                    <h3 className="font-semibold text-blue-800 mb-2 bg-gray-100 px-3 py-2 rounded">{ammoName} - BFD vs Velocity Curve</h3>
                    <div className="border border-gray-200 rounded p-4">
                      <Plot
                        data={Object.entries(shots).map(([shotNum, curve]) => ({
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
                );
              });
              return ammoGraphs;
            })()}
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
    </div>
  );
}
