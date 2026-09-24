import { useState, useEffect } from 'react';
import { X, Plus, Trash2 } from 'lucide-react';
import { useMaterials } from '../hooks/useMaterials';
import { useGeometries } from '../hooks/useGeometries';
import { VestCreate, VestLayerCreate } from '../api/vests';
import { apiClient } from '../api/client';

interface ProtocolThreatLevel {
  protocol_id: string;
  protocol_name: string;
  threat_levels: string[];
}

interface VestFormModalProps {
  onSave: (vest: VestCreate) => void;
  onCancel: () => void;
  initialValues?: Partial<VestCreate>;
}

const emptyForm: VestCreate = {
  vest_code: '',
  vest_type: '',
  is_female: false,
  threat_level: '',
  total_layers: null,
  total_thickness_mm: null,
  sizes: {},
  construction_notes: '',
  compatible_geometry_ids: [],
  weight_g: null,
  flexibility_rating: false,
  is_panel_sewn: false,
  is_catalog_model: false,
  notes: '',
  layers: [],
};

export function VestFormModal({ onSave, onCancel, initialValues }: VestFormModalProps) {
  const { data: materials } = useMaterials();
  const { data: geometries } = useGeometries();
  const [formData, setFormData] = useState<VestCreate>({ ...emptyForm, ...initialValues });
  const [layers, setLayers] = useState<VestLayerCreate[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [protocolThreatLevels, setProtocolThreatLevels] = useState<ProtocolThreatLevel[]>([]);
  const [calcWeight, setCalcWeight] = useState<{ size: string; geometryId: string | null }>({ size: 'M', geometryId: null });
  const [calcWeightResult, setCalcWeightResult] = useState<string | null>(null);

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

  const addLayer = () => {
    setLayers([...layers, { layer_index: layers.length, material_id: null, layer_count: 1, notes: '' }]);
  };

  const updateLayer = (index: number, field: keyof VestLayerCreate, value: any) => {
    const updated = [...layers];
    updated[index] = { ...updated[index], [field]: value };
    setLayers(updated);
  };

  const removeLayer = (index: number) => {
    setLayers(layers.filter((_, i) => i !== index).map((l, i) => ({ ...l, layer_index: i })));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const totalLayerCount = layers.reduce((sum, l) => sum + (l.layer_count || 0), 0);
    if (formData.total_layers && totalLayerCount !== formData.total_layers) {
      setValidationError(`Total layers (${formData.total_layers}) must equal sum of individual layer counts (${totalLayerCount})`);
      return;
    }
    let calculatedThickness = formData.total_thickness_mm;
    if (!calculatedThickness && layers.length > 0 && materials) {
      calculatedThickness = layers.reduce((sum, layer) => {
        const material = materials.find((m) => m.id === layer.material_id);
        if (material?.thickness_mm && layer.layer_count) {
          return sum + material.thickness_mm * layer.layer_count;
        }
        return sum;
      }, 0);
    }
    onSave({ ...formData, layers, total_thickness_mm: calculatedThickness });
  };

  const handleCalcWeight = () => {
    setCalcWeightResult(null);
    const geoId = calcWeight.geometryId || formData.compatible_geometry_ids?.[0];
    if (!geoId) {
      setCalcWeightResult('No geometry selected. Assign a compatible geometry or pick one above.');
      return;
    }
    const geo = geometries?.find((g) => g.id === geoId);
    if (!geo) {
      setCalcWeightResult('Geometry not found.');
      return;
    }
    const sizeAreas = geo.surface_areas?.[calcWeight.size];
    if (!sizeAreas) {
      const available = Object.keys(geo.surface_areas || {});
      setCalcWeightResult(`Size '${calcWeight.size}' not in geometry '${geo.name}'. Available: ${available.join(', ')}`);
      return;
    }
    const totalArea = Number(sizeAreas.front || 0) + Number(sizeAreas.back || 0);
    if (totalArea <= 0) {
      setCalcWeightResult(`Geometry '${geo.name}' size '${calcWeight.size}' has no surface area defined.`);
      return;
    }
    const missing: string[] = [];
    let totalWeight = 0;
    for (const layer of layers) {
      if (!layer.material_id) continue;
      const mat = materials?.find((m) => m.id === layer.material_id);
      if (!mat) continue;
      if (!mat.areal_density_g_m2) {
        missing.push(mat.name);
        continue;
      }
      totalWeight += Number(mat.areal_density_g_m2) * (layer.layer_count || 1) * totalArea;
    }
    if (missing.length > 0) {
      setCalcWeightResult(`Cannot calculate: missing areal_density_g_m2 for: ${missing.join(', ')}`);
      return;
    }
    const rounded = Math.round(totalWeight * 100) / 100;
    setFormData({ ...formData, weight_g: rounded });
    setCalcWeightResult(`Auto-calculated: ${rounded} g (${geo.name}, size ${calcWeight.size})`);
  };

  const isSoft = formData.vest_type?.toLowerCase() === 'soft';

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="text-lg font-semibold text-gray-900">Create New Vest</h2>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {validationError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-md text-sm">
              {validationError}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Vest Name *</label>
              <input
                type="text"
                required
                value={formData.vest_code}
                onChange={(e) => setFormData({ ...formData, vest_code: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Vest Type *</label>
              <select
                value={formData.vest_type || ''}
                onChange={(e) => setFormData({ ...formData, vest_type: e.target.value })}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              >
                <option value="">Select type...</option>
                <option value="Soft">Soft</option>
                <option value="Hard">Hard</option>
                <option value="IWC">IWC</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Threat Level *</label>
              <select
                value={formData.threat_level || ''}
                onChange={(e) => setFormData({ ...formData, threat_level: e.target.value })}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              >
                <option value="">Select level...</option>
                {protocolThreatLevels.map((protocol) => (
                  <optgroup key={protocol.protocol_id} label={protocol.protocol_name}>
                    {protocol.threat_levels.map((level) => (
                      <option key={level} value={level}>{level}</option>
                    ))}
                  </optgroup>
                ))}
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Total Layers *</label>
              <input
                type="number"
                value={formData.total_layers ?? ''}
                onChange={(e) => setFormData({ ...formData, total_layers: e.target.value ? parseInt(e.target.value) : null })}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">Weight (g)</label>
              <div className="flex items-end gap-2">
                <input
                  type="number"
                  step="0.01"
                  value={formData.weight_g ?? ''}
                  onChange={(e) => setFormData({ ...formData, weight_g: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
                <div className="flex flex-col">
                  <label className="block text-xs font-medium text-gray-500 mb-1">Auto-Calc</label>
                  <div className="flex items-center gap-1">
                    <select
                      value={calcWeight.geometryId || ''}
                      onChange={(e) => setCalcWeight({ ...calcWeight, geometryId: e.target.value || null })}
                      className="text-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-1"
                    >
                      <option value="">Auto</option>
                      {geometries?.map((geo) => (
                        <option key={geo.id} value={geo.id}>{geo.name}</option>
                      ))}
                    </select>
                    <select
                      value={calcWeight.size}
                      onChange={(e) => setCalcWeight({ ...calcWeight, size: e.target.value })}
                      className="text-xs rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 border p-1"
                    >
                      {['XS', 'S', 'M', 'L', 'XL', 'XXL'].map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleCalcWeight}
                      className="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 whitespace-nowrap"
                    >
                      Calc
                    </button>
                  </div>
                </div>
              </div>
              {calcWeightResult && (
                <p className={`text-xs mt-1 ${calcWeightResult.startsWith('Auto-calculated') ? 'text-green-700' : 'text-red-600'}`}>
                  {calcWeightResult}
                </p>
              )}
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Compatible Geometries</label>
              <div className="flex flex-wrap gap-2">
                {geometries?.map((geo) => (
                  <label key={geo.id} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.compatible_geometry_ids?.includes(geo.id) || false}
                      onChange={(e) => {
                        const current = formData.compatible_geometry_ids || [];
                        setFormData({
                          ...formData,
                          compatible_geometry_ids: e.target.checked
                            ? [...current, geo.id]
                            : current.filter((id) => id !== geo.id),
                        });
                      }}
                      className="mr-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                    />
                    <span className="text-sm text-gray-700">{geo.name}</span>
                  </label>
                ))}
              </div>
            </div>

            {isSoft && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Flexibility</label>
                  <label className="flex items-center mt-1">
                    <input
                      type="checkbox"
                      checked={formData.flexibility_rating || false}
                      onChange={(e) => setFormData({ ...formData, flexibility_rating: e.target.checked })}
                      className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                    />
                    <span className="text-sm text-gray-700">Yes</span>
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Female Vest</label>
                  <label className="flex items-center mt-1">
                    <input
                      type="checkbox"
                      checked={formData.is_female || false}
                      onChange={(e) => setFormData({ ...formData, is_female: e.target.checked })}
                      className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                    />
                    <span className="text-sm text-gray-700">Is Female Vest</span>
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Stitched</label>
                  <label className="flex items-center mt-1">
                    <input
                      type="checkbox"
                      checked={formData.is_panel_sewn || false}
                      onChange={(e) => setFormData({ ...formData, is_panel_sewn: e.target.checked })}
                      className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                    />
                    <span className="text-sm text-gray-700">Stitched</span>
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Catalog Model</label>
                  <label className="flex items-center mt-1">
                    <input
                      type="checkbox"
                      checked={formData.is_catalog_model || false}
                      onChange={(e) => setFormData({ ...formData, is_catalog_model: e.target.checked })}
                      className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                    />
                    <span className="text-sm text-gray-700">Official catalog model</span>
                  </label>
                </div>
              </>
            )}

            {!isSoft && formData.vest_type && (
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700">Catalog Model</label>
                <label className="flex items-center mt-1">
                  <input
                    type="checkbox"
                    checked={formData.is_catalog_model || false}
                    onChange={(e) => setFormData({ ...formData, is_catalog_model: e.target.checked })}
                    className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                  />
                  <span className="text-sm text-gray-700">Official catalog model (shows in compatibility & matching)</span>
                </label>
              </div>
            )}

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700">Notes</label>
              <textarea
                value={formData.notes || ''}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={2}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
          </div>

          <div className="border-t pt-4">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-md font-medium text-gray-900">Layers</h3>
              <button
                type="button"
                onClick={addLayer}
                className="px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm inline-flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> Add Layer
              </button>
            </div>
            {layers.map((layer, index) => (
              <div key={index} className="bg-gray-50 p-3 rounded-md mb-2">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">Layer {index + 1}</span>
                  <button
                    type="button"
                    onClick={() => removeLayer(index)}
                    className="text-red-600 hover:text-red-900 text-sm inline-flex items-center gap-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Remove
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
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
                      value={layer.layer_count ?? ''}
                      onChange={(e) => updateLayer(index, 'layer_count', e.target.value === '' ? '' : parseInt(e.target.value))}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700">Layer Notes</label>
                    <input
                      type="text"
                      value={layer.notes || ''}
                      onChange={(e) => updateLayer(index, 'notes', e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Save Vest
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
