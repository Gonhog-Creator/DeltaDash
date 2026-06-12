import { useState, useEffect, useCallback } from 'react';
import { useGeometries, Geometry } from '../hooks/useGeometries';
import { useVests } from '../hooks/useVests';
import { useMaterials } from '../hooks/useMaterials';
import { 
  useGeometryMaterialConfigs, 
  GeometryMaterialConfig, 
  GeometryMaterialConfigCreate,
  useCreateGeometryMaterialConfig,
  useUpdateGeometryMaterialConfig,
  useDeleteGeometryMaterialConfig
} from '../hooks/useGeometryMaterialConfigs';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface MaterialRequirement {
  material_id: string;
  material_name: string;
  area_m2: number;
  weight_kg: number;
  cost: number | null;
  roll_count: number | null;
}

interface FabricCalculationResponse {
  total_fabric_area_m2: number;
  total_weight_kg: number;
  total_cost: number | null;
  efficiency_factor: number;
  quantity: number;
  size: string;
  geometry_name: string;
  by_material: MaterialRequirement[];
  breakdown: {
    geometry: {
      name: string;
      vest_type: string;
      size: string;
      front_area_m2: number;
      back_area_m2: number;
      total_panel_area_m2: number;
    };
    production: {
      quantity: number;
      efficiency_factor: number;
      includes_hard_plates: boolean;
    };
    layers: Array<{
      material_id: string;
      layer_count: number;
    }>;
  };
}

export function FabricEstimation() {
  const { data: geometries } = useGeometries();
  const { data: vests } = useVests();
  const { data: materials } = useMaterials();
  const { isAdmin, role } = useAuth();
  const { data: materialConfigs, refetch: refetchConfigs } = useGeometryMaterialConfigs();
  const createConfigMutation = useCreateGeometryMaterialConfig();
  const updateConfigMutation = useUpdateGeometryMaterialConfig();
  const deleteConfigMutation = useDeleteGeometryMaterialConfig();

  const [activeTab, setActiveTab] = useState<'calculator' | 'configuration'>('calculator');
  const [selectedVestId, setSelectedVestId] = useState<string>('');
  const [selectedGeometryId, setSelectedGeometryId] = useState<string>('');
  const [selectedSize, setSelectedSize] = useState<string>('');
  const [quantity, setQuantity] = useState<number>(1);
  const [efficiencyFactor, setEfficiencyFactor] = useState<number>(1.15);
  const [calculation, setCalculation] = useState<FabricCalculationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom Vest State
  const [useCustomVest, setUseCustomVest] = useState(false);
  const [customVestLayers, setCustomVestLayers] = useState<Array<{material_id: string; layer_count: number}>>([]);

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

  const handleCalculate = useCallback(async () => {
    if (!selectedGeometryId) {
      setError('Please select a geometry');
      return;
    }
    if (!selectedSize) {
      setError('Please select a size');
      return;
    }
    if (!useCustomVest && !selectedVestId) {
      setError('Please select a vest or build a custom vest');
      return;
    }
    if (quantity < 1) {
      setError('Quantity must be at least 1');
      return;
    }

    setLoading(true);
    setError(null);
    setCalculation(null);

    try {
      const requestBody: any = {
        geometry_id: selectedGeometryId,
        size: selectedSize,
        quantity: quantity,
        efficiency_factor: efficiencyFactor,
      };

      if (useCustomVest) {
        requestBody.custom_vest = {
          layers: customVestLayers,
        };
      } else {
        requestBody.vest_id = selectedVestId;
      }

      const result = await apiClient.post<FabricCalculationResponse>(
        '/api/v1/fabric-estimation/calculate',
        requestBody
      );
      setCalculation(result);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Calculation failed';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [selectedGeometryId, selectedSize, quantity, efficiencyFactor, useCustomVest, selectedVestId, customVestLayers]);

  // Auto-calculate when inputs change
  useEffect(() => {
    if (selectedGeometryId && selectedSize && quantity >= 1 && (!useCustomVest || customVestLayers.length > 0)) {
      handleCalculate();
    }
  }, [selectedGeometryId, selectedSize, quantity, efficiencyFactor, useCustomVest, selectedVestId, customVestLayers, handleCalculate]);

  const selectedGeometry = geometries?.find(g => g.id === selectedGeometryId);
  const availableSizes = selectedGeometry?.available_sizes || [];

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Fabric Estimation</h1>

      {/* Tab Navigation */}
      <div className="mb-6 border-b">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('calculator')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'calculator'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Calculator
          </button>
          {isAdmin && (
            <button
              onClick={() => setActiveTab('configuration')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'configuration'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Configuration
            </button>
          )}
        </nav>
      </div>

      <div className="space-y-6">
        {activeTab === 'calculator' ? (
          <>
        {/* Input Form */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Input Parameters</h2>

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
                      {vest.vest_code || vest.name} - {vest.vest_type || 'N/A'}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Custom Vest Form */}
            {useCustomVest && (
              <div className="lg:col-span-2 space-y-4">
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
                </div>
              </div>
            )}

            {/* Geometry Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">Geometry</label>
              <select
                value={selectedGeometryId}
                onChange={(e) => {
                  setSelectedGeometryId(e.target.value);
                  setSelectedSize('');
                }}
                className="w-full border rounded p-2"
              >
                <option value="">Select geometry...</option>
                {geometries?.map((geometry) => (
                  <option key={geometry.id} value={geometry.id}>
                    {geometry.name} {geometry.vest_type ? `(${geometry.vest_type})` : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Size Selection */}
            <div>
              <label className="block text-sm font-medium mb-1">Size</label>
              <select
                value={selectedSize}
                onChange={(e) => setSelectedSize(e.target.value)}
                className="w-full border rounded p-2"
                disabled={!selectedGeometryId}
              >
                <option value="">Select size...</option>
                {availableSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div>
              <label className="block text-sm font-medium mb-1">Quantity</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value === '' ? '' : parseInt(e.target.value))}
                className="w-full border rounded p-2"
                min={1}
              />
            </div>

            {/* Efficiency Factor */}
            <div>
              <label className="block text-sm font-medium mb-1">Efficiency Factor</label>
              <input
                type="number"
                step="0.01"
                value={efficiencyFactor}
                onChange={(e) => setEfficiencyFactor(e.target.value === '' ? 1.15 : parseFloat(e.target.value))}
                className="w-full border rounded p-2"
                min={1.0}
              />
              <p className="text-xs text-gray-500 mt-1">Default 1.15 (15% waste for soft armor)</p>
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={handleCalculate}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? 'Calculating...' : 'Calculate'}
            </button>
          </div>
        </div>

        {/* Calculation Results */}
        {calculation && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Calculation Results</h2>
            
            {/* Summary */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded">
              <h3 className="font-semibold text-blue-800 mb-2">Summary</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">Geometry:</span>
                  <span className="ml-2 font-medium">{calculation.geometry_name}</span>
                </div>
                <div>
                  <span className="text-gray-600">Size:</span>
                  <span className="ml-2 font-medium">{calculation.size}</span>
                </div>
                <div>
                  <span className="text-gray-600">Quantity:</span>
                  <span className="ml-2 font-medium">{calculation.quantity}</span>
                </div>
                <div>
                  <span className="text-gray-600">Efficiency:</span>
                  <span className="ml-2 font-medium">{calculation.efficiency_factor}</span>
                </div>
                <div>
                  <span className="text-gray-600">Total Area:</span>
                  <span className="ml-2 font-medium">{calculation.total_fabric_area_m2.toFixed(4)} m²</span>
                </div>
                <div>
                  <span className="text-gray-600">Total Weight:</span>
                  <span className="ml-2 font-medium">{calculation.total_weight_kg.toFixed(4)} kg</span>
                </div>
                <div>
                  <span className="text-gray-600">Total Cost:</span>
                  <span className="ml-2 font-medium">{calculation.total_cost ? `$${calculation.total_cost.toFixed(2)}` : 'N/A'}</span>
                </div>
              </div>
            </div>

            {/* Material Breakdown */}
            <div className="mb-6">
              <h3 className="font-semibold text-blue-800 mb-2">Material Breakdown</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Material</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Area (m²)</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Rolls</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Weight (kg)</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Cost</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {calculation.by_material.map((req) => (
                      <tr key={req.material_id} className="hover:bg-gray-50">
                        <td className="px-4 py-2 text-sm text-gray-900">{req.material_name}</td>
                        <td className="px-4 py-2 text-sm text-gray-500">{Math.ceil(req.area_m2)}</td>
                        <td className="px-4 py-2 text-sm text-gray-500">{req.roll_count !== null ? req.roll_count : 'N/A'}</td>
                        <td className="px-4 py-2 text-sm text-gray-500">{Math.ceil(req.weight_kg)}</td>
                        <td className="px-4 py-2 text-sm text-gray-500">{req.cost ? `$${req.cost.toFixed(2)}` : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Detailed Breakdown */}
            <div>
              <h3 className="font-semibold text-blue-800 mb-2">Detailed Breakdown</h3>
              <div className="bg-gray-50 p-4 rounded border">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Front Panel Area:</span>
                    <span className="ml-2 font-medium">{calculation.breakdown.geometry.front_area_m2.toFixed(4)} m²</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Back Panel Area:</span>
                    <span className="ml-2 font-medium">{calculation.breakdown.geometry.back_area_m2.toFixed(4)} m²</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Total Panel Area (per vest):</span>
                    <span className="ml-2 font-medium">{calculation.breakdown.geometry.total_panel_area_m2.toFixed(4)} m²</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Includes Hard Plates:</span>
                    <span className="ml-2 font-medium">{calculation.breakdown.production.includes_hard_plates ? 'Yes' : 'No'}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
          </>
        ) : (
          <ConfigurationTab
            geometries={geometries}
            materials={materials}
            materialConfigs={materialConfigs}
            refetchConfigs={refetchConfigs}
            createConfigMutation={createConfigMutation}
            updateConfigMutation={updateConfigMutation}
            deleteConfigMutation={deleteConfigMutation}
          />
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

function ConfigurationTab({
  geometries,
  materials,
  materialConfigs,
  refetchConfigs,
  createConfigMutation,
  updateConfigMutation,
  deleteConfigMutation
}: any) {
  const [selectedGeometryId, setSelectedGeometryId] = useState<string>('');
  const [selectedSize, setSelectedSize] = useState<string>('ALL');
  const [editingConfig, setEditingConfig] = useState<GeometryMaterialConfig | null>(null);
  const [showForm, setShowForm] = useState(false);

  const selectedGeometry = geometries?.find(g => g.id === selectedGeometryId);
  const availableSizes = selectedGeometry?.available_sizes || [];

  const filteredConfigs = materialConfigs?.filter(
    c => (!selectedGeometryId || c.geometry_id === selectedGeometryId) &&
           (selectedSize === 'ALL' || c.size === selectedSize)
  ) || [];

  const handleCreate = async (config: GeometryMaterialConfigCreate) => {
    try {
      await createConfigMutation.mutateAsync(config);
      setShowForm(false);
      refetchConfigs();
    } catch (error) {
      console.error('Failed to create config:', error);
    }
  };

  const handleUpdate = async (id: string, config: GeometryMaterialConfigCreate) => {
    try {
      await updateConfigMutation.mutateAsync({ id, config });
      setEditingConfig(null);
      refetchConfigs();
    } catch (error) {
      console.error('Failed to update config:', error);
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this configuration?')) {
      try {
        await deleteConfigMutation.mutateAsync(id);
        refetchConfigs();
      } catch (error) {
        console.error('Failed to delete config:', error);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Filter Configurations</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Geometry</label>
            <select
              value={selectedGeometryId}
              onChange={(e) => setSelectedGeometryId(e.target.value)}
              className="w-full border rounded p-2"
            >
              <option value="">All Geometries</option>
              {geometries?.map((g: Geometry) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Size</label>
            <select
              value={selectedSize}
              onChange={(e) => setSelectedSize(e.target.value)}
              className="w-full border rounded p-2"
            >
              <option value="ALL">All Sizes</option>
              {availableSizes.map((size: string) => (
                <option key={size} value={size}>{size}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={() => {
                setSelectedGeometryId('');
                setSelectedSize('ALL');
              }}
              className="w-full bg-gray-200 text-gray-700 py-2 px-4 rounded hover:bg-gray-300"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Configurations List */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Configurations ({filteredConfigs.length})</h2>
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
          >
            Add Configuration
          </button>
        </div>

        {filteredConfigs.length === 0 ? (
          <p className="text-gray-500 italic">No configurations found. Add one to get started.</p>
        ) : (
          <div className="space-y-4">
            {filteredConfigs.map((config: GeometryMaterialConfig) => (
              <div key={config.id} className="border rounded p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium">{config.geometry_name} - {config.size}</h3>
                  <div className="space-x-2">
                    <button
                      onClick={() => setEditingConfig(config)}
                      className="text-blue-600 hover:text-blue-900 text-sm"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(config.id)}
                      className="text-red-600 hover:text-red-900 text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="text-sm text-gray-600">
                  <p>Materials: {config.material_requirements.length} items</p>
                  <p>Accessories: {config.accessories.length} items</p>
                  {config.efficiency_factor && <p>Efficiency Factor: {config.efficiency_factor}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Form Modal */}
      {(showForm || editingConfig) && (
        <ConfigForm
          geometries={geometries}
          materials={materials}
          editingConfig={editingConfig}
          onSave={editingConfig ? (c) => handleUpdate(editingConfig.id, c) : handleCreate}
          onCancel={() => {
            setShowForm(false);
            setEditingConfig(null);
          }}
        />
      )}
    </div>
  );
}

function ConfigForm({ geometries, materials, editingConfig, onSave, onCancel }: any) {
  const [formData, setFormData] = useState<GeometryMaterialConfigCreate>(
    editingConfig || {
      geometry_id: '',
      size: 'ALL',
      material_requirements: [],  // Empty - ballistic materials are in Vest → VestLayer
      accessories: [],
      efficiency_factor: null,
      notes: ''
    }
  );

  const addAccessory = () => {
    setFormData({
      ...formData,
      accessories: [...formData.accessories, { material_id: '', quantity_per_vest: 1, unit: 'meters', notes: '' }]
    });
  };

  const removeAccessory = (index: number) => {
    setFormData({
      ...formData,
      accessories: formData.accessories.filter((_, i) => i !== index)
    });
  };

  const updateAccessory = (index: number, field: string, value: any) => {
    const updated = [...formData.accessories];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, accessories: updated });
  };

  const selectedGeometry = geometries?.find((g: Geometry) => g.id === formData.geometry_id);
  const availableSizes = selectedGeometry?.available_sizes || [];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold mb-4">
          {editingConfig ? 'Edit Configuration' : 'Add Configuration'}
        </h2>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Geometry</label>
              <select
                value={formData.geometry_id}
                onChange={(e) => setFormData({ ...formData, geometry_id: e.target.value })}
                className="w-full border rounded p-2"
                disabled={!!editingConfig}
              >
                <option value="">Select geometry...</option>
                {geometries?.map((g: Geometry) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Size</label>
              <select
                value={formData.size}
                onChange={(e) => setFormData({ ...formData, size: e.target.value })}
                className="w-full border rounded p-2"
                disabled={!!editingConfig}
              >
                <option value="ALL">All Sizes</option>
                {availableSizes.map((size: string) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Efficiency Factor</label>
            <input
              type="number"
              step="0.01"
              value={formData.efficiency_factor ?? ''}
              onChange={(e) => setFormData({ ...formData, efficiency_factor: e.target.value ? parseFloat(e.target.value) : null })}
              className="w-full border rounded p-2"
              placeholder="Default 1.15"
            />
          </div>

          {/* Accessories (Carrier Materials - Nylon, Velcro, Elastic, etc.) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium">Carrier/Accessories (nylon, velcro, elastic, etc.)</h3>
              <button
                type="button"
                onClick={addAccessory}
                className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
              >
                Add Accessory
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-2">Ballistic materials are configured in Vest → VestLayer</p>
            {formData.accessories.map((acc, index) => (
              <div key={index} className="bg-gray-50 p-3 rounded mb-2 border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Accessory {index + 1}</span>
                  <button
                    type="button"
                    onClick={() => removeAccessory(index)}
                    className="text-red-600 hover:text-red-900 text-sm"
                  >
                    Remove
                  </button>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Material</label>
                    <select
                      value={acc.material_id}
                      onChange={(e) => updateAccessory(index, 'material_id', e.target.value)}
                      className="w-full border rounded p-2 text-sm"
                    >
                      <option value="">Select material...</option>
                      {materials?.map((m: any) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Quantity per Vest</label>
                    <input
                      type="number"
                      step="0.01"
                      value={acc.quantity_per_vest}
                      onChange={(e) => updateAccessory(index, 'quantity_per_vest', parseFloat(e.target.value))}
                      className="w-full border rounded p-2 text-sm"
                      min={0}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Unit</label>
                    <select
                      value={acc.unit}
                      onChange={(e) => updateAccessory(index, 'unit', e.target.value)}
                      className="w-full border rounded p-2 text-sm"
                    >
                      <option value="meters">Meters</option>
                      <option value="pieces">Pieces</option>
                      <option value="pairs">Pairs</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">Notes</label>
                    <input
                      type="text"
                      value={acc.notes || ''}
                      onChange={(e) => updateAccessory(index, 'notes', e.target.value)}
                      className="w-full border rounded p-2 text-sm"
                      placeholder="Optional"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Notes</label>
            <textarea
              value={formData.notes || ''}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full border rounded p-2"
              rows={2}
              placeholder="Optional notes..."
            />
          </div>
        </div>

        <div className="flex justify-end space-x-4 mt-6">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onSave(formData)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
