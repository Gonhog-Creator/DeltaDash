import { useState } from 'react';
import { useMaterials, useCreateMaterial, useUpdateMaterial, useDeleteMaterial, useUploadMaterialFiles } from '../hooks/useMaterials';
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
  const { role } = useAuth();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingMaterial, setEditingMaterial] = useState<Material | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Material | null>(null);
  const [mssFile, setMssFile] = useState<File | null>(null);
  const [sdsFile, setSdsFile] = useState<File | null>(null);
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
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '' });
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

      // Upload files if any are selected
      if (mssFile || sdsFile) {
        const files: { mss?: File; sds?: File } = {};
        if (mssFile) files.mss = mssFile;
        if (sdsFile) files.sds = sdsFile;
        try {
          await uploadFilesMutation.mutateAsync({ id: editingMaterial.id, files });
          refetch(); // Refresh the materials list to show updated filenames
        } catch (uploadError) {
          console.error('Failed to upload files:', uploadError);
          alert('Material updated but file upload failed. Please try uploading files again.');
        }
      }

      setEditingMaterial(null);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '' });
      setMssFile(null);
      setSdsFile(null);
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
      } else {
        setSdsFile(file);
      }
    }
  };

  const handleFileReplaceConfirm = () => {
    if (!fileToReplace) return;
    
    if (fileToReplace.type === 'mss') {
      setMssFile(fileToReplace.file);
    } else {
      setSdsFile(fileToReplace.file);
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
    });
  };

  const cancelEdit = () => {
    setEditingMaterial(null);
    setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '' });
    setMssFile(null);
    setSdsFile(null);
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
                <label className="block text-sm font-medium text-gray-700">MSS (Material Specification Sheet)</label>
                {editingMaterial && editingMaterial.mss_file_path && (
                  <div className="mt-1 mb-2">
                    <a
                      href={`https://deltadash-backend-production.up.railway.app/api/v1/materials/${editingMaterial.id}/download/mss`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-900 text-sm"
                    >
                      Current file: {editingMaterial.mss_original_filename || editingMaterial.mss_file_path}
                    </a>
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
                {editingMaterial && editingMaterial.sds_file_path && (
                  <div className="mt-1 mb-2">
                    <a
                      href={`https://deltadash-backend-production.up.railway.app/api/v1/materials/${editingMaterial.id}/download/sds`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-900 text-sm"
                    >
                      Current file: {editingMaterial.sds_original_filename || editingMaterial.sds_file_path}
                    </a>
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
                        href={`https://deltadash-backend-production.up.railway.app/api/v1/materials/${material.id}/download/mss`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        MSS
                      </a>
                    )}
                    {material.sds_file_path && (
                      <a
                        href={`https://deltadash-backend-production.up.railway.app/api/v1/materials/${material.id}/download/sds`}
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
      {fileToRemove && (
        <ConfirmModal
          title="Remove File"
          message={`Are you sure you want to remove the ${fileToRemove.fileType === 'mss' ? 'MSS' : 'SDS'} file from "${fileToRemove.material.name}"? This action cannot be undone.`}
          confirmLabel="Remove"
          variant="danger"
          onConfirm={handleRemoveFileConfirm}
          onCancel={() => setFileToRemove(null)}
        />
      )}
    </div>
  );
}
