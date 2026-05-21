import { useState, useEffect } from 'react';
import { useVests, useCreateVest, useUpdateVest, useDeleteVest, useUpdateVestLayers } from '../hooks/useVests';
import { Vest, VestCreate, VestUpdate, VestLayerCreate } from '../api/vests';
import { vestsApi } from '../api/vests';
import { useMaterials } from '../hooks/useMaterials';
import { Material } from '../api/materials';
import { ConfirmModal } from '../components/ConfirmModal';
import { useAuth } from '../hooks/useAuth';

export function Vests() {
  const { data: vests, isLoading, error } = useVests();
  const { data: materials, refetch: refetchMaterials } = useMaterials();
  const createMutation = useCreateVest();
  const updateMutation = useUpdateVest();
  const deleteMutation = useDeleteVest();
  const updateLayersMutation = useUpdateVestLayers();
  const { role } = useAuth();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingVest, setEditingVest] = useState<Vest | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Vest | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Refetch materials when form opens to get latest ply_count values
  useEffect(() => {
    if (showCreateForm || editingVest) {
      refetchMaterials();
    }
  }, [showCreateForm, editingVest, refetchMaterials]);
  const [formData, setFormData] = useState<VestCreate>({
    vest_code: '',
    vest_type: '',
    threat_level: '',
    protection_class: '',
    total_layers: null,
    total_thickness_mm: null,
    sizes: {},
    construction_notes: '',
    stitch_pattern: '',
    backing_material: '',
    notes: '',
    layers: [],
  });

  const [layers, setLayers] = useState<VestLayerCreate[]>([]);

  const SIZE_OPTIONS = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL'];

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
      
      await createMutation.mutateAsync({ ...formData, layers });
      setShowCreateForm(false);
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
        backing_material: '',
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

      const updatePayload = Object.fromEntries(
        Object.entries(formData).filter(([, v]) => v !== '' && v !== undefined && v !== null)
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
        backing_material: '',
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

  const startEdit = async (vest: Vest) => {
    // Fetch full vest details with layers
    const fullVest = await vestsApi.get(vest.id);
    setEditingVest(fullVest);
    setFormData({
      vest_code: fullVest.vest_code,
      vest_type: fullVest.vest_type || '',
      threat_level: fullVest.threat_level || '',
      protection_class: fullVest.protection_class || '',
      total_layers: fullVest.total_layers,
      total_thickness_mm: fullVest.total_thickness_mm,
      sizes: fullVest.sizes || {},
      construction_notes: fullVest.construction_notes || '',
      stitch_pattern: fullVest.stitch_pattern || '',
      backing_material: fullVest.backing_material || '',
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
      threat_level: '',
      protection_class: '',
      total_layers: null,
      total_thickness_mm: null,
      sizes: {},
      construction_notes: '',
      stitch_pattern: '',
      backing_material: '',
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

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Vests Library</h1>
        {role !== 'viewer' && (
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            {showCreateForm ? 'Cancel' : 'Add Vest'}
          </button>
        )}
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
                  onChange={(e) => setFormData({ ...formData, vest_type: e.target.value })}
                  required
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select type...</option>
                  <option value="soft">Soft</option>
                  <option value="hard">Hard</option>
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
                  <option value="NIJ_0101.07_HG1">NIJ 0101.07 HG1</option>
                  <option value="NIJ_0101.07_HG2">NIJ 0101.07 HG2</option>
                  <option value="NIJ_0101.07_RF1">NIJ 0101.07 RF1</option>
                  <option value="NIJ_0101.07_RF2">NIJ 0101.07 RF2</option>
                  <option value="NIJ_0101.07_RF3">NIJ 0101.07 RF3</option>
                  <option value="NIJ_IIA">NIJ IIA (Legacy)</option>
                  <option value="NIJ_II">NIJ II (Legacy)</option>
                  <option value="NIJ_IIIA">NIJ IIIA (Legacy)</option>
                  <option value="NIJ_III">NIJ III (Legacy)</option>
                  <option value="NIJ_IV">NIJ IV (Legacy)</option>
                  <option value="STANAG_4569_Level_1">STANAG 4569 Level 1</option>
                  <option value="STANAG_4569_Level_2">STANAG 4569 Level 2</option>
                  <option value="ARG_RB1">Argentina RB1</option>
                  <option value="ARG_RB2">Argentina RB2</option>
                  <option value="ARG_RB3">Argentina RB3</option>
                  <option value="ARG_RB4">Argentina RB4</option>
                  <option value="ARG_RB5">Argentina RB5</option>
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
                <label className="block text-sm font-medium text-gray-700">Total Thickness (mm)</label>
                <input
                  type="number"
                  step="0.001"
                  value={formData.total_thickness_mm ?? ''}
                  onChange={(e) => setFormData({ ...formData, total_thickness_mm: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Stitch Pattern</label>
                <input
                  type="text"
                  value={formData.stitch_pattern || ''}
                  onChange={(e) => setFormData({ ...formData, stitch_pattern: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Backing Material</label>
                <input
                  type="text"
                  value={formData.backing_material || ''}
                  onChange={(e) => setFormData({ ...formData, backing_material: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
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
              <h3 className="text-md font-medium text-gray-900 mb-4">Sizes and Surface Areas</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {SIZE_OPTIONS.map((size) => (
                  <div key={size} className="bg-gray-50 p-4 rounded-md">
                    <div className="flex items-center mb-2">
                      <input
                        type="checkbox"
                        id={`size-${size}`}
                        checked={formData.sizes?.[size] !== undefined}
                        onChange={(e) => {
                          const newSizes = { ...formData.sizes };
                          if (e.target.checked) {
                            newSizes[size] = 0;
                          } else {
                            delete newSizes[size];
                          }
                          setFormData(prev => ({ ...prev, sizes: newSizes }));
                        }}
                        className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                      />
                      <label htmlFor={`size-${size}`} className="text-sm font-medium text-gray-700 cursor-pointer">
                        {size}
                      </label>
                    </div>
                    {formData.sizes?.[size] !== undefined && (
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Surface Area (cm²)</label>
                        <input
                          type="number"
                          step="0.001"
                          value={formData.sizes[size] || ''}
                          onChange={(e) => {
                            const newSizes = { ...formData.sizes };
                            newSizes[size] = e.target.value ? parseFloat(e.target.value) : 0;
                            setFormData({ ...formData, sizes: newSizes });
                          }}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                        />
                      </div>
                    )}
                  </div>
                ))}
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
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vest Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Threat Level</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Protection Class</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total Layers</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Thickness</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {vests?.map((vest) => (
              <tr key={vest.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{vest.vest_code}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.vest_type || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.threat_level || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.protection_class || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.total_layers || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{vest.total_thickness_mm || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {role !== 'viewer' && (
                    <>
                      <button
                        onClick={() => startEdit(vest)}
                        className="text-indigo-600 hover:text-indigo-900 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteTarget(vest)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </>
                  )}
                  {role === 'viewer' && '-'}
                </td>
              </tr>
            ))}
            {vests?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                  No vests found. Click "Add Vest" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
    </div>
  );
}
