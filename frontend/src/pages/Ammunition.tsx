import { useState } from 'react';
import { useAmmunition, useCreateAmmunition, useUpdateAmmunition, useDeleteAmmunition } from '../hooks/useAmmunition';
import { Ammunition, AmmunitionCreate, AmmunitionUpdate } from '../api/ammunition';

export function AmmunitionPage() {
  const { data: ammunitionList, isLoading, error } = useAmmunition();
  const createMutation = useCreateAmmunition();
  const updateMutation = useUpdateAmmunition();
  const deleteMutation = useDeleteAmmunition();
  
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingItem, setEditingItem] = useState<Ammunition | null>(null);
  const [formData, setFormData] = useState<AmmunitionCreate>({
    name: '',
    caliber: '',
    projectile_type: '',
    projectile_mass_grains: null,
    nominal_velocity_fps: null,
    manufacturer: '',
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading ammunition</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createMutation.mutateAsync(formData);
      setShowCreateForm(false);
      setFormData({ name: '', caliber: '', projectile_type: '', projectile_mass_grains: null, nominal_velocity_fps: null, manufacturer: '' });
    } catch (err) {
      console.error('Failed to create ammunition:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;
    try {
      await updateMutation.mutateAsync({ id: editingItem.id, ammunition: formData as AmmunitionUpdate });
      setEditingItem(null);
      setFormData({ name: '', caliber: '', projectile_type: '', projectile_mass_grains: null, nominal_velocity_fps: null, manufacturer: '' });
    } catch (err) {
      console.error('Failed to update ammunition:', err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this ammunition?')) return;
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      console.error('Failed to delete ammunition:', err);
    }
  };

  const startEdit = (item: Ammunition) => {
    setEditingItem(item);
    setFormData({
      name: item.name,
      caliber: item.caliber || '',
      projectile_type: item.projectile_type || '',
      projectile_mass_grains: item.projectile_mass_grains,
      nominal_velocity_fps: item.nominal_velocity_fps,
      manufacturer: item.manufacturer || '',
    });
  };

  const cancelEdit = () => {
    setEditingItem(null);
    setFormData({ name: '', caliber: '', projectile_type: '', projectile_mass_grains: null, nominal_velocity_fps: null, manufacturer: '' });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Ammunition Library</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
        >
          {showCreateForm ? 'Cancel' : 'Add Ammunition'}
        </button>
      </div>

      {(showCreateForm || editingItem) && (
        <div className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4">
            {editingItem ? 'Edit Ammunition' : 'Create New Ammunition'}
          </h2>
          <form onSubmit={editingItem ? handleUpdate : handleCreate} className="space-y-4">
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
                <label className="block text-sm font-medium text-gray-700">Caliber</label>
                <input
                  type="text"
                  value={formData.caliber}
                  onChange={(e) => setFormData({ ...formData, caliber: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Projectile Type</label>
                <select
                  value={formData.projectile_type}
                  onChange={(e) => setFormData({ ...formData, projectile_type: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select type...</option>
                  <option value="FMJ">FMJ</option>
                  <option value="JHP">JHP</option>
                  <option value="ball">Ball</option>
                  <option value="AP">AP</option>
                  <option value="fragment">Fragment</option>
                  <option value="slug">Slug</option>
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
                <label className="block text-sm font-medium text-gray-700">Projectile Mass (grains)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.projectile_mass_grains || ''}
                  onChange={(e) => setFormData({ ...formData, projectile_mass_grains: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Nominal Velocity (fps)</label>
                <input
                  type="number"
                  step="1"
                  value={formData.nominal_velocity_fps || ''}
                  onChange={(e) => setFormData({ ...formData, nominal_velocity_fps: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={editingItem ? cancelEdit : () => setShowCreateForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : editingItem ? 'Update' : 'Create'}
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
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Caliber</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Manufacturer</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mass (gr)</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Velocity (fps)</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {ammunitionList?.map((item) => (
              <tr key={item.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.caliber || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.projectile_type || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.manufacturer || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.projectile_mass_grains || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.nominal_velocity_fps || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => startEdit(item)}
                    className="text-indigo-600 hover:text-indigo-900 mr-3"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(item.id)}
                    className="text-red-600 hover:text-red-900"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {ammunitionList?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                  No ammunition found. Click "Add Ammunition" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
