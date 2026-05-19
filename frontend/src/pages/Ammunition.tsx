import { useState } from 'react';
import { useAmmunition, useCreateAmmunition, useUpdateAmmunition, useDeleteAmmunition } from '../hooks/useAmmunition';
import { useAuth } from '../hooks/useAuth';
import { Ammunition, AmmunitionCreate, AmmunitionUpdate } from '../api/ammunition';
import { ConfirmModal } from '../components/ConfirmModal';

export function AmmunitionPage() {
  const { data: ammunitionList, isLoading, error } = useAmmunition();
  const createMutation = useCreateAmmunition();
  const updateMutation = useUpdateAmmunition();
  const deleteMutation = useDeleteAmmunition();
  const { isAdmin } = useAuth();
  
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingItem, setEditingItem] = useState<Ammunition | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Ammunition | null>(null);
  const [velocityUnit, setVelocityUnit] = useState<'fps' | 'm/s'>('fps');
  const [formData, setFormData] = useState<AmmunitionCreate>({
    name: '',
    caliber: '',
    caliber_unit: 'mm',
    caliber_diameter_mm: null,
    caliber_length_mm: null,
    caliber_inch: null,
    projectile_type: '',
    projectile_mass_grains: 0,
    nominal_velocity_fps: 0,
    nominal_velocity_m_s: null,
    manufacturer: '',
  });

  const convertVelocity = (value: number, fromUnit: 'fps' | 'm/s', toUnit: 'fps' | 'm/s'): number => {
    if (fromUnit === toUnit) return value;
    if (fromUnit === 'fps' && toUnit === 'm/s') return value * 0.3048;
    if (fromUnit === 'm/s' && toUnit === 'fps') return value / 0.3048;
    return value;
  };

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading ammunition</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createMutation.mutateAsync(formData);
      setShowCreateForm(false);
      setFormData({ name: '', caliber: '', caliber_unit: 'mm', caliber_diameter_mm: null, caliber_length_mm: null, caliber_inch: null, projectile_type: '', projectile_mass_grains: 0, nominal_velocity_fps: 0, nominal_velocity_m_s: null, manufacturer: '' });
      setVelocityUnit('fps');
    } catch (err) {
      console.error('Failed to create ammunition:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem) return;
    try {
      const updatePayload = Object.fromEntries(
        Object.entries(formData).filter(([, v]) => v !== '' && v !== undefined)
      ) as AmmunitionUpdate;
      await updateMutation.mutateAsync({ id: editingItem.id, ammunition: updatePayload });
      setEditingItem(null);
      setFormData({ name: '', caliber: '', caliber_unit: 'mm', caliber_diameter_mm: null, caliber_length_mm: null, caliber_inch: null, projectile_type: '', projectile_mass_grains: 0, nominal_velocity_fps: 0, nominal_velocity_m_s: null, manufacturer: '' });
      setVelocityUnit('fps');
    } catch (err) {
      console.error('Failed to update ammunition:', err);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch (err) {
      console.error('Failed to delete ammunition:', err);
    } finally {
      setDeleteTarget(null);
    }
  };

  const startEdit = (item: Ammunition) => {
    setEditingItem(item);
    setFormData({
      name: item.name,
      caliber: item.caliber || '',
      caliber_unit: item.caliber_unit || 'mm',
      caliber_diameter_mm: item.caliber_diameter_mm,
      caliber_length_mm: item.caliber_length_mm,
      caliber_inch: item.caliber_inch,
      projectile_type: item.projectile_type || '',
      projectile_mass_grains: item.projectile_mass_grains || 0,
      nominal_velocity_fps: item.nominal_velocity_fps || 0,
      nominal_velocity_m_s: item.nominal_velocity_m_s || null,
      manufacturer: item.manufacturer || '',
    });
    setVelocityUnit(item.nominal_velocity_m_s && item.nominal_velocity_m_s > 0 ? 'm/s' : 'fps');
  };

  const cancelEdit = () => {
    setEditingItem(null);
    setFormData({ name: '', caliber: '', caliber_unit: 'mm', caliber_diameter_mm: null, caliber_length_mm: null, caliber_inch: null, projectile_type: '', projectile_mass_grains: 0, nominal_velocity_fps: 0, nominal_velocity_m_s: null, manufacturer: '' });
    setVelocityUnit('fps');
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Ammunition Library</h1>
        {isAdmin && (
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            {showCreateForm ? 'Cancel' : 'Add Ammunition'}
          </button>
        )}
      </div>

      {!(showCreateForm || editingItem) && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Caliber</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Manufacturer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mass (gr)</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Velocity</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {ammunitionList?.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{item.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {item.caliber_unit === 'mm'
                      ? `${item.caliber_diameter_mm && item.caliber_length_mm
                          ? `${parseFloat(item.caliber_diameter_mm).toFixed(2).replace(/\.00$/, '')}x${parseFloat(item.caliber_length_mm).toFixed(2).replace(/\.00$/, '')}mm`
                          : '-'
                        }`
                      : item.caliber_inch ? `${parseFloat(item.caliber_inch).toFixed(4).replace(/\.?0+$/, '')} in` : '-'
                    }
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.projectile_type || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.manufacturer || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{item.projectile_mass_grains || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {item.nominal_velocity_m_s ? `${Math.round(item.nominal_velocity_m_s)} m/s` : item.nominal_velocity_fps ? `${Math.round(item.nominal_velocity_fps * 0.3048)} m/s` : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    {isAdmin && (
                      <>
                        <button
                          onClick={() => startEdit(item)}
                          className="text-indigo-600 hover:text-indigo-900 mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => setDeleteTarget(item)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {ammunitionList?.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                    No ammunition found.
                    {isAdmin && ' Click "Add Ammunition" to create one.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {(showCreateForm || editingItem) && isAdmin && (
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
                <label className="block text-sm font-medium text-gray-700">Caliber Unit</label>
                <div className="mt-1 flex space-x-4">
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      name="caliber_unit"
                      value="mm"
                      checked={formData.caliber_unit === 'mm'}
                      onChange={(e) => setFormData({ ...formData, caliber_unit: e.target.value })}
                      className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">mm</span>
                  </label>
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      name="caliber_unit"
                      value="inches"
                      checked={formData.caliber_unit === 'inches'}
                      onChange={(e) => setFormData({ ...formData, caliber_unit: e.target.value })}
                      className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">Inches</span>
                  </label>
                </div>
              </div>
              {formData.caliber_unit === 'mm' ? (
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-gray-700">Dimensions (Diameter x Length, mm) *</label>
                  <div className="mt-1 flex items-center space-x-2">
                    <input
                      type="number"
                      step="0.001"
                      required
                      placeholder="Diameter"
                      value={formData.caliber_diameter_mm ?? ''}
                      onChange={(e) => setFormData({ ...formData, caliber_diameter_mm: e.target.value ? parseFloat(e.target.value) : null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                    />
                    <span className="text-gray-500">x</span>
                    <input
                      type="number"
                      step="0.001"
                      required
                      placeholder="Length"
                      value={formData.caliber_length_mm ?? ''}
                      onChange={(e) => setFormData({ ...formData, caliber_length_mm: e.target.value ? parseFloat(e.target.value) : null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-gray-700">Caliber (inches) *</label>
                  <input
                    type="number"
                    step="0.0001"
                    required
                    placeholder="e.g., 0.308"
                    value={formData.caliber_inch ?? ''}
                    onChange={(e) => setFormData({ ...formData, caliber_inch: e.target.value ? parseFloat(e.target.value) : null })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                  />
                </div>
              )}
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
                <label className="block text-sm font-medium text-gray-700">Projectile Mass (grains) *</label>
                <input
                  type="number"
                  step="0.1"
                  required
                  value={formData.projectile_mass_grains || ''}
                  onChange={(e) => setFormData({ ...formData, projectile_mass_grains: e.target.value ? parseFloat(e.target.value) : 0 })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Nominal Velocity Unit</label>
                <div className="mt-1 flex space-x-4">
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      name="velocity_unit"
                      value="fps"
                      checked={velocityUnit === 'fps'}
                      onChange={(e) => {
                        const newUnit = e.target.value as 'fps' | 'm/s';
                        const currentValue = velocityUnit === 'fps' ? formData.nominal_velocity_fps : formData.nominal_velocity_m_s;
                        const convertedValue = currentValue ? convertVelocity(currentValue, velocityUnit, newUnit) : 0;
                        setVelocityUnit(newUnit);
                        if (newUnit === 'fps') {
                          setFormData({ ...formData, nominal_velocity_fps: convertedValue, nominal_velocity_m_s: null });
                        } else {
                          setFormData({ ...formData, nominal_velocity_fps: 0, nominal_velocity_m_s: convertedValue });
                        }
                      }}
                      className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">fps</span>
                  </label>
                  <label className="inline-flex items-center">
                    <input
                      type="radio"
                      name="velocity_unit"
                      value="m/s"
                      checked={velocityUnit === 'm/s'}
                      onChange={(e) => {
                        const newUnit = e.target.value as 'fps' | 'm/s';
                        const currentValue = velocityUnit === 'fps' ? formData.nominal_velocity_fps : formData.nominal_velocity_m_s;
                        const convertedValue = currentValue ? convertVelocity(currentValue, velocityUnit, newUnit) : 0;
                        setVelocityUnit(newUnit);
                        if (newUnit === 'fps') {
                          setFormData({ ...formData, nominal_velocity_fps: convertedValue, nominal_velocity_m_s: null });
                        } else {
                          setFormData({ ...formData, nominal_velocity_fps: 0, nominal_velocity_m_s: convertedValue });
                        }
                      }}
                      className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">m/s</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Nominal Velocity ({velocityUnit}) *</label>
                <input
                  type="number"
                  step="0.1"
                  required
                  value={velocityUnit === 'fps' ? (formData.nominal_velocity_fps || '') : (formData.nominal_velocity_m_s || '')}
                  onChange={(e) => {
                    const value = e.target.value ? parseFloat(e.target.value) : 0;
                    if (velocityUnit === 'fps') {
                      setFormData({ ...formData, nominal_velocity_fps: value, nominal_velocity_m_s: convertVelocity(value, 'fps', 'm/s') });
                    } else {
                      setFormData({ ...formData, nominal_velocity_fps: convertVelocity(value, 'm/s', 'fps'), nominal_velocity_m_s: value });
                    }
                  }}
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

      {deleteTarget && (
        <ConfirmModal
          title="Delete Ammunition"
          message={`Are you sure you want to delete "${deleteTarget.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
