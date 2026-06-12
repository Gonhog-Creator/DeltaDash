import { useState, useEffect } from 'react';
import { useVests, useCreateVest, useUpdateVest, useDeleteVest, useUpdateVestLayers } from '../hooks/useVests';
import { Vest, VestCreate, VestUpdate, VestLayerCreate, VestTestSessionsResponse } from '../api/vests';
import { vestsApi } from '../api/vests';
import { useMaterials } from '../hooks/useMaterials';
import { Material } from '../api/materials';
import { ConfirmModal } from '../components/ConfirmModal';
import { useAuth } from '../hooks/useAuth';
import { apiClient } from '../api/client';

interface ProtocolThreatLevel {
  protocol_id: string;
  protocol_name: string;
  threat_levels: string[];
}

export function Vests() {
  const { data: vests, isLoading, error, refetch } = useVests();
  const { data: materials, refetch: refetchMaterials } = useMaterials();
  const createMutation = useCreateVest();
  const updateMutation = useUpdateVest();
  const deleteMutation = useDeleteVest();
  const updateLayersMutation = useUpdateVestLayers();
  const { role } = useAuth();

  // Automatically calculate thickness for vests that don't have it when library loads
  useEffect(() => {
    const autoCalculateThickness = async () => {
      if (role !== 'viewer' && vests && vests.length > 0) {
        try {
          await vestsApi.recalculateThickness();
        } catch (err) {
          // Silently fail - this is a background optimization
          console.error('Failed to auto-calculate thickness:', err);
        }
      }
    };
    autoCalculateThickness();
  }, [vests, role]);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingVest, setEditingVest] = useState<Vest | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Vest | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [sortField, setSortField] = useState<keyof Vest>('vest_code');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filterField, setFilterField] = useState<'vest_type' | 'threat_level' | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);
  const [activeFilterField, setActiveFilterField] = useState<'vest_type' | 'threat_level' | null>(null);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const [selectedVest, setSelectedVest] = useState<Vest | null>(null);
  const [testSessions, setTestSessions] = useState<VestTestSessionsResponse | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [loadingTestSessions, setLoadingTestSessions] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [protocolThreatLevels, setProtocolThreatLevels] = useState<ProtocolThreatLevel[]>([]);
  const [vestTestSessionCounts, setVestTestSessionCounts] = useState<Record<string, number>>({});

  // Refetch materials when form opens to get latest ply_count values
  useEffect(() => {
    if (showCreateForm || editingVest) {
      refetchMaterials();
    }
  }, [showCreateForm, editingVest, refetchMaterials]);

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

  // Fetch test session counts for all vests on mount
  useEffect(() => {
    const fetchVestTestSessionCounts = async () => {
      if (!vests) return;
      try {
        const counts: Record<string, number> = {};
        await Promise.all(
          vests.map(async (vest) => {
            try {
              const sessions = await vestsApi.getTestSessions(vest.id);
              counts[vest.id] = sessions.test_sessions.length;
            } catch (err) {
              counts[vest.id] = 0;
            }
          })
        );
        setVestTestSessionCounts(counts);
      } catch (err) {
        console.error('Failed to fetch vest test session counts:', err);
      }
    };
    fetchVestTestSessionCounts();
  }, [vests]);
  const [formData, setFormData] = useState<VestCreate>({
    vest_code: '',
    vest_type: '',
    is_female: false,
    threat_level: '',
    total_layers: null,
    total_thickness_mm: null,
    sizes: {},
    construction_notes: '',
    stitch_pattern: '',
    notes: '',
    created_by_username: '',
    layers: [],
  });

  const [layers, setLayers] = useState<VestLayerCreate[]>([]);

  const SIZE_OPTIONS = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL'];

  // Close modal on Escape key - must be before early returns
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && showDetailsModal) {
        handleCloseDetailsModal();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [showDetailsModal]);

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading vests</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Validate that total layers matches sum of layer counts
      const totalLayerCount = layers.reduce((sum, layer) => sum + (layer.layer_count || 0), 0);
      if (formData.total_layers && totalLayerCount !== formData.total_layers) {
        setValidationError(`Total layers (${formData.total_layers}) must equal sum of individual layer counts (${totalLayerCount})`);
        return;
      }
      
      // Calculate total_thickness_mm from layers if not provided
      let calculatedThickness = formData.total_thickness_mm;
      if (!calculatedThickness && layers.length > 0 && materials) {
        calculatedThickness = layers.reduce((sum, layer) => {
          const material = materials.find(m => m.id === layer.material_id);
          if (material && material.thickness_mm && layer.layer_count) {
            return sum + (material.thickness_mm * layer.layer_count);
          }
          return sum;
        }, 0);
      }
      
      await createMutation.mutateAsync({ ...formData, layers, total_thickness_mm: calculatedThickness });
      setShowCreateForm(false);
      setFormData({
        vest_code: '',
        vest_type: '',
        threat_level: '',
        total_layers: null,
        total_thickness_mm: null,
        sizes: {},
        construction_notes: '',
        stitch_pattern: '',
        notes: '',
        layers: [],
      });
      setLayers([]);
    } catch (err) {
      console.error('Failed to create vest:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingVest) return;
    try {
      // Validate that total layers matches sum of layer counts
      const totalLayerCount = layers.reduce((sum, layer) => sum + (layer.layer_count || 0), 0);
      if (formData.total_layers && totalLayerCount !== formData.total_layers) {
        setValidationError(`Total layers (${formData.total_layers}) must equal sum of individual layer counts (${totalLayerCount})`);
        return;
      }

      // Calculate total_thickness_mm from layers if not provided
      let calculatedThickness = formData.total_thickness_mm;
      if (!calculatedThickness && layers.length > 0 && materials) {
        calculatedThickness = layers.reduce((sum, layer) => {
          const material = materials.find(m => m.id === layer.material_id);
          if (material && material.thickness_mm && layer.layer_count) {
            return sum + (material.thickness_mm * layer.layer_count);
          }
          return sum;
        }, 0);
      }

      const updatePayload = Object.fromEntries(
        Object.entries({ ...formData, total_thickness_mm: calculatedThickness }).filter(([, v]) => v !== '' && v !== undefined && v !== null)
      ) as VestUpdate;
      await updateMutation.mutateAsync({ id: editingVest.id, vest: updatePayload });

      // Always update layers to ensure current state is saved
      await updateLayersMutation.mutateAsync({ id: editingVest.id, layers });

      setEditingVest(null);
      setFormData({
        vest_code: '',
        vest_type: '',
        threat_level: '',
        protection_class: '',
        total_layers: null,
        total_thickness_mm: null,
        sizes: {},
        construction_notes: '',
        stitch_pattern: '',
        notes: '',
        layers: [],
      });
      setLayers([]);
    } catch (err) {
      console.error('Failed to update vest:', err);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch (err) {
      console.error('Failed to delete vest:', err);
    } finally {
      setDeleteTarget(null);
    }
  };

  const handleRecalculateThickness = async () => {
    if (!vests) return;
    setRecalculating(true);
    try {
      const result = await vestsApi.recalculateThickness(true);
      alert(result.message);
      refetch();
    } catch (err) {
      console.error('Failed to recalculate thickness:', err);
      alert('Failed to recalculate thickness. See console for details.');
    } finally {
      setRecalculating(false);
    }
  };

  const startEdit = async (vest: Vest) => {
    // Fetch full vest details with layers
    const fullVest = await vestsApi.get(vest.id);
    setEditingVest(fullVest);
    setFormData({
      vest_code: fullVest.vest_code,
      vest_type: fullVest.vest_type || '',
      is_female: fullVest.is_female || false,
      threat_level: fullVest.threat_level || '',
      protection_class: fullVest.protection_class || '',
      total_layers: fullVest.total_layers,
      total_thickness_mm: fullVest.total_thickness_mm,
      sizes: fullVest.sizes || {},
      construction_notes: fullVest.construction_notes || '',
      stitch_pattern: fullVest.stitch_pattern || '',
      notes: fullVest.notes || '',
      created_by_username: fullVest.created_by_username || '',
      layers: [],
    });
    setLayers(
      fullVest.layers.map((layer) => ({
        layer_index: layer.layer_index,
        material_id: layer.material_id,
        layer_count: layer.layer_count,
        notes: layer.notes,
      }))
    );
  };

  const cancelEdit = () => {
    setEditingVest(null);
    setFormData({
      vest_code: '',
      vest_type: '',
      is_female: false,
      threat_level: '',
      protection_class: '',
      total_layers: null,
      total_thickness_mm: null,
      sizes: {},
      construction_notes: '',
      stitch_pattern: '',
      notes: '',
      created_by_username: '',
      layers: [],
    });
    setLayers([]);
  };

  const addLayer = () => {
    const newLayer: VestLayerCreate = {
      layer_index: layers.length,
      material_id: null,
      layer_count: 1,
      notes: '',
    };
    setLayers([...layers, newLayer]);
  };

  const updateLayer = (index: number, field: keyof VestLayerCreate, value: any) => {
    const updatedLayers = [...layers];
    updatedLayers[index] = { ...updatedLayers[index], [field]: value };
    setLayers(updatedLayers);
  };

  const removeLayer = (index: number) => {
    const updatedLayers = layers.filter((_, i) => i !== index).map((layer, i) => ({ ...layer, layer_index: i }));
    setLayers(updatedLayers);
  };

  const handleSort = (field: keyof Vest) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getFilteredAndSortedVests = (vests: Vest[] | undefined) => {
    if (!vests) return vests;
    
    let filtered = vests;
    
    // Apply filter
    if (activeFilterField && activeFilters.length > 0) {
      filtered = vests.filter(vest => {
        const value = vest[activeFilterField];
        if (!value) return false;
        // Case-insensitive comparison
        return activeFilters.some(selected => 
          selected.toLowerCase() === value.toString().toLowerCase()
        );
      });
    }
    
    // Apply sort
    if (!sortField) return filtered;
    
    return [...filtered].sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];
      
      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;
      
      // For numeric fields, convert to numbers for proper comparison
      const numericFields = ['total_layers', 'total_thickness_mm'];
      
      if (numericFields.includes(sortField as string)) {
        const aNum = typeof aValue === 'string' ? parseFloat(aValue) : aValue as number;
        const bNum = typeof bValue === 'string' ? parseFloat(bValue) : bValue as number;
        
        if (isNaN(aNum)) return 1;
        if (isNaN(bNum)) return -1;
        
        return sortDirection === 'asc' ? aNum - bNum : bNum - aNum;
      }
      
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }
      
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return sortDirection === 'asc' 
          ? aValue - bValue
          : bValue - aValue;
      }
      
      return 0;
    });
  };

  const getUniqueValues = (field: 'vest_type' | 'threat_level') => {
    if (!vests) return [];
    const values = vests
      .map(v => v[field])
      .filter((v): v is string => v !== null && v !== undefined);
    return Array.from(new Set(values)).sort();
  };

  const handleVestClick = async (vest: Vest) => {
    setSelectedVest(vest);
    setShowDetailsModal(true);
    setLoadingTestSessions(true);
    try {
      const sessions = await vestsApi.getTestSessions(vest.id);
      setTestSessions(sessions);
    } catch (err) {
      console.error('Failed to fetch test sessions:', err);
      setTestSessions(null);
    } finally {
      setLoadingTestSessions(false);
    }
  };

  const handleCloseDetailsModal = () => {
    setSelectedVest(null);
    setTestSessions(null);
    setShowDetailsModal(false);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Vests Library</h1>
        <div className="flex gap-2">
          {role !== 'viewer' && !editingVest && (
            <button
              onClick={() => setShowCreateForm(!showCreateForm)}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              {showCreateForm ? 'Cancel' : 'Add Vest'}
            </button>
          )}
          {role === 'admin' && !editingVest && (
            <button
              onClick={handleRecalculateThickness}
              disabled={recalculating}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {recalculating ? 'Recalculating...' : 'Recalculate Thickness'}
            </button>
          )}
        </div>
      </div>

      {(showCreateForm || editingVest) && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4">
            {editingVest ? 'Edit Vest' : 'Create New Vest'}
          </h2>
          <form onSubmit={editingVest ? handleUpdate : handleCreate} className="space-y-4">
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
                  onChange={(e) => {
                    const newType = e.target.value;
                    setFormData({ ...formData, vest_type: newType, stitch_pattern: newType.toLowerCase() === 'soft' ? formData.stitch_pattern : null });
                  }}
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
                        <option key={level} value={level}>
                          {level}
                        </option>
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
              {formData.vest_type?.toLowerCase() === 'soft' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Female Vest</label>
                    <div className="flex items-center gap-4 mt-1">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.is_female || false}
                          onChange={(e) => setFormData({ ...formData, is_female: e.target.checked })}
                          className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                        />
                        <span className="text-sm text-gray-700">Is Female Vest</span>
                      </label>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Stitched</label>
                    <div className="flex items-center gap-4 mt-1">
                      <label className="flex items-center">
                        <input
                          type="checkbox"
                          checked={formData.stitch_pattern === 'stitched'}
                          onChange={(e) => setFormData({ ...formData, stitch_pattern: e.target.checked ? 'stitched' : null })}
                          className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                        />
                      <span className="text-sm text-gray-700">Stitched</span>
                    </label>
                  </div>
                </div>
              </>
            )}
            {editingVest && role === 'admin' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">Created By</label>
                  <input
                    type="text"
                    value={formData.created_by_username || ''}
                    onChange={(e) => setFormData({ ...formData, created_by_username: e.target.value })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                  />
                </div>
              )}
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700">Construction Notes</label>
                <textarea
                  value={formData.construction_notes || ''}
                  onChange={(e) => setFormData({ ...formData, construction_notes: e.target.value })}
                  rows={2}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
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
                        value={layer.layer_count}
                        onChange={(e) => updateLayer(index, 'layer_count', e.target.value === '' ? '' : parseInt(e.target.value))}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div className="md:col-span-3">
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

            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={editingVest ? cancelEdit : () => setShowCreateForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : editingVest ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {!(showCreateForm || editingVest) && (
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 max-w-[180px] truncate"
                onClick={() => handleSort('vest_code')}
              >
                Vest Code {sortField === 'vest_code' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 max-w-32 truncate"
                onClick={() => handleSort('vest_type')}
              >
                <div className="flex items-center gap-1">
                  <span>Type</span>
                  <span>{sortField === 'vest_type' && (sortDirection === 'asc' ? '↑' : '↓')}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setFilterField('vest_type');
                      setSelectedFilters(activeFilterField === 'vest_type' ? [...activeFilters] : []);
                    }}
                    className="text-gray-400 hover:text-gray-600 text-xs"
                    title="Filter"
                  >
                    ⚙
                  </button>
                </div>
              </th>
              <th
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 max-w-40 truncate"
                onClick={() => handleSort('threat_level')}
              >
                <div className="flex items-center gap-1">
                  <span>Threat Level</span>
                  <span>{sortField === 'threat_level' && (sortDirection === 'asc' ? '↑' : '↓')}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setFilterField('threat_level');
                      setSelectedFilters(activeFilterField === 'threat_level' ? [...activeFilters] : []);
                    }}
                    className="text-gray-400 hover:text-gray-600 text-xs"
                    title="Filter"
                  >
                    ⚙
                  </button>
                </div>
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('total_layers')}
              >
                Total Layers {sortField === 'total_layers' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-xs">Composition</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Thickness</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Stitched</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Linked</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {getFilteredAndSortedVests(vests)?.map((vest) => {
              // Calculate estimated thickness from layers if not provided
              let thicknessDisplay = vest.total_thickness_mm ? `${Number(vest.total_thickness_mm).toFixed(2)} mm` : '-';
              if (!vest.total_thickness_mm && vest.layers && vest.layers.length > 0) {
                const estimatedThickness = vest.layers.reduce((sum, layer) => {
                  const material = materials?.find(m => m.id === layer.material_id);
                  if (material && material.thickness_mm && layer.layer_count) {
                    return sum + (material.thickness_mm * layer.layer_count);
                  }
                  return sum;
                }, 0);
                if (estimatedThickness > 0) {
                  thicknessDisplay = `${estimatedThickness.toFixed(2)} mm (estimated)`;
                }
              }

              const isStitched = vest.stitch_pattern === 'stitched';
              const shouldShowStitched = vest.vest_type?.toLowerCase() === 'soft';
              const isLinked = vestTestSessionCounts[vest.id] > 0;

              return (
                <tr key={vest.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleVestClick(vest)}>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 max-w-[180px] break-words">{vest.vest_code?.toUpperCase()}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-32 break-words">{vest.vest_type ? vest.vest_type.charAt(0).toUpperCase() + vest.vest_type.slice(1).toLowerCase() : '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-40 break-words">{vest.threat_level || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.total_layers || '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-xs break-words">{vest.composition || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{thicknessDisplay}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{shouldShowStitched ? (isStitched ? 'Yes' : 'No') : '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {isLinked ? (
                      <span className="text-green-500 text-lg">✓</span>
                    ) : (
                      <span className="text-red-500 text-lg">✗</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {role !== 'viewer' && (
                    <>
                      <button
                        onClick={(e) => { e.stopPropagation(); startEdit(vest); }}
                        className="text-indigo-600 hover:text-indigo-900 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setDeleteTarget(vest); }}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </>
                  )}
                  {role === 'viewer' && '-'}
                </td>
              </tr>
              );
            })}
            {vests?.length === 0 && (
              <tr>
                <td colSpan={9} className="px-6 py-4 text-center text-sm text-gray-500">
                  No vests found. Click "Add Vest" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
      )}
      {deleteTarget && (
        <ConfirmModal
          title="Delete Vest"
          message={`Are you sure you want to delete "${deleteTarget.vest_code}"? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
      {validationError && (
        <ConfirmModal
          title="Validation Error"
          message={validationError}
          confirmLabel="OK"
          variant="info"
          onConfirm={() => setValidationError(null)}
          onCancel={() => setValidationError(null)}
        />
      )}
      {filterField && (
        <ConfirmModal
          title={`Filter by ${filterField === 'vest_type' ? 'Type' : 'Threat Level'}`}
          message={
            <div className="max-h-96 overflow-y-auto">
              {getUniqueValues(filterField).map((value) => (
                <label key={value} className="flex items-center mb-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedFilters.includes(value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedFilters([...selectedFilters, value]);
                      } else {
                        setSelectedFilters(selectedFilters.filter(f => f !== value));
                      }
                    }}
                    className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                  />
                  <span className="text-sm text-gray-700">{value}</span>
                </label>
              ))}
              {selectedFilters.length > 0 && (
                <button
                  onClick={() => setSelectedFilters([])}
                  className="mt-3 text-sm text-red-600 hover:text-red-900"
                >
                  Clear all
                </button>
              )}
            </div>
          }
          confirmLabel="Apply"
          variant="default"
          onConfirm={() => {
            setActiveFilterField(filterField);
            setActiveFilters([...selectedFilters]);
            setFilterField(null);
          }}
          onCancel={() => {
            setFilterField(null);
            setSelectedFilters([]);
          }}
        />
      )}
      {showDetailsModal && selectedVest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={handleCloseDetailsModal} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Vest Details</h3>
              <button
                onClick={handleCloseDetailsModal}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            
            {/* Vest Info */}
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Vest Information</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Vest Code:</span>
                  <span className="ml-2 font-medium">{selectedVest.vest_code?.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-gray-500">Type:</span>
                  <span className="ml-2 font-medium">{selectedVest.vest_type ? selectedVest.vest_type.charAt(0).toUpperCase() + selectedVest.vest_type.slice(1).toLowerCase() : '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Female:</span>
                  <span className="ml-2 font-medium">{selectedVest.is_female ? 'Yes' : 'No'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Threat Level:</span>
                  <span className="ml-2 font-medium">{selectedVest.threat_level || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Total Layers:</span>
                  <span className="ml-2 font-medium">{selectedVest.total_layers || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Total Thickness:</span>
                  <span className="ml-2 font-medium">{selectedVest.total_thickness_mm ? `${selectedVest.total_thickness_mm} mm` : '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Protection Class:</span>
                  <span className="ml-2 font-medium">{selectedVest.protection_class || '-'}</span>
                </div>
                {selectedVest.vest_type?.toLowerCase() === 'soft' && (
                  <div className="md:col-span-2">
                    <span className="text-gray-500">Stitch Pattern:</span>
                    <span className="ml-2 font-medium">{selectedVest.stitch_pattern || '-'}</span>
                  </div>
                )}
              </div>
            </div>
            
            {/* Test Sessions */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">Test Sessions ({testSessions?.test_sessions.length || 0})</h4>
              {loadingTestSessions ? (
                <div className="text-sm text-gray-500">Loading test sessions...</div>
              ) : testSessions && testSessions.test_sessions.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Test Date</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Lab</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Protocol</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Official</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Shot Count</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {testSessions.test_sessions.map((session) => (
                        <tr key={session.id} className="hover:bg-gray-50">
                          <td className="px-4 py-2 text-sm text-gray-900">{session.name}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{session.test_date ? new Date(session.test_date).toLocaleDateString() : '-'}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{session.lab_name || '-'}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{session.protocol || '-'}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{session.is_official ? 'Yes' : 'No'}</td>
                          <td className="px-4 py-2 text-sm text-gray-500">{session.shot_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-gray-500">No test sessions found for this vest.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
