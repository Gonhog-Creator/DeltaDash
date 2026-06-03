import { useState } from 'react';
import { useProtocols, useCreateProtocol, useUpdateProtocol, useDeleteProtocol } from '../hooks/useProtocols';
import { useAmmunition } from '../hooks/useAmmunition';
import { Protocol } from '../api/protocols';
import { ConfirmModal } from '../components/ConfirmModal';
import { useAuth } from '../hooks/useAuth';

interface AmmunitionConfig {
  ammunition_id: string;
  reference_velocity_m_s: number;
  velocity_window_m_s: number;
  shots_per_panel: number;
}

interface ProtocolLevel {
  level_name: string;
  ammunition_config: AmmunitionConfig[];
}

export function Protocols() {
  const { data: protocols, isLoading, error, refetch } = useProtocols();
  const { data: ammunition } = useAmmunition();
  const createMutation = useCreateProtocol();
  const updateMutation = useUpdateProtocol();
  const deleteMutation = useDeleteProtocol();
  const { role } = useAuth();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingProtocol, setEditingProtocol] = useState<Protocol | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Protocol | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    levels_config: [] as ProtocolLevel[],
  });

  if (role !== 'admin' && role !== 'editor') {
    return <div className="p-6">Access denied. Admin or editor only.</div>;
  }

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading protocols</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createMutation.mutateAsync(formData);
      setShowCreateForm(false);
      setFormData({ name: '', description: '', levels_config: [] });
      refetch();
    } catch (err) {
      console.error('Failed to create protocol:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProtocol) return;
    try {
      await updateMutation.mutateAsync({ id: editingProtocol.id, protocol: formData });
      setEditingProtocol(null);
      setFormData({ name: '', description: '', levels_config: [] });
      refetch();
    } catch (err) {
      console.error('Failed to update protocol:', err);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      setDeleteTarget(null);
      refetch();
    } catch (err) {
      console.error('Failed to delete protocol:', err);
    }
  };

  const addLevel = () => {
    setFormData({
      ...formData,
      levels_config: [
        ...formData.levels_config,
        { level_name: '', ammunition_config: [] },
      ],
    });
  };

  const removeLevel = (index: number) => {
    setFormData({
      ...formData,
      levels_config: formData.levels_config.filter((_, i) => i !== index),
    });
  };

  const updateLevel = (index: number, field: keyof ProtocolLevel, value: any) => {
    const updatedLevels = [...formData.levels_config];
    updatedLevels[index] = { ...updatedLevels[index], [field]: value };
    setFormData({ ...formData, levels_config: updatedLevels });
  };

  const addAmmunitionToLevel = (levelIndex: number) => {
    const updatedLevels = [...formData.levels_config];
    updatedLevels[levelIndex].ammunition_config.push({
      ammunition_id: '',
      reference_velocity_m_s: 400,
      velocity_window_m_s: 5,
      shots_per_panel: 6,
    });
    setFormData({ ...formData, levels_config: updatedLevels });
  };

  const updateAmmunitionInLevel = (levelIndex: number, ammoIndex: number, field: keyof AmmunitionConfig, value: any) => {
    const updatedLevels = [...formData.levels_config];
    updatedLevels[levelIndex].ammunition_config[ammoIndex] = {
      ...updatedLevels[levelIndex].ammunition_config[ammoIndex],
      [field]: value,
    };
    setFormData({ ...formData, levels_config: updatedLevels });
  };

  const removeAmmunitionFromLevel = (levelIndex: number, ammoIndex: number) => {
    const updatedLevels = [...formData.levels_config];
    updatedLevels[levelIndex].ammunition_config = updatedLevels[levelIndex].ammunition_config.filter((_, i) => i !== ammoIndex);
    setFormData({ ...formData, levels_config: updatedLevels });
  };

  const startEdit = (protocol: Protocol) => {
    setEditingProtocol(protocol);
    setFormData({
      name: protocol.name,
      description: protocol.description || '',
      levels_config: protocol.levels_config || [],
    });
  };

  const cancelEdit = () => {
    setEditingProtocol(null);
    setFormData({ name: '', description: '', levels_config: [] });
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Protocols</h1>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Add Protocol
        </button>
      </div>

      {/* Create/Edit Form */}
      {(showCreateForm || editingProtocol) && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">
            {editingProtocol ? 'Edit Protocol' : 'Create Protocol'}
          </h2>
          <form onSubmit={editingProtocol ? handleUpdate : handleCreate}>
            <div className="grid grid-cols-1 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium mb-1">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full border rounded p-2"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full border rounded p-2"
                />
              </div>
            </div>

            {/* Levels Configuration */}
            <div className="mb-4">
              <div className="flex justify-between items-center mb-2">
                <h3 className="font-semibold">Protocol Levels</h3>
                <button
                  type="button"
                  onClick={addLevel}
                  className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700"
                >
                  Add Level
                </button>
              </div>
              {formData.levels_config.map((level, levelIndex) => (
                <div key={levelIndex} className="bg-gray-50 p-4 rounded mb-3 border border-gray-200">
                  <div className="flex justify-end items-center mb-2">
                    <button
                      type="button"
                      onClick={() => removeLevel(levelIndex)}
                      className="text-red-600 hover:text-red-900 text-sm"
                    >
                      Remove Level
                    </button>
                  </div>
                  <div className="mb-3">
                    <label className="block text-xs font-medium mb-1">Level Name</label>
                    <input
                      type="text"
                      value={level.level_name}
                      onChange={(e) => updateLevel(levelIndex, 'level_name', e.target.value)}
                      className="w-full border rounded p-2 text-sm"
                    />
                  </div>
                  
                  {/* Ammunition Configuration for this level */}
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs font-medium text-gray-600">Ammunition Configuration</span>
                      <button
                        type="button"
                        onClick={() => addAmmunitionToLevel(levelIndex)}
                        className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                      >
                        Add Ammunition
                      </button>
                    </div>
                    {level.ammunition_config.map((ammo, ammoIndex) => (
                      <div key={ammoIndex} className="bg-white p-3 rounded mb-2 border border-gray-100">
                        <div className="flex justify-between items-center mb-2">
                          <span className="text-xs font-medium">Ammunition {ammoIndex + 1}</span>
                          <button
                            type="button"
                            onClick={() => removeAmmunitionFromLevel(levelIndex, ammoIndex)}
                            className="text-red-600 hover:text-red-900 text-xs"
                          >
                            Remove
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-xs font-medium mb-1">Ammunition</label>
                            <select
                              value={ammo.ammunition_id}
                              onChange={(e) => updateAmmunitionInLevel(levelIndex, ammoIndex, 'ammunition_id', e.target.value)}
                              className="w-full border rounded p-2 text-xs"
                            >
                              <option value="">Select ammunition...</option>
                              {ammunition?.map((ammoType) => (
                                <option key={ammoType.id} value={ammoType.id}>
                                  {ammoType.name} - {ammoType.caliber}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="block text-xs font-medium mb-1">Reference Velocity (m/s)</label>
                            <input
                              type="number"
                              step="0.1"
                              value={ammo.reference_velocity_m_s}
                              onChange={(e) => updateAmmunitionInLevel(levelIndex, ammoIndex, 'reference_velocity_m_s', parseFloat(e.target.value))}
                              className="w-full border rounded p-2 text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium mb-1">Velocity Window (±m/s)</label>
                            <input
                              type="number"
                              step="0.1"
                              value={ammo.velocity_window_m_s}
                              onChange={(e) => updateAmmunitionInLevel(levelIndex, ammoIndex, 'velocity_window_m_s', parseFloat(e.target.value))}
                              className="w-full border rounded p-2 text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium mb-1">Shots per Panel</label>
                            <input
                              type="number"
                              value={ammo.shots_per_panel}
                              onChange={(e) => updateAmmunitionInLevel(levelIndex, ammoIndex, 'shots_per_panel', parseInt(e.target.value))}
                              className="w-full border rounded p-2 text-xs"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={editingProtocol ? cancelEdit : () => setShowCreateForm(false)}
                className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                {editingProtocol ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Protocols Table */}
      {!editingProtocol && (
        <div className="bg-white rounded-lg shadow">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Levels</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {protocols?.map((protocol) => (
                <tr key={protocol.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{protocol.name}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{protocol.description || '-'}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {protocol.levels_config?.length || 0} level(s)
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => startEdit(protocol)}
                      className="text-indigo-600 hover:text-indigo-900 mr-3"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteTarget(protocol)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {protocols?.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-4 text-center text-sm text-gray-500">
                    No protocols found. Click "Add Protocol" to create one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteTarget && (
        <ConfirmModal
          title="Delete Protocol"
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
