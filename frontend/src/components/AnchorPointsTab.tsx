import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

interface AnchorPoint {
  id: string;
  name: string;
  description: string;
  ammunition_scope: 'all' | 'calibers';
  caliber_ids: string[];
  expected_perforated: boolean;
  expected_bfd_mm: number;
  custom_velocity_mps: number;
  layers: Array<{
    id: string;
    material_id: string;
    material_name: string;
    layer_count: number;
    layer_index: number;
  }>;
  created_by_id: string;
  created_by_username: string;
  created_at: string;
  updated_at: string;
  batch_id?: string | null;
}

interface AnchorPointsTabProps {
  onError: (error: string) => void;
}

export const AnchorPointsTab: React.FC<AnchorPointsTabProps> = ({ onError }) => {
  const [anchorPoints, setAnchorPoints] = useState<AnchorPoint[]>([]);
  const [anchorLoading, setAnchorLoading] = useState(false);
  const [showAnchorForm, setShowAnchorForm] = useState(false);
  const [editingAnchor, setEditingAnchor] = useState<AnchorPoint | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [anchorToDelete, setAnchorToDelete] = useState<string | null>(null);
  const [anchorForm, setAnchorForm] = useState({
    name: '',
    description: '',
    ammunition_scope: 'all' as 'all' | 'calibers',
    caliber_ids: [] as string[],
    expected_perforated: false,
    expected_bfd_mm: '',
    custom_velocity_mps: '',
    layers: [] as Array<{ material_id: string; layer_count: number; layer_index: number }>
  });
  const [batchMode, setBatchMode] = useState(false);
  const [materials, setMaterials] = useState<any[]>([]);
  const [calibers, setCalibers] = useState<string[]>([]);

  // Fetch anchor points
  useEffect(() => {
    const fetchAnchorPoints = async () => {
      try {
        const result = await apiClient.get<any>('/api/v1/anchor-points');
        setAnchorPoints(result || []);
      } catch (err: any) {
        onError(err.detail || 'Failed to fetch anchor points');
      }
    };
    fetchAnchorPoints();
  }, []);

  // Fetch materials and ammunition for anchor form
  useEffect(() => {
    const fetchMaterials = async () => {
      try {
        const result = await apiClient.get<any>('/api/v1/materials');
        setMaterials(result || []);
      } catch (err: any) {
        console.error('Failed to fetch materials:', err);
      }
    };
    const fetchAmmunition = async () => {
      try {
        const result = await apiClient.get<any>('/api/v1/ammunition');
        // Extract unique calibers
        const uniqueCalibers = Array.from(new Set((result || []).map((a: any) => a.caliber).filter((c: any) => c)));
        setCalibers(uniqueCalibers);
      } catch (err: any) {
        console.error('Failed to fetch ammunition:', err);
      }
    };
    fetchMaterials();
    fetchAmmunition();
  }, []);

  // Handle ESC key to close modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showDeleteModal) {
          handleCancelDelete();
        }
      }
      if (e.key === 'Delete' && showDeleteModal) {
        handleConfirmDelete();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showDeleteModal, anchorToDelete]);

  const handleAddLayer = () => {
    const newLayer = {
      material_id: '',
      layer_count: 1,
      layer_index: anchorForm.layers.length
    };
    setAnchorForm({
      ...anchorForm,
      layers: [...anchorForm.layers, newLayer]
    });
  };

  const handleRemoveLayer = (index: number) => {
    setAnchorForm({
      ...anchorForm,
      layers: anchorForm.layers.filter((_, i) => i !== index).map((l, i) => ({ ...l, layer_index: i }))
    });
  };

  const handleLayerChange = (index: number, field: string, value: any) => {
    setAnchorForm({
      ...anchorForm,
      layers: anchorForm.layers.map((l, i) => i === index ? { ...l, [field]: value } : l)
    });
  };

  const handleSaveAnchor = async () => {
    setAnchorLoading(true);
    try {
      // Convert empty strings to None for numeric fields
      const payload = {
        ...anchorForm,
        expected_bfd_mm: anchorForm.expected_bfd_mm ? parseFloat(anchorForm.expected_bfd_mm) : null,
        custom_velocity_mps: anchorForm.custom_velocity_mps ? parseFloat(anchorForm.custom_velocity_mps) : null
      };
      
      if (editingAnchor) {
        await apiClient.put<any>(`/api/v1/anchor-points/${editingAnchor.id}`, payload);
      } else {
        if (batchMode) {
          // Create batch anchor points - one for each material
          await apiClient.post<any>('/api/v1/anchor-points/batch', payload);
        } else {
          // Create single anchor point
          await apiClient.post<any>('/api/v1/anchor-points', payload);
        }
      }
      setShowAnchorForm(false);
      setEditingAnchor(null);
      setAnchorForm({
        name: '',
        description: '',
        ammunition_scope: 'all',
        caliber_ids: [],
        expected_perforated: false,
        expected_bfd_mm: '',
        custom_velocity_mps: '',
        layers: []
      });
      setBatchMode(false);
      // Refresh anchor points
      const result = await apiClient.get<any>('/api/v1/anchor-points');
      setAnchorPoints(result || []);
    } catch (err: any) {
      onError(err.detail || 'Failed to save anchor point');
    } finally {
      setAnchorLoading(false);
    }
  };

  const handleEditAnchor = (anchor: AnchorPoint) => {
    setEditingAnchor(anchor);
    setAnchorForm({
      name: anchor.name,
      description: anchor.description || '',
      ammunition_scope: anchor.ammunition_scope,
      caliber_ids: anchor.caliber_ids || [],
      expected_perforated: anchor.expected_perforated,
      expected_bfd_mm: anchor.expected_bfd_mm?.toString() || '',
      custom_velocity_mps: anchor.custom_velocity_mps?.toString() || '',
      layers: anchor.layers?.map((l: any) => ({
        material_id: l.material_id,
        layer_count: l.layer_count,
        layer_index: l.layer_index
      })) || []
    });
    setShowAnchorForm(true);
  };

  const handleDeleteAnchor = async (id: string) => {
    setAnchorToDelete(id);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    if (!anchorToDelete) return;
    setAnchorLoading(true);
    try {
      // Check if this is part of a batch
      const anchor = anchorPoints.find(a => a.id === anchorToDelete);
      if (anchor && anchor.batch_id) {
        // Delete all anchor points in the batch
        const batchAnchors = anchorPoints.filter(a => a.batch_id === anchor.batch_id);
        await Promise.all(batchAnchors.map(a => apiClient.delete<any>(`/api/v1/anchor-points/${a.id}`)));
      } else {
        // Delete single anchor point
        await apiClient.delete<any>(`/api/v1/anchor-points/${anchorToDelete}`);
      }
      const result = await apiClient.get<any>('/api/v1/anchor-points');
      setAnchorPoints(result || []);
    } catch (err: any) {
      onError(err.detail || 'Failed to delete anchor point');
    } finally {
      setAnchorLoading(false);
      setShowDeleteModal(false);
      setAnchorToDelete(null);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setAnchorToDelete(null);
  };

  const handleCancelEdit = () => {
    setShowAnchorForm(false);
    setEditingAnchor(null);
    setAnchorForm({
      name: '',
      description: '',
      ammunition_scope: 'all',
      caliber_ids: [],
      expected_perforated: false,
      expected_bfd_mm: '',
      custom_velocity_mps: '',
      layers: []
    });
    setBatchMode(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Anchor Points</h2>
          <button
            onClick={() => setShowAnchorForm(true)}
            className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
          >
            Add Anchor Point
          </button>
        </div>
        <p className="text-sm text-gray-600">
          Anchor points are synthetic training data that represent known boundary conditions (e.g., 10,000 layers will stop any bullet).
          These are used for model training but do not appear in analytics.
        </p>
      </div>

      {/* Anchor Point Form */}
      {showAnchorForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">{editingAnchor ? 'Edit Anchor Point' : 'Add Anchor Point'}</h3>
          {!editingAnchor && (
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">Creation Mode</label>
              <div className="flex space-x-4">
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="single"
                    checked={!batchMode}
                    onChange={() => setBatchMode(false)}
                    className="mr-2"
                  />
                  Single Composition
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="batch"
                    checked={batchMode}
                    onChange={() => setBatchMode(true)}
                    className="mr-2"
                  />
                  Multiple Materials (separate points)
                </label>
              </div>
              {batchMode && (
                <p className="text-xs text-gray-500 mt-1">
                  This will create a separate anchor point for each material layer with the same settings.
                </p>
              )}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Name</label>
              <input
                type="text"
                value={anchorForm.name}
                onChange={(e) => setAnchorForm({ ...anchorForm, name: e.target.value })}
                className="w-full border rounded p-2"
                placeholder="e.g., 10,000 layers absolute stop"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <textarea
                value={anchorForm.description}
                onChange={(e) => setAnchorForm({ ...anchorForm, description: e.target.value })}
                className="w-full border rounded p-2"
                rows={2}
                placeholder="Optional description"
              />
            </div>

            {/* Ammunition Scope */}
            <div>
              <label className="block text-sm font-medium mb-1">Ammunition Scope</label>
              <div className="flex space-x-4">
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="all"
                    checked={anchorForm.ammunition_scope === 'all'}
                    onChange={(e) => setAnchorForm({ ...anchorForm, ammunition_scope: e.target.value as 'all' | 'calibers' })}
                    className="mr-2"
                  />
                  All Available Ammunition
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="calibers"
                    checked={anchorForm.ammunition_scope === 'calibers'}
                    onChange={(e) => setAnchorForm({ ...anchorForm, ammunition_scope: e.target.value as 'all' | 'calibers' })}
                    className="mr-2"
                  />
                  Specific Calibers
                </label>
              </div>
            </div>

            {/* Caliber Selection */}
            {anchorForm.ammunition_scope === 'calibers' && (
              <div>
                <label className="block text-sm font-medium mb-1">Select Calibers</label>
                <div className="max-h-40 overflow-y-auto border rounded p-2 space-y-2">
                  {calibers.map((caliber) => (
                    <label key={caliber} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={anchorForm.caliber_ids.includes(caliber)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAnchorForm({ ...anchorForm, caliber_ids: [...anchorForm.caliber_ids, caliber] });
                          } else {
                            setAnchorForm({ ...anchorForm, caliber_ids: anchorForm.caliber_ids.filter(id => id !== caliber) });
                          }
                        }}
                        className="mr-2"
                      />
                      <span className="text-sm">{caliber}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Layers */}
            <div>
              <label className="block text-sm font-medium mb-1">Material Composition</label>
              <div className="space-y-2">
                {anchorForm.layers.map((layer, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <select
                      value={layer.material_id}
                      onChange={(e) => handleLayerChange(index, 'material_id', e.target.value)}
                      className="flex-1 border rounded p-2"
                    >
                      <option value="">Select material</option>
                      {materials.map((mat) => (
                        <option key={mat.id} value={mat.id}>{mat.name}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={layer.layer_count}
                      onChange={(e) => handleLayerChange(index, 'layer_count', parseInt(e.target.value))}
                      className="w-24 border rounded p-2"
                      min="1"
                      placeholder="Layers"
                    />
                    <button
                      onClick={() => handleRemoveLayer(index)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  onClick={handleAddLayer}
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  + Add Material Layer
                </button>
              </div>
            </div>

            {/* Expected Outcome */}
            <div>
              <label className="block text-sm font-medium mb-1">Expected Perforated</label>
              <select
                value={anchorForm.expected_perforated.toString()}
                onChange={(e) => setAnchorForm({ ...anchorForm, expected_perforated: e.target.value === 'true' })}
                className="w-full border rounded p-2"
              >
                <option value="false">No (Stopped)</option>
                <option value="true">Yes (Penetrated)</option>
              </select>
            </div>

            {!anchorForm.expected_perforated && (
              <div>
                <label className="block text-sm font-medium mb-1">Expected BFD (mm)</label>
                <input
                  type="number"
                  value={anchorForm.expected_bfd_mm}
                  onChange={(e) => setAnchorForm({ ...anchorForm, expected_bfd_mm: e.target.value })}
                  className="w-full border rounded p-2"
                  placeholder="e.g., 0, 5, 10"
                />
              </div>
            )}

            {/* Custom Velocity */}
            <div>
              <label className="block text-sm font-medium mb-1">Custom Velocity (m/s) - Optional</label>
              <input
                type="number"
                value={anchorForm.custom_velocity_mps}
                onChange={(e) => setAnchorForm({ ...anchorForm, custom_velocity_mps: e.target.value })}
                className="w-full border rounded p-2"
                placeholder="Leave empty to use nominal velocity from ammunition"
              />
            </div>

            {/* Actions */}
            <div className="flex space-x-2">
              <button
                onClick={handleSaveAnchor}
                disabled={anchorLoading}
                className="bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700 disabled:bg-gray-400"
              >
                {anchorLoading ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={handleCancelEdit}
                className="bg-gray-600 text-white py-2 px-4 rounded hover:bg-gray-700"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Anchor Points List */}
      {!showAnchorForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Existing Anchor Points ({anchorPoints.length})</h3>
          {anchorPoints.length === 0 ? (
            <p className="text-sm text-gray-600">No anchor points defined yet.</p>
          ) : (
            <div className="space-y-4">
              {(() => {
                // Group anchor points by batch_id
                const groupedAnchors = anchorPoints.reduce((acc, anchor) => {
                  if (anchor.batch_id) {
                    if (!acc[anchor.batch_id]) {
                      acc[anchor.batch_id] = [];
                    }
                    acc[anchor.batch_id].push(anchor);
                  } else {
                    acc[anchor.id] = [anchor];
                  }
                  return acc;
                }, {} as Record<string, AnchorPoint[]>);

                return Object.values(groupedAnchors).map((group) => {
                  if (group.length === 1) {
                    const anchor = group[0];
                    return (
                      <div key={anchor.id} className="border rounded p-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-medium">{anchor.name}</h4>
                            {anchor.description && <p className="text-sm text-gray-600">{anchor.description}</p>}
                            <div className="mt-2 text-sm">
                              <div><strong>Scope:</strong> {anchor.ammunition_scope === 'all' ? 'All ammunition' : `Calibers: ${anchor.caliber_ids?.join(', ')}`}</div>
                              <div><strong>Composition:</strong> {anchor.layers?.map((l: any) => `${l.layer_count}x ${l.material_name}`).join(' + ')}</div>
                              <div><strong>Expected:</strong> {anchor.expected_perforated ? 'Penetrated' : `Stopped (${anchor.expected_bfd_mm}mm BFD)`}</div>
                              {anchor.custom_velocity_mps && <div><strong>Velocity:</strong> {anchor.custom_velocity_mps} m/s</div>}
                              <div className="text-xs text-gray-500">Created by {anchor.created_by_username}</div>
                            </div>
                          </div>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleEditAnchor(anchor)}
                              className="text-blue-600 hover:text-blue-800 text-sm"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteAnchor(anchor.id)}
                              className="text-red-600 hover:text-red-800 text-sm"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  } else {
                    // Batch group
                    const baseName = group[0].name.split(' - ')[0];
                    return (
                      <div key={group[0].batch_id} className="border rounded p-4 bg-gray-50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="font-medium">{baseName}</h4>
                            <p className="text-xs text-gray-500 mb-2">Batch ({group.length} materials)</p>
                            <div className="mt-2 text-sm">
                              <div><strong>Scope:</strong> {group[0].ammunition_scope === 'all' ? 'All ammunition' : `Calibers: ${group[0].caliber_ids?.join(', ')}`}</div>
                              <div><strong>Expected:</strong> {group[0].expected_perforated ? 'Penetrated' : `Stopped (${group[0].expected_bfd_mm}mm BFD)`}</div>
                              {group[0].custom_velocity_mps && <div><strong>Velocity:</strong> {group[0].custom_velocity_mps} m/s</div>}
                              <div className="text-xs text-gray-500">Created by {group[0].created_by_username}</div>
                            </div>
                            <div className="mt-2 pl-4 border-l-2 border-gray-300">
                              {group.map((anchor) => (
                                <div key={anchor.id} className="text-sm py-1">
                                  <strong>{anchor.layers?.map((l: any) => `${l.layer_count}x ${l.material_name}`).join(' + ')}</strong>
                                </div>
                              ))}
                            </div>
                          </div>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleEditAnchor(group[0])}
                              className="text-blue-600 hover:text-blue-800 text-sm"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteAnchor(group[0].id)}
                              className="text-red-600 hover:text-red-800 text-sm"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  }
                });
              })()}
            </div>
          )}
        </div>
      )}
    {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={handleCancelDelete} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Delete Anchor Point</h3>
            <p className="text-sm text-gray-600 mb-4">
              Are you sure you want to delete this anchor point? This action cannot be undone.
              {anchorToDelete && anchorPoints.find(a => a.id === anchorToDelete)?.batch_id && (
                <span className="block mt-2 text-red-600 font-medium">
                  This will delete all {anchorPoints.filter(a => a.batch_id === anchorPoints.find(x => x.id === anchorToDelete)?.batch_id).length} anchor points in this batch.
                </span>
              )}
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={handleCancelDelete}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={anchorLoading}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {anchorLoading ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
