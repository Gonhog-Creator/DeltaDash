import { useState, Fragment } from 'react';
import { apiClient } from '../api/client';
import { useMaterials } from '../hooks/useMaterials';
import { useProtocols } from '../hooks/useProtocols';
import { exportRecommendationsPdf } from '../utils/recommendationsPdfExport';

interface Recommendation {
  composition: string;
  vest_type: string;
  total_layers: number;
  source: string;
  source_detail: string;
  predicted_mean_bfd_mm: number;
  predicted_max_bfd_mm: number;
  predicted_min_bfd_mm: number;
  max_perforation_probability: number;
  extrapolation_warning: boolean;
  out_of_range_features: string[];
  ci_width_mm: number;
  feature_space_distance: number;
  comparable_training_shots: number;
  scores: {
    uncertainty: number;
    distance: number;
    sparsity: number;
    practical: number;
    composite: number;
  };
  reason: string;
  layers: Array<{
    material_id: string;
    material_name: string;
    material_class: string | null;
    layer_count: number;
    layer_index: number;
  }>;
  prediction_summary: {
    mean_bfd_mm: number | null;
    max_bfd_mm: number | null;
    min_bfd_mm: number | null;
    std_bfd_mm: number | null;
  };
}

interface RecommendTestsResponse {
  recommendations: Recommendation[];
  summary: {
    total_candidates_generated: number;
    total_candidates_scored: number;
    returned: number;
    model_version: string;
    protocol_id: string;
  };
}

interface TestPlannerTabProps {
  selectedModelVersion: string;
  modelVersions: Array<{ version: string; model_name?: string }>;
  onError: (error: string) => void;
}

export function TestPlannerTab({ selectedModelVersion, modelVersions, onError }: TestPlannerTabProps) {
  const { data: materials } = useMaterials();
  const { data: protocols } = useProtocols();

  const [selectedProtocolId, setSelectedProtocolId] = useState('');
  const [vestType, setVestType] = useState('soft');
  const [maxLayers, setMaxLayers] = useState(60);
  const [maxCandidates, setMaxCandidates] = useState(20);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [includeSwapVariants, setIncludeSwapVariants] = useState(true);
  const [includeLayerVariants, setIncludeLayerVariants] = useState(true);
  const [includeUserConstrained, setIncludeUserConstrained] = useState(true);

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<RecommendTestsResponse | null>(null);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const handleGenerate = async () => {
    if (!selectedProtocolId) {
      onError('Please select a protocol');
      return;
    }

    setLoading(true);
    onError('');
    try {
      const requestBody: any = {
        protocol_id: selectedProtocolId,
        version: selectedModelVersion || undefined,
        vest_type: vestType,
        max_layers: maxLayers,
        max_candidates: maxCandidates,
        include_swap_variants: includeSwapVariants,
        include_layer_variants: includeLayerVariants,
        include_user_constrained: includeUserConstrained,
      };

      if (selectedMaterialIds.length > 0) {
        requestBody.selected_material_ids = selectedMaterialIds;
      }

      const result = await apiClient.post<RecommendTestsResponse>('/api/v1/ballistic/recommend-tests', requestBody);
      setResults(result);
    } catch (err: any) {
      onError(err.detail || err.message || 'Failed to generate recommendations');
    } finally {
      setLoading(false);
    }
  };

  const toggleMaterial = (materialId: string) => {
    setSelectedMaterialIds(prev => {
      if (prev.includes(materialId)) {
        return prev.filter(id => id !== materialId);
      }
      return [...prev, materialId];
    });
  };

  const getScoreColor = (score: number) => {
    if (score >= 0.7) return 'bg-red-100 text-red-800';
    if (score >= 0.5) return 'bg-orange-100 text-orange-800';
    if (score >= 0.3) return 'bg-yellow-100 text-yellow-800';
    return 'bg-green-100 text-green-800';
  };

  return (
    <div className="space-y-6">
      {/* Configuration Panel */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Test Planner Configuration</h2>
        <p className="text-sm text-gray-600 mb-4">
          Generate ranked recommendations for which vest configuration to physically test next.
          The model identifies regions of the design space where it is most uncertain and recommends
          configurations that would maximally improve its predictive accuracy.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Protocol Selection */}
          <div>
            <label className="block text-sm font-medium mb-1">Protocol *</label>
            <select
              value={selectedProtocolId}
              onChange={(e) => setSelectedProtocolId(e.target.value)}
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

          {/* Model Version */}
          <div>
            <label className="block text-sm font-medium mb-1">Model Version</label>
            <select
              value={selectedModelVersion}
              onChange={() => {}}
              className="w-full border rounded p-2 bg-gray-100"
              disabled
            >
              <option value={selectedModelVersion}>
                {modelVersions.find(v => v.version === selectedModelVersion)?.model_name || selectedModelVersion || 'Latest'}
              </option>
            </select>
            <p className="text-xs text-gray-500 mt-1">Uses the model version selected on the Training tab</p>
          </div>

          {/* Vest Type */}
          <div>
            <label className="block text-sm font-medium mb-1">Vest Type</label>
            <select
              value={vestType}
              onChange={(e) => setVestType(e.target.value)}
              className="w-full border rounded p-2"
            >
              <option value="soft">Soft Armor</option>
              <option value="hard">Hard Armor</option>
              <option value="hybrid">Hybrid</option>
            </select>
          </div>

          {/* Max Layers */}
          <div>
            <label className="block text-sm font-medium mb-1">Max Layers: {maxLayers}</label>
            <input
              type="range"
              min={10}
              max={200}
              step={5}
              value={maxLayers}
              onChange={(e) => setMaxLayers(parseInt(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Max Candidates */}
          <div>
            <label className="block text-sm font-medium mb-1">Max Recommendations: {maxCandidates}</label>
            <input
              type="range"
              min={5}
              max={100}
              step={5}
              value={maxCandidates}
              onChange={(e) => setMaxCandidates(parseInt(e.target.value))}
              className="w-full"
            />
          </div>
        </div>

        {/* Candidate Generation Strategies */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Candidate Generation Strategies</label>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={includeSwapVariants}
                onChange={(e) => setIncludeSwapVariants(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Material Swap Variants</span>
            </label>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={includeLayerVariants}
                onChange={(e) => setIncludeLayerVariants(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Layer Count Variations</span>
            </label>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={includeUserConstrained}
                onChange={(e) => setIncludeUserConstrained(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">User-Constrained Generation</span>
            </label>
          </div>
        </div>

        {/* Material Filter */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">
            Filter by Available Materials (optional — leave empty to use all)
          </label>
          <div className="max-h-40 overflow-y-auto border rounded p-3 bg-gray-50">
            {materials?.map((material) => (
              <label key={material.id} className="flex items-center space-x-2 py-0.5">
                <input
                  type="checkbox"
                  checked={selectedMaterialIds.includes(material.id)}
                  onChange={() => toggleMaterial(material.id)}
                  className="rounded"
                />
                <span className="text-sm">
                  {material.name} ({material.material_class || 'N/A'})
                </span>
              </label>
            ))}
          </div>
          {selectedMaterialIds.length > 0 && (
            <button
              onClick={() => setSelectedMaterialIds([])}
              className="text-xs text-indigo-600 hover:text-indigo-800 mt-1"
            >
              Clear selection ({selectedMaterialIds.length} selected)
            </button>
          )}
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading || !selectedProtocolId}
          className="w-full bg-indigo-600 text-white py-2 px-4 rounded hover:bg-indigo-700 disabled:bg-gray-400"
        >
          {loading ? 'Generating Recommendations...' : 'Generate Test Recommendations'}
        </button>
      </div>

      {/* Results Summary */}
      {results && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Recommendations</h2>
            <div className="flex items-center gap-4">
              <div className="text-sm text-gray-600">
                {results.summary.total_candidates_generated} candidates generated →{' '}
                {results.summary.total_candidates_scored} scored →{' '}
                <strong>{results.summary.returned} shown</strong>
                <span className="ml-2 text-gray-400">| Model: {results.summary.model_version}</span>
              </div>
              <button
                onClick={() => exportRecommendationsPdf(results)}
                className="bg-indigo-600 text-white text-sm py-1.5 px-4 rounded hover:bg-indigo-700 whitespace-nowrap"
              >
                Export PDF
              </button>
            </div>
          </div>

          {results.recommendations.length === 0 ? (
            <p className="text-sm text-gray-600">
              No recommendations generated. Try adjusting the configuration or enabling more candidate generation strategies.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">#</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Composition</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Layers</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pred. BFD (mm)</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Perf. Prob</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Test Value</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Why?</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Source</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {results.recommendations.map((rec, index) => (
                    <Fragment key={index}>
                      <tr
                        onClick={() => setExpandedRow(expandedRow === index ? null : index)}
                        className="cursor-pointer hover:bg-gray-50"
                      >
                        <td className="px-4 py-3 text-sm text-gray-900 font-medium">{index + 1}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 font-mono">{rec.composition}</td>
                        <td className="px-4 py-3 text-sm text-gray-600 capitalize">{rec.vest_type}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">{rec.total_layers}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          <div>{rec.predicted_mean_bfd_mm?.toFixed(1)} <span className="text-gray-400 text-xs">mean</span></div>
                          <div className="text-xs text-gray-500">{rec.predicted_min_bfd_mm?.toFixed(1)}–{rec.predicted_max_bfd_mm?.toFixed(1)}</div>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span className={rec.max_perforation_probability > 0.5 ? 'text-red-600 font-medium' : 'text-gray-600'}>
                            {(rec.max_perforation_probability * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`px-2 py-1 rounded text-xs font-bold ${getScoreColor(rec.scores.composite)}`}>
                            {rec.scores.composite.toFixed(3)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-600 max-w-xs truncate" title={rec.reason}>
                          {rec.extrapolation_warning && (
                            <span className="inline-block bg-orange-100 text-orange-800 text-xs px-1.5 py-0.5 rounded mr-1 font-medium" title={`Out of range: ${rec.out_of_range_features.join(', ')}`}>
                              ⚠
                            </span>
                          )}
                          {rec.reason}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">
                          {rec.source === 'material_swap' ? 'Swap' : rec.source === 'layer_count_variation' ? 'Layers' : 'Custom'}
                        </td>
                      </tr>
                      {expandedRow === index && (
                        <tr className="bg-gray-50">
                          <td colSpan={9} className="px-8 py-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                              {/* Score Breakdown */}
                              <div>
                                <h4 className="font-medium text-gray-800 mb-2">Score Breakdown</h4>
                                <div className="space-y-2">
                                  <ScoreBar label="Uncertainty" value={rec.scores.uncertainty} />
                                  <ScoreBar label="Feature Distance" value={rec.scores.distance} />
                                  <ScoreBar label="Data Sparsity" value={rec.scores.sparsity} />
                                  <ScoreBar label="Practical Relevance" value={rec.scores.practical} />
                                  <div className="pt-2 border-t">
                                    <ScoreBar label="Composite" value={rec.scores.composite} bold />
                                  </div>
                                </div>
                              </div>

                              {/* Prediction Details */}
                              <div>
                                <h4 className="font-medium text-gray-800 mb-2">Prediction Details</h4>
                                <div className="text-sm space-y-1 text-gray-600">
                                  <div><strong>Predicted Mean BFD:</strong> {rec.predicted_mean_bfd_mm?.toFixed(2)} mm</div>
                                  <div><strong>Predicted Max BFD:</strong> {rec.predicted_max_bfd_mm?.toFixed(2)} mm</div>
                                  <div><strong>CI Width:</strong> ±{rec.ci_width_mm / 2} mm</div>
                                  <div><strong>Max Perforation Prob:</strong> {(rec.max_perforation_probability * 100).toFixed(1)}%</div>
                                  <div><strong>Feature Space Distance:</strong> {rec.feature_space_distance.toFixed(3)}</div>
                                  <div><strong>Comparable Training Shots:</strong> {rec.comparable_training_shots}</div>
                                  {rec.extrapolation_warning && (
                                    <div className="text-orange-700 bg-orange-50 rounded p-2 mt-2">
                                      <strong>⚠ Extrapolation Warning:</strong> Features outside training range:
                                      <ul className="list-disc list-inside ml-2 mt-1">
                                        {rec.out_of_range_features.map(f => (
                                          <li key={f} className="text-xs">{f}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Layer Details */}
                              <div className="md:col-span-2">
                                <h4 className="font-medium text-gray-800 mb-2">Vest Composition Details</h4>
                                <div className="text-sm text-gray-600 mb-2">
                                  <strong>Source:</strong> {rec.source_detail}
                                </div>
                                <table className="min-w-full border border-gray-200 rounded">
                                  <thead className="bg-gray-100">
                                    <tr>
                                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Layer Index</th>
                                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Material</th>
                                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Class</th>
                                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-600">Count</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {rec.layers.map((layer, i) => (
                                      <tr key={i} className="border-t">
                                        <td className="px-3 py-2 text-sm">{layer.layer_index}</td>
                                        <td className="px-3 py-2 text-sm font-medium">{layer.material_name}</td>
                                        <td className="px-3 py-2 text-sm text-gray-600">{layer.material_class || 'N/A'}</td>
                                        <td className="px-3 py-2 text-sm">{layer.layer_count}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>

                              {/* Reason */}
                              <div className="md:col-span-2">
                                <h4 className="font-medium text-gray-800 mb-2">Why This Test?</h4>
                                <p className="text-sm text-gray-600">{rec.reason}</p>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ScoreBar({ label, value, bold }: { label: string; value: number; bold?: boolean }) {
  return (
    <div className="flex items-center space-x-3">
      <span className={`text-sm ${bold ? 'font-bold' : 'text-gray-600'} w-32`}>{label}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full ${bold ? 'bg-indigo-600' : 'bg-indigo-400'}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className={`text-xs ${bold ? 'font-bold' : 'text-gray-600'} w-12 text-right`}>
        {value.toFixed(3)}
      </span>
    </div>
  );
}
