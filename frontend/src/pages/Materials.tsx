import { useState } from 'react';
import { useMaterials, useCreateMaterial, useUpdateMaterial, useDeleteMaterial, useUploadMaterialFiles, useRemoveMaterialFile } from '../hooks/useMaterials';
import { Material, MaterialCreate, MaterialUpdate } from '../api/materials';
import { ConfirmModal } from '../components/ConfirmModal';
import { normalizeString } from '../utils/string';
import { useAuth } from '../hooks/useAuth';

export function Materials() {
  const { data: materials, isLoading, error, refetch } = useMaterials();
  const createMutation = useCreateMaterial();
  const updateMutation = useUpdateMaterial();
  const uploadFilesMutation = useUploadMaterialFiles();
  const deleteMutation = useDeleteMaterial();
  const removeFileMutation = useRemoveMaterialFile();
  const { role } = useAuth();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingMaterial, setEditingMaterial] = useState<Material | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Material | null>(null);
  const [fileToRemove, setFileToRemove] = useState<{ material: Material; fileType: 'mss' | 'sds' } | null>(null);
  const [mssFile, setMssFile] = useState<File | null>(null);
  const [sdsFile, setSdsFile] = useState<File | null>(null);
  const [pendingMssDelete, setPendingMssDelete] = useState(false);
  const [pendingSdsDelete, setPendingSdsDelete] = useState(false);
  const [showFileReplaceModal, setShowFileReplaceModal] = useState(false);
  const [fileToReplace, setFileToReplace] = useState<{ type: 'mss' | 'sds', file: File } | null>(null);
  const [formData, setFormData] = useState<MaterialCreate>({
    name: '',
    material_class: '',
    manufacturer: '',
    areal_density_g_m2: null,
    thickness_mm: null,
    thickness_tolerance_mm: null,
    material_function: '',
    ply_count: null,
    ply_orientations: null,
  });

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading materials</div>;

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const files: { mss?: File; sds?: File } = {};
      if (mssFile) files.mss = mssFile;
      if (sdsFile) files.sds = sdsFile;
      await createMutation.mutateAsync({ material: formData, files });
      setShowCreateForm(false);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null, created_by_username: '' });
      setMssFile(null);
      setSdsFile(null);
    } catch (err) {
      console.error('Failed to create material:', err);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMaterial) return;
    try {
      const updatePayload = Object.fromEntries(
        Object.entries(formData).filter(([, v]) => v !== '' && v !== undefined)
      ) as MaterialUpdate;
      await updateMutation.mutateAsync({ id: editingMaterial.id, material: updatePayload });

      // Execute pending file operations
      const fileOperations = [];
      
      // Handle file uploads
      if (mssFile) fileOperations.push(uploadFilesMutation.mutateAsync({ id: editingMaterial.id, files: { mss: mssFile } }));
      if (sdsFile) fileOperations.push(uploadFilesMutation.mutateAsync({ id: editingMaterial.id, files: { sds: sdsFile } }));
      
      // Handle file deletions
      if (pendingMssDelete) fileOperations.push(removeFileMutation.mutateAsync({ id: editingMaterial.id, fileType: 'mss' }));
      if (pendingSdsDelete) fileOperations.push(removeFileMutation.mutateAsync({ id: editingMaterial.id, fileType: 'sds' }));
      
      if (fileOperations.length > 0) {
        try {
          await Promise.all(fileOperations);
          refetch();
        } catch (uploadError) {
          console.error('Failed to process file operations:', uploadError);
          alert('Material updated but file operations failed. Please try again.');
        }
      }

      setEditingMaterial(null);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null });
      setMssFile(null);
      setSdsFile(null);
      setPendingMssDelete(false);
      setPendingSdsDelete(false);
    } catch (err) {
      console.error('Failed to update material:', err);
      alert('Failed to update material. Please try again.');
    }
  };

  const handleFileChange = (type: 'mss' | 'sds', file: File | null) => {
    if (!file || !editingMaterial) return;
    
    // Check if a file already exists
    const existingFile = type === 'mss' ? editingMaterial.mss_file_path : editingMaterial.sds_file_path;
    if (existingFile) {
      setFileToReplace({ type, file });
      setShowFileReplaceModal(true);
    } else {
      if (type === 'mss') {
        setMssFile(file);
        setPendingMssDelete(false); // Clear pending delete if uploading
      } else {
        setSdsFile(file);
        setPendingSdsDelete(false); // Clear pending delete if uploading
      }
    }
  };

  const handleFileReplaceConfirm = () => {
    if (!fileToReplace) return;
    
    if (fileToReplace.type === 'mss') {
      setMssFile(fileToReplace.file);
      setPendingMssDelete(false); // Clear pending delete if uploading
    } else {
      setSdsFile(fileToReplace.file);
      setPendingSdsDelete(false); // Clear pending delete if uploading
    }
    
    setShowFileReplaceModal(false);
    setFileToReplace(null);
  };

  const handleFileReplaceCancel = () => {
    setShowFileReplaceModal(false);
    setFileToReplace(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch (err) {
      console.error('Failed to delete material:', err);
    } finally {
      setDeleteTarget(null);
    }
  };

  const handlePendingDelete = (fileType: 'mss' | 'sds') => {
    if (fileType === 'mss') {
      setPendingMssDelete(true);
      setMssFile(null); // Clear any pending upload
    } else {
      setPendingSdsDelete(true);
      setSdsFile(null); // Clear any pending upload
    }
  };

  const cancelPendingDelete = (fileType: 'mss' | 'sds') => {
    if (fileType === 'mss') {
      setPendingMssDelete(false);
    } else {
      setPendingSdsDelete(false);
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
      thickness_tolerance_mm: material.thickness_tolerance_mm,
      material_function: material.material_function || '',
      ply_count: material.ply_count,
      ply_orientations: material.ply_orientations,
    });
  };

  const cancelEdit = () => {
    setEditingMaterial(null);
    setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null });
    setMssFile(null);
    setSdsFile(null);
    setPendingMssDelete(false);
    setPendingSdsDelete(false);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Materials Library</h1>
        {role !== 'viewer' && (
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            {showCreateForm ? 'Cancel' : 'Add Material'}
          </button>
        )}
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
                  <option value="fabric">Fabric</option>
                  <option value="ceramic">Ceramic</option>
                  <option value="metal">Metal</option>
                  <option value="foam">Foam</option>
                  <option value="rubber">Rubber</option>
                  <option value="film">Film</option>
                  <option value="coating">Coating</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Function *</label>
                <select
                  required
                  value={formData.material_function || ''}
                  onChange={(e) => setFormData({ ...formData, material_function: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select function...</option>
                  <option value="antiballistic">Antiballistic</option>
                  <option value="anti-trauma">Anti-Trauma</option>
                  <option value="anti-AP">Anti-AP</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Manufacturer *</label>
                <input
                  type="text"
                  required
                  value={formData.manufacturer || ''}
                  onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Areal Density (g/m²) *</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={formData.areal_density_g_m2 ?? ''}
                  onChange={(e) => setFormData({ ...formData, areal_density_g_m2: e.target.value ? parseFloat(e.target.value) : null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Thickness (mm) *</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.001"
                    required
                    value={formData.thickness_mm ?? ''}
                    onChange={(e) => setFormData({ ...formData, thickness_mm: e.target.value ? parseFloat(e.target.value) : null })}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                  />
                  <input
                    type="text"
                    value={formData.thickness_tolerance_mm || ''}
                    onChange={(e) => setFormData({ ...formData, thickness_tolerance_mm: e.target.value })}
                    placeholder="±"
                    className="mt-1 w-20 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Ply Count: {formData.ply_count ?? 1}</label>
                <input
                  type="range"
                  min="1"
                  max="6"
                  step="1"
                  value={formData.ply_count ?? 1}
                  onChange={(e) => {
                    const newPlyCount = parseInt(e.target.value);
                    setFormData({ ...formData, ply_count: newPlyCount });
                    // Initialize ply_orientations array when ply_count changes
                    if (newPlyCount > 1) {
                      setFormData(prev => ({ ...prev, ply_orientations: Array(newPlyCount).fill(0) }));
                    } else if (newPlyCount === 1) {
                      setFormData(prev => ({ ...prev, ply_orientations: [0] }));
                    }
                  }}
                  className="mt-1 block w-full"
                />
                <p className="mt-1 text-xs text-gray-500">Number of plies in this material (for multi-ply orientation configuration)</p>
              </div>
              {formData.ply_count && formData.ply_count > 1 && (
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Ply Orientations (degrees) - {formData.ply_count} plies
                  </label>
                  <div className="mt-1 grid grid-cols-2 md:grid-cols-4 gap-2">
                    {Array.from({ length: formData.ply_count }).map((_, plyIndex) => (
                      <div key={plyIndex}>
                        <label className="block text-xs text-gray-500 mb-1">Ply {plyIndex + 1}</label>
                        <input
                          type="number"
                          step="0.01"
                          value={formData.ply_orientations?.[plyIndex] ?? ''}
                          onChange={(e) => {
                            const newOrientations = [...(formData.ply_orientations || [])];
                            newOrientations[plyIndex] = e.target.value ? parseFloat(e.target.value) : 0;
                            setFormData({ ...formData, ply_orientations: newOrientations });
                          }}
                          placeholder="0"
                          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-1"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {editingMaterial && role === 'admin' && (
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
              <div>
                <label className="block text-sm font-medium text-gray-700">MSS (Material Specification Sheet)</label>
                {editingMaterial && editingMaterial.mss_file_path && !pendingMssDelete && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <a
                      href={`/api/v1/materials/${editingMaterial.id}/download/mss`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-900 text-sm"
                    >
                      Current file: {editingMaterial.mss_original_filename || editingMaterial.mss_file_path}
                    </a>
                    <button
                      type="button"
                      onClick={() => handlePendingDelete('mss')}
                      className="text-red-600 hover:text-red-900 text-xs"
                      title="Remove file"
                    >
                      ✕ Remove
                    </button>
                  </div>
                )}
                {pendingMssDelete && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <span className="text-orange-600 text-sm">File will be deleted on update</span>
                    <button
                      type="button"
                      onClick={() => cancelPendingDelete('mss')}
                      className="text-indigo-600 hover:text-indigo-900 text-xs"
                      title="Cancel deletion"
                    >
                      ✕ Cancel
                    </button>
                  </div>
                )}
                {mssFile && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <span className="text-green-600 text-sm">New file: {mssFile.name} (will upload on update)</span>
                    <button
                      type="button"
                      onClick={() => setMssFile(null)}
                      className="text-red-600 hover:text-red-900 text-xs"
                      title="Cancel upload"
                    >
                      ✕ Cancel
                    </button>
                  </div>
                )}
                <input
                  type="file"
                  onChange={(e) => handleFileChange('mss', e.target.files?.[0] || null)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">SDS (Safety Data Sheet)</label>
                {editingMaterial && editingMaterial.sds_file_path && !pendingSdsDelete && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <a
                      href={`/api/v1/materials/${editingMaterial.id}/download/sds`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-900 text-sm"
                    >
                      Current file: {editingMaterial.sds_original_filename || editingMaterial.sds_file_path}
                    </a>
                    <button
                      type="button"
                      onClick={() => handlePendingDelete('sds')}
                      className="text-red-600 hover:text-red-900 text-xs"
                      title="Remove file"
                    >
                      ✕ Remove
                    </button>
                  </div>
                )}
                {pendingSdsDelete && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <span className="text-orange-600 text-sm">File will be deleted on update</span>
                    <button
                      type="button"
                      onClick={() => cancelPendingDelete('sds')}
                      className="text-indigo-600 hover:text-indigo-900 text-xs"
                      title="Cancel deletion"
                    >
                      ✕ Cancel
                    </button>
                  </div>
                )}
                {sdsFile && (
                  <div className="mt-1 mb-2 flex items-center space-x-2">
                    <span className="text-green-600 text-sm">New file: {sdsFile.name} (will upload on update)</span>
                    <button
                      type="button"
                      onClick={() => setSdsFile(null)}
                      className="text-red-600 hover:text-red-900 text-xs"
                      title="Cancel upload"
                    >
                      ✕ Cancel
                    </button>
                  </div>
                )}
                <input
                  type="file"
                  onChange={(e) => handleFileChange('sds', e.target.files?.[0] || null)}
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

      {!(showCreateForm || editingMaterial) && (
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Class</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Manufacturer</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Areal Density (g/m²)</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Thickness (mm)</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created By</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Files</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {materials?.map((material) => (
              <tr key={material.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{material.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {normalizeString(material.material_class) || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.manufacturer || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.areal_density_g_m2 ? Math.round(Number(material.areal_density_g_m2)) : '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.thickness_mm ? Number(material.thickness_mm).toFixed(2) : '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.created_by_username || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <div className="space-x-2">
                    {material.mss_file_path && (
                      <a
                        href={`/api/v1/materials/${material.id}/download/mss`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        MSS
                      </a>
                    )}
                    {material.sds_file_path && (
                      <a
                        href={`/api/v1/materials/${material.id}/download/sds`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        SDS
                      </a>
                    )}
                    {!material.mss_file_path && !material.sds_file_path && '-'}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {role !== 'viewer' && (
                    <>
                      <button
                        onClick={() => startEdit(material)}
                        className="text-indigo-600 hover:text-indigo-900 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteTarget(material)}
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
            {materials?.length === 0 && (
              <tr>
                <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">
                  No materials found. Click "Add Material" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}
      {deleteTarget && (
        <ConfirmModal
          title="Delete Material"
          message={`Are you sure you want to delete "${deleteTarget.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
      {showFileReplaceModal && fileToReplace && (
        <ConfirmModal
          title="Replace File"
          message={`This will permanently remove the existing ${fileToReplace.type === 'mss' ? 'MSS' : 'SDS'} file and replace it with "${fileToReplace.file.name}". This action cannot be undone.`}
          confirmLabel="Replace"
          variant="danger"
          onConfirm={handleFileReplaceConfirm}
          onCancel={handleFileReplaceCancel}
        />
      )}
    </div>
  );
}
