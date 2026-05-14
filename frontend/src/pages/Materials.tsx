import { useState } from 'react';
import { useMaterials, useCreateMaterial, useUpdateMaterial, useDeleteMaterial } from '../hooks/useMaterials';
import { Material, MaterialCreate, MaterialUpdate } from '../types/material';

export function Materials() {
  const { data: materials, isLoading, error } = useMaterials();
  const createMutation = useCreateMaterial();
  const updateMutation = useUpdateMaterial();
  const deleteMutation = useDeleteMaterial();
  
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingMaterial, setEditingMaterial] = useState<Material | null>(null);
  const [formData, setFormData] = useState<MaterialCreate>({
    name: '',
    material_class: '',
    manufacturer: '',
    areal_density_g_m2: null,
    thickness_mm: null,
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading materials</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createMutation.mutateAsync(formData);
      setShowCreateForm(false);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null });
    } catch (err) {
      console.error('Failed to create material:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMaterial) return;
    try {
      await updateMutation.mutateAsync({ id: editingMaterial.id, material: formData as MaterialUpdate });
      setEditingMaterial(null);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null });
    } catch (err) {
      console.error('Failed to update material:', err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this material?')) return;
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      console.error('Failed to delete material:', err);
    }
  };

  const startEdit = (material: Material) => {
    setEditingMaterial(material);
    setFormData({
      name: material.name,
      material_class: material.material_class || '',
      manufacturer: material.manufacturer || '',
      areal_density_g_m2: material.areal_density_g_m2,
      thickness_mm: material.thickness_mm,
    });
  };

  const cancelEdit = () => {
    setEditingMaterial(null);
    setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Materials Library</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
        >
          {showCreateForm ? 'Cancel' : 'Add Material'}
        </button>
      </div>

      {(showCreateForm || editingMaterial) && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4">
            {editingMaterial ? 'Edit Material' : 'Create New Material'}
          </h2>
          <form onSubmit={editingMaterial ? handleUpdate : handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Material Class</label>
                <select
                  value={formData.material_class}
                  onChange={(e) => setFormData({ ...formData, material_class: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select class...</option>
                  <option value="aramid">Aramid</option>
                  <option value="UHMWPE">UHMWPE</option>
                  <option value="nylon">Nylon</option>
                  <option value="basalt">Basalt</option>
                  <option value="carbon_fiber">Carbon Fiber</option>
                  <option value="glass_fiber">Glass Fiber</option>
                  <option value="ceramic">Ceramic</option>
                  <option value="metal">Metal</option>
                  <option value="foam">Foam</option>
                  <option value="rubber">Rubber</option>
                  <option value="film">Film</option>
                  <option value="coating">Coating</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Manufacturer</label>
                <input
                  type="text"
                  value={formData.manufacturer}
                  onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Areal Density (g/m²)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.areal_density_g_m2 || ''}
                  onChange={(e) => setFormData({ ...formData, areal_density_g_m2: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Thickness (mm)</label>
                <input
                  type="number"
                  step="0.001"
                  value={formData.thickness_mm || ''}
                  onChange={(e) => setFormData({ ...formData, thickness_mm: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={editingMaterial ? cancelEdit : () => setShowCreateForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : editingMaterial ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Class</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Manufacturer</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Areal Density</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Thickness</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {materials?.map((material) => (
              <tr key={material.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{material.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.material_class || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.manufacturer || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.areal_density_g_m2 || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.thickness_mm || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => startEdit(material)}
                    className="text-indigo-600 hover:text-indigo-900 mr-3"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(material.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {materials?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">
                  No materials found. Click "Add Material" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
