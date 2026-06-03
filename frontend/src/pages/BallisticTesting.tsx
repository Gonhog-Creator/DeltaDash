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
    if (!selectedVestId) {
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
      const result = await apiClient.post<PredictionResponse>(
        `/api/v1/ballistic/predict-protocol?version=${selectedVersion}`,
        {
          vest_id: selectedVestId,
          protocol_id: selectedProtocolId,
          level_index: selectedLevelIndex,
        }
      );
      setPrediction(result);
    } catch (err: any) {
      const errorMessage = err.detail || 'Prediction failed';
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Vest Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">Vest</label>
              <select
                value={selectedVestId}
                onChange={(e) => setSelectedVestId(e.target.value)}
                className="w-full border rounded p-2"
              >
                <option value="">Select vest...</option>
                {vests?.map((vest) => (
                  <option key={vest.id} value={vest.id}>
                    {vest.vest_code || vest.name} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                  </option>
                ))}
              </select>
            </div>

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
                  <span className="text-gray-600">Mean BFD:</span>
                  <span className="ml-2 font-medium">{prediction.summary.mean_bfd_mm.toFixed(2)} mm</span>
                </div>
                <div>
                  <span className="text-gray-600">Max BFD:</span>
                  <span className="ml-2 font-medium">{prediction.summary.max_bfd_mm.toFixed(2)} mm</span>
                </div>
                <div>
                  <span className="text-gray-600">Min BFD:</span>
                  <span className="ml-2 font-medium">{prediction.summary.min_bfd_mm.toFixed(2)} mm</span>
                </div>
                <div>
                  <span className="text-gray-600">Std Dev:</span>
                  <span className="ml-2 font-medium">{prediction.summary.std_bfd_mm.toFixed(2)} mm</span>
                </div>
              </div>
            </div>

            {/* Detailed Predictions Table */}
            <div className="mb-6">
              <h3 className="font-semibold text-blue-800 mb-2">Detailed Predictions</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Shot #</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Side</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Conditioning</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Ammunition</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Velocity (m/s)</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Predicted BFD (mm)</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">95% CI (mm)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {prediction.predictions.map((shot) => (
                      <tr key={`${shot.shot_number}-${shot.side}-${shot.conditioning}`} className="border-b">
                        <td className="px-4 py-2 text-sm">{shot.shot_number}</td>
                        <td className="px-4 py-2 text-sm capitalize">{shot.side}</td>
                        <td className="px-4 py-2 text-sm capitalize">{shot.conditioning}</td>
                        <td className="px-4 py-2 text-sm">{shot.ammunition_name}</td>
                        <td className="px-4 py-2 text-sm">{shot.reference_velocity_m_s.toFixed(1)}</td>
                        <td className="px-4 py-2 text-sm font-medium">{shot.predicted_bfd_mm.toFixed(2)}</td>
                        <td className="px-4 py-2 text-sm">{shot.confidence_interval_low_mm.toFixed(2)} - {shot.confidence_interval_high_mm.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* BFD vs Velocity Chart */}
            {prediction.velocity_curves && (
              <div className="mb-6">
                <h3 className="font-semibold text-blue-800 mb-2">BFD vs Velocity Curve (All Shots)</h3>
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
            )}
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
