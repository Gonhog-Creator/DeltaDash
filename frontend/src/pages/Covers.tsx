import { useState } from 'react';
import { useCovers, useCreateCover, useUpdateCover, useDeleteCover } from '../hooks/useCovers';
import { useGeometries } from '../hooks/useGeometries';
import { useAuth } from '../hooks/useAuth';
import { Cover, CoverCreate } from '../api/covers';

const VEST_TYPES = ['Soft', 'Hard', 'Hybrid'];
const SIZE_OPTIONS = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];

const emptyForm: CoverCreate = {
  cover_code: '',
  name: '',
  geometry_id: null,
  fabric_type: null,
  fabric_weight_g_m2: null,
  layer_count: null,
  weight_g: null,
  has_molle: false,
  molle_config: null,
  has_quick_release: false,
  quick_release_type: null,
  fin_height_mm: null,
  fin_width_mm: null,
  available_sizes: [],
  compatible_vest_types: [],
  notes: null,
};

export function Covers() {
  const { data: covers, isLoading, error } = useCovers();
  const { data: geometries } = useGeometries();
  const { isAdmin, role } = useAuth();
  const createMutation = useCreateCover();
  const updateMutation = useUpdateCover();
  const deleteMutation = useDeleteCover();

  const canEdit = isAdmin && role !== 'viewer';

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<CoverCreate>(emptyForm);
  const [selectedCover, setSelectedCover] = useState<Cover | null>(null);

  const resetForm = () => {
    setFormData(emptyForm);
    setEditingId(null);
    setShowForm(false);
  };

  const handleCreate = () => {
    setFormData(emptyForm);
    setEditingId(null);
    setShowForm(true);
  };

  const handleEdit = (cover: Cover) => {
    setFormData({
      cover_code: cover.cover_code,
      name: cover.name,
      geometry_id: cover.geometry_id,
      fabric_type: cover.fabric_type,
      fabric_weight_g_m2: cover.fabric_weight_g_m2,
      layer_count: cover.layer_count,
      weight_g: cover.weight_g,
      has_molle: cover.has_molle,
      molle_config: cover.molle_config,
      has_quick_release: cover.has_quick_release,
      quick_release_type: cover.quick_release_type,
      fin_height_mm: cover.fin_height_mm,
      fin_width_mm: cover.fin_width_mm,
      available_sizes: cover.available_sizes,
      compatible_vest_types: cover.compatible_vest_types,
      notes: cover.notes,
    });
    setEditingId(cover.id);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updateMutation.mutateAsync({ id: editingId, data: formData });
      } else {
        await createMutation.mutateAsync(formData);
      }
      resetForm();
    } catch (err: any) {
      alert(`Failed to save cover: ${err.message || err.detail}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this cover?')) return;
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err: any) {
      alert(`Failed to delete cover: ${err.message || err.detail}`);
    }
  };

  const toggleSize = (size: string) => {
    const current = formData.available_sizes || [];
    setFormData({
      ...formData,
      available_sizes: current.includes(size)
        ? current.filter(s => s !== size)
        : [...current, size],
    });
  };

  const toggleVestType = (type: string) => {
    const current = formData.compatible_vest_types || [];
    setFormData({
      ...formData,
      compatible_vest_types: current.includes(type)
        ? current.filter(t => t !== type)
        : [...current, type],
    });
  };

  if (isLoading) return <div className="p-6">Loading covers...</div>;
  if (error) return <div className="p-6 text-red-600">Error loading covers.</div>;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Covers (Fundas)</h1>
        {canEdit && !showForm && (
          <button
            onClick={handleCreate}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Add Cover
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            {editingId ? 'Edit Cover' : 'New Cover'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Cover Code *</label>
              <input
                type="text"
                required
                value={formData.cover_code}
                onChange={e => setFormData({ ...formData, cover_code: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                placeholder="e.g., FUND-STOP-II"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Name *</label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                placeholder="e.g., Funda STOP II"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Geometry</label>
              <select
                value={formData.geometry_id || ''}
                onChange={e => setFormData({ ...formData, geometry_id: e.target.value || null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              >
                <option value="">None</option>
                {geometries?.map(g => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Fabric Type</label>
              <input
                type="text"
                value={formData.fabric_type || ''}
                onChange={e => setFormData({ ...formData, fabric_type: e.target.value || null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                placeholder="e.g., Cordura 500D"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Fabric Weight (g/m2)</label>
              <input
                type="number"
                step="0.01"
                value={formData.fabric_weight_g_m2 ?? ''}
                onChange={e => setFormData({ ...formData, fabric_weight_g_m2: e.target.value ? parseFloat(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Layer Count</label>
              <input
                type="number"
                value={formData.layer_count ?? ''}
                onChange={e => setFormData({ ...formData, layer_count: e.target.value ? parseInt(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Total Weight (g)</label>
              <input
                type="number"
                step="0.01"
                value={formData.weight_g ?? ''}
                onChange={e => setFormData({ ...formData, weight_g: e.target.value ? parseFloat(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Quick Release Type</label>
              <input
                type="text"
                value={formData.quick_release_type || ''}
                onChange={e => setFormData({ ...formData, quick_release_type: e.target.value || null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                placeholder="e.g., Tubo, Cinta, Ladder"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Fin Height (mm)</label>
              <input
                type="number"
                step="0.01"
                value={formData.fin_height_mm ?? ''}
                onChange={e => setFormData({ ...formData, fin_height_mm: e.target.value ? parseFloat(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Fin Width (mm)</label>
              <input
                type="number"
                step="0.01"
                value={formData.fin_width_mm ?? ''}
                onChange={e => setFormData({ ...formData, fin_width_mm: e.target.value ? parseFloat(e.target.value) : null })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
              />
            </div>
          </div>

          <div className="mt-4 flex items-center gap-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.has_molle || false}
                onChange={e => setFormData({ ...formData, has_molle: e.target.checked })}
                className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
              />
              <span className="text-sm text-gray-700">MOLLE</span>
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.has_quick_release || false}
                onChange={e => setFormData({ ...formData, has_quick_release: e.target.checked })}
                className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
              />
              <span className="text-sm text-gray-700">Quick Release</span>
            </label>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Available Sizes</label>
            <div className="flex flex-wrap gap-2">
              {SIZE_OPTIONS.map(size => (
                <label key={size} className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.available_sizes?.includes(size) || false}
                    onChange={() => toggleSize(size)}
                    className="mr-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                  />
                  <span className="text-sm text-gray-700">{size}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">Compatible Vest Types</label>
            <div className="flex flex-wrap gap-2">
              {VEST_TYPES.map(type => (
                <label key={type} className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.compatible_vest_types?.includes(type) || false}
                    onChange={() => toggleVestType(type)}
                    className="mr-1 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 accent-indigo-600"
                  />
                  <span className="text-sm text-gray-700">{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700">Notes</label>
            <textarea
              value={formData.notes || ''}
              onChange={e => setFormData({ ...formData, notes: e.target.value || null })}
              rows={3}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
            />
          </div>

          <div className="mt-6 flex gap-3">
            <button
              type="submit"
              disabled={createMutation.isPending || updateMutation.isPending}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {editingId ? 'Update' : 'Create'}
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Code</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Geometry</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fabric</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Weight</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">MOLLE</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quick Release</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sizes</th>
              {canEdit && <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {covers && covers.length > 0 ? covers.map(cover => (
              <tr key={cover.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setSelectedCover(cover)}>
                <td className="px-6 py-4 text-sm font-medium text-gray-900">{cover.cover_code}</td>
                <td className="px-6 py-4 text-sm text-gray-700">{cover.name}</td>
                <td className="px-6 py-4 text-sm text-gray-700">{cover.geometry_name || '-'}</td>
                <td className="px-6 py-4 text-sm text-gray-700">
                  {cover.fabric_type ? `${cover.fabric_type}${cover.fabric_weight_g_m2 ? ` (${cover.fabric_weight_g_m2} g/m2)` : ''}` : '-'}
                </td>
                <td className="px-6 py-4 text-sm text-gray-700">{cover.weight_g ? `${cover.weight_g} g` : '-'}</td>
                <td className="px-6 py-4 text-sm text-gray-700">{cover.has_molle ? 'Yes' : 'No'}</td>
                <td className="px-6 py-4 text-sm text-gray-700">
                  {cover.has_quick_release ? (cover.quick_release_type || 'Yes') : 'No'}
                </td>
                <td className="px-6 py-4 text-sm text-gray-700">{cover.available_sizes?.join(', ') || '-'}</td>
                {canEdit && (
                  <td className="px-6 py-4 text-sm font-medium" onClick={e => e.stopPropagation()}>
                    <button onClick={() => handleEdit(cover)} className="text-indigo-600 hover:text-indigo-900 mr-3">Edit</button>
                    <button onClick={() => handleDelete(cover.id)} className="text-red-600 hover:text-red-900">Delete</button>
                  </td>
                )}
              </tr>
            )) : (
              <tr>
                <td colSpan={canEdit ? 9 : 8} className="px-6 py-4 text-center text-sm text-gray-500">
                  No covers yet. {canEdit && 'Click "Add Cover" to create one.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedCover && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={() => setSelectedCover(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{selectedCover.cover_code}</h3>
                <p className="text-sm text-gray-500">{selectedCover.name}</p>
              </div>
              <button onClick={() => setSelectedCover(null)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500">Geometry:</span> <span className="ml-2 font-medium">{selectedCover.geometry_name || '-'}</span></div>
              <div><span className="text-gray-500">Fabric Type:</span> <span className="ml-2 font-medium">{selectedCover.fabric_type || '-'}</span></div>
              <div><span className="text-gray-500">Fabric Weight:</span> <span className="ml-2 font-medium">{selectedCover.fabric_weight_g_m2 ? `${selectedCover.fabric_weight_g_m2} g/m2` : '-'}</span></div>
              <div><span className="text-gray-500">Layer Count:</span> <span className="ml-2 font-medium">{selectedCover.layer_count ?? '-'}</span></div>
              <div><span className="text-gray-500">Total Weight:</span> <span className="ml-2 font-medium">{selectedCover.weight_g ? `${selectedCover.weight_g} g` : '-'}</span></div>
              <div><span className="text-gray-500">MOLLE:</span> <span className="ml-2 font-medium">{selectedCover.has_molle ? 'Yes' : 'No'}</span></div>
              <div><span className="text-gray-500">Quick Release:</span> <span className="ml-2 font-medium">{selectedCover.has_quick_release ? (selectedCover.quick_release_type || 'Yes') : 'No'}</span></div>
              <div><span className="text-gray-500">Fin Height:</span> <span className="ml-2 font-medium">{selectedCover.fin_height_mm ? `${selectedCover.fin_height_mm} mm` : '-'}</span></div>
              <div><span className="text-gray-500">Fin Width:</span> <span className="ml-2 font-medium">{selectedCover.fin_width_mm ? `${selectedCover.fin_width_mm} mm` : '-'}</span></div>
              <div><span className="text-gray-500">Sizes:</span> <span className="ml-2 font-medium">{selectedCover.available_sizes?.join(', ') || '-'}</span></div>
              <div><span className="text-gray-500">Compatible Vest Types:</span> <span className="ml-2 font-medium">{selectedCover.compatible_vest_types?.join(', ') || '-'}</span></div>
            </div>
            {selectedCover.notes && (
              <div className="mt-4 pt-4 border-t">
                <span className="text-gray-500 text-sm">Notes:</span>
                <p className="mt-1 text-sm text-gray-700">{selectedCover.notes}</p>
              </div>
            )}
            {canEdit && (
              <div className="mt-4 pt-4 border-t flex gap-3">
                <button onClick={() => { handleEdit(selectedCover); setSelectedCover(null); }} className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm">Edit</button>
                <button onClick={() => { handleDelete(selectedCover.id); setSelectedCover(null); }} className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm">Delete</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
