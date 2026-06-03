import { useState } from 'react';
import { useMaterials, useCreateMaterial, useUpdateMaterial, useDeleteMaterial, useUploadMaterialFiles, useRemoveMaterialFile } from '../hooks/useMaterials';
import { Material, MaterialCreate, MaterialUpdate, MaterialVestUsageResponse } from '../api/materials';
import { ConfirmModal } from '../components/ConfirmModal';
import { normalizeString } from '../utils/string';
import { useAuth } from '../hooks/useAuth';
import { useViewerMode } from '../contexts/ViewerModeContext';
import { materialsApi } from '../api/materials';

export function Materials() {
  const { data: materials, isLoading, error, refetch } = useMaterials();
  const createMutation = useCreateMaterial();
  const updateMutation = useUpdateMaterial();
  const uploadFilesMutation = useUploadMaterialFiles();
  const deleteMutation = useDeleteMaterial();
  const removeFileMutation = useRemoveMaterialFile();
  const { role } = useAuth();
  const { isViewerMode } = useViewerMode();
  
  const canViewComplete = role === 'admin' || role === 'editor';

  const shouldShowElongationFields = (materialClass: string | null) => {
    const allowedClasses = ['fabric', 'foam', 'UHMWPE', 'aramid'];
    return materialClass ? allowedClasses.includes(materialClass) : false;
  };

  const calculateForcePerCm = (force: number | null, testLength: string | null) => {
    if (!force || !testLength) return null;
    const lengthInCm = testLength === '5cm' ? 5 : 2.5;
    return force / lengthInCm;
  };

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
  const [errorInputValues, setErrorInputValues] = useState<Record<string, string>>({});
  const [sortField, setSortField] = useState<keyof Material | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filterField, setFilterField] = useState<'material_class' | 'manufacturer' | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<string[]>([]);
  const [activeFilterField, setActiveFilterField] = useState<'material_class' | 'manufacturer' | null>(null);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [vestUsage, setVestUsage] = useState<MaterialVestUsageResponse | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [loadingVestUsage, setLoadingVestUsage] = useState(false);
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
    elongation_longitudinal_percent: null,
    elongation_longitudinal_error_percent: null,
    force_longitudinal_newtons: null,
    force_longitudinal_error_percent: null,
    elongation_transverse_percent: null,
    elongation_transverse_error_percent: null,
    force_transverse_newtons: null,
    force_transverse_error_percent: null,
    stretch_test_length: '5cm',
    fabric_composition_ids: null,
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
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null, elongation_longitudinal_percent: null, elongation_longitudinal_error_percent: null, force_longitudinal_newtons: null, force_longitudinal_error_percent: null, elongation_transverse_percent: null, elongation_transverse_error_percent: null, force_transverse_newtons: null, force_transverse_error_percent: null, stretch_test_length: '5cm', fabric_composition_ids: null, created_by_username: '' });
      setErrorInputValues({});
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
        } catch (uploadError) {
          console.error('Failed to process file operations:', uploadError);
          alert('Material updated but file operations failed. Please try again.');
        }
      }

      // Always refetch to get fresh data from server
      refetch();

      setEditingMaterial(null);
      setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null, elongation_longitudinal_percent: null, elongation_longitudinal_error_percent: null, force_longitudinal_newtons: null, force_longitudinal_error_percent: null, elongation_transverse_percent: null, elongation_transverse_error_percent: null, force_transverse_newtons: null, force_transverse_error_percent: null, stretch_test_length: '5cm', fabric_composition_ids: null });
      setErrorInputValues({});
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
    if (!file) return;
    
    // If editing, check if a file already exists and show replace modal
    if (editingMaterial) {
      const existingFile = type === 'mss' ? editingMaterial.mss_file_path : editingMaterial.sds_file_path;
      if (existingFile) {
        setFileToReplace({ type, file });
        setShowFileReplaceModal(true);
        return;
      }
    }
    
    // Set the file for upload
    if (type === 'mss') {
      setMssFile(file);
      setPendingMssDelete(false); // Clear pending delete if uploading
    } else {
      setSdsFile(file);
      setPendingSdsDelete(false); // Clear pending delete if uploading
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
      elongation_longitudinal_percent: material.elongation_longitudinal_percent,
      elongation_longitudinal_error_percent: material.elongation_longitudinal_error_percent,
      force_longitudinal_newtons: material.force_longitudinal_newtons,
      force_longitudinal_error_percent: material.force_longitudinal_error_percent,
      elongation_transverse_percent: material.elongation_transverse_percent,
      elongation_transverse_error_percent: material.elongation_transverse_error_percent,
      force_transverse_newtons: material.force_transverse_newtons,
      force_transverse_error_percent: material.force_transverse_error_percent,
      stretch_test_length: material.stretch_test_length || '5cm',
      fabric_composition_ids: material.fabric_composition_ids,
      created_by_username: material.created_by_username,
    });
    setErrorInputValues({
      elongation_longitudinal_error_percent: material.elongation_longitudinal_error_percent?.toString() || '',
      elongation_transverse_error_percent: material.elongation_transverse_error_percent?.toString() || '',
      force_longitudinal_error_percent: material.force_longitudinal_error_percent?.toString() || '',
      force_transverse_error_percent: material.force_transverse_error_percent?.toString() || '',
    });
  };

  const cancelEdit = () => {
    setEditingMaterial(null);
    setFormData({ name: '', material_class: '', manufacturer: '', areal_density_g_m2: null, thickness_mm: null, thickness_tolerance_mm: null, material_function: '', ply_count: null, ply_orientations: null, elongation_longitudinal_percent: null, elongation_longitudinal_error_percent: null, force_longitudinal_newtons: null, force_longitudinal_error_percent: null, elongation_transverse_percent: null, elongation_transverse_error_percent: null, force_transverse_newtons: null, force_transverse_error_percent: null, stretch_test_length: '5cm', fabric_composition_ids: null });
    setErrorInputValues({});
    setMssFile(null);
    setSdsFile(null);
    setPendingMssDelete(false);
    setPendingSdsDelete(false);
  };

  const isMaterialComplete = (material: Material) => {
    const allowedClasses = ['fabric', 'foam', 'UHMWPE', 'aramid'];
    const hasElongationFields = material.material_class ? allowedClasses.includes(material.material_class) : false;
    
    const requiredFields = [
      material.areal_density_g_m2,
      material.thickness_mm,
    ];
    
    if (hasElongationFields) {
      requiredFields.push(
        material.elongation_longitudinal_percent,
        material.elongation_longitudinal_error_percent,
        material.force_longitudinal_newtons,
        material.force_longitudinal_error_percent,
        material.elongation_transverse_percent,
        material.elongation_transverse_error_percent,
        material.force_transverse_newtons,
        material.force_transverse_error_percent
      );
    }
    
    // Compressed plates must have fabric composition selected
    if (material.material_class === 'compressed_plate') {
      requiredFields.push(material.fabric_composition_ids);
    }
    
    return requiredFields.every(field => field !== null && field !== undefined && field !== '');
  };

  const handleSort = (field: keyof Material) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getFilteredAndSortedMaterials = (materials: Material[] | undefined) => {
    if (!materials) return materials;
    
    let filtered = materials;
    
    // Apply filter
    if (activeFilterField && activeFilters.length > 0) {
      filtered = materials.filter(material => {
        const value = material[activeFilterField];
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
      const numericFields = ['areal_density_g_m2', 'thickness_mm', 'ply_count', 'density_g_cm3', 
                            'tensile_strength_mpa', 'modulus_gpa', 'elongation_longitudinal_percent',
                            'elongation_longitudinal_error_percent', 'force_longitudinal_newtons',
                            'force_longitudinal_error_percent', 'elongation_transverse_percent',
                            'elongation_transverse_error_percent', 'force_transverse_newtons',
                            'force_transverse_error_percent'];
      
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

  const getUniqueValues = (field: 'material_class' | 'manufacturer') => {
    if (!materials) return [];
    const values = materials
      .map(m => m[field])
      .filter((v): v is string => v !== null && v !== undefined);
    return Array.from(new Set(values)).sort();
  };

  const normalizeFilterValue = (value: string, field: 'material_class' | 'manufacturer') => {
    if (field === 'material_class') {
      return normalizeString(value);
    }
    return value;
  };

  const evaluateMathExpression = (value: string): number | null => {
    if (!value.trim()) return null;
    
    // Check if it's a simple number
    if (!/[\/*+\-]/.test(value)) {
      const parsed = parseFloat(value);
      return isNaN(parsed) ? null : parsed;
    }
    
    try {
      // Safe evaluation of simple math expressions
      // Only allow numbers, basic operators, and parentheses
      const sanitized = value.replace(/[^0-9\.\+\-\*\/\(\)\s]/g, '');
      const result = Function('"use strict"; return (' + sanitized + ')')();
      
      if (typeof result === 'number' && !isNaN(result) && isFinite(result)) {
        // Multiply by 100 to get percentage and round to 2 decimal places
        return Math.round(result * 100 * 100) / 100;
      }
      return null;
    } catch {
      return null;
    }
  };

  const handlePercentageErrorBlur = (fieldName: keyof MaterialCreate, value: string) => {
    const evaluated = evaluateMathExpression(value);
    setFormData({ ...formData, [fieldName]: evaluated });
    setErrorInputValues({ ...errorInputValues, [fieldName]: evaluated !== null ? evaluated.toString() : '' });
  };

  const handleMaterialClick = async (material: Material) => {
    setSelectedMaterial(material);
    setShowDetailsModal(true);
    setLoadingVestUsage(true);
    try {
      const usage = await materialsApi.getVestUsage(material.id);
      setVestUsage(usage);
    } catch (err) {
      console.error('Failed to fetch vest usage:', err);
      setVestUsage(null);
    } finally {
      setLoadingVestUsage(false);
    }
  };

  const handleCloseDetailsModal = () => {
    setSelectedMaterial(null);
    setVestUsage(null);
    setShowDetailsModal(false);
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
                  <option value="fabric">Fabric</option>
                  <option value="ceramic">Ceramic</option>
                  <option value="metal">Metal</option>
                  <option value="steel">Steel</option>
                  <option value="foam">Foam</option>
                  <option value="rubber">Rubber</option>
                  <option value="compressed_plate">Compressed Plate</option>
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
              {shouldShowElongationFields(formData.material_class) && (
              <div className="md:col-span-2">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Elongation & Force Measurements</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Longitudinal Force (N)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.force_longitudinal_newtons ?? ''}
                        onChange={(e) => setFormData({ ...formData, force_longitudinal_newtons: e.target.value ? parseFloat(e.target.value) : null })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                      {formData.force_longitudinal_newtons && (
                        <div className="mt-1 text-xs text-gray-600">
                          Force/cm: {calculateForcePerCm(formData.force_longitudinal_newtons, formData.stretch_test_length)?.toFixed(2) || '-'} N/cm
                        </div>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Longitudinal Force Error (%)</label>
                      <input
                        type="text"
                        step="0.01"
                        value={errorInputValues.force_longitudinal_error_percent ?? formData.force_longitudinal_error_percent ?? ''}
                        onChange={(e) => setErrorInputValues({ ...errorInputValues, force_longitudinal_error_percent: e.target.value })}
                        onBlur={(e) => handlePercentageErrorBlur('force_longitudinal_error_percent', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Longitudinal % Elongation</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.elongation_longitudinal_percent ?? ''}
                        onChange={(e) => setFormData({ ...formData, elongation_longitudinal_percent: e.target.value ? parseFloat(e.target.value) : null })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Longitudinal Error (%)</label>
                      <input
                        type="text"
                        step="0.01"
                        value={errorInputValues.elongation_longitudinal_error_percent ?? formData.elongation_longitudinal_error_percent ?? ''}
                        onChange={(e) => setErrorInputValues({ ...errorInputValues, elongation_longitudinal_error_percent: e.target.value })}
                        onBlur={(e) => handlePercentageErrorBlur('elongation_longitudinal_error_percent', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Transverse Force (N)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.force_transverse_newtons ?? ''}
                        onChange={(e) => setFormData({ ...formData, force_transverse_newtons: e.target.value ? parseFloat(e.target.value) : null })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                      {formData.force_transverse_newtons && (
                        <div className="mt-1 text-xs text-gray-600">
                          Force/cm: {calculateForcePerCm(formData.force_transverse_newtons, formData.stretch_test_length)?.toFixed(2) || '-'} N/cm
                        </div>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Transverse Force Error (%)</label>
                      <input
                        type="text"
                        step="0.01"
                        value={errorInputValues.force_transverse_error_percent ?? formData.force_transverse_error_percent ?? ''}
                        onChange={(e) => setErrorInputValues({ ...errorInputValues, force_transverse_error_percent: e.target.value })}
                        onBlur={(e) => handlePercentageErrorBlur('force_transverse_error_percent', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Transverse % Elongation</label>
                      <input
                        type="number"
                        step="0.01"
                        value={formData.elongation_transverse_percent ?? ''}
                        onChange={(e) => setFormData({ ...formData, elongation_transverse_percent: e.target.value ? parseFloat(e.target.value) : null })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700">Transverse Error (%)</label>
                      <input
                        type="text"
                        step="0.01"
                        value={errorInputValues.elongation_transverse_error_percent ?? formData.elongation_transverse_error_percent ?? ''}
                        onChange={(e) => setErrorInputValues({ ...errorInputValues, elongation_transverse_error_percent: e.target.value })}
                        onBlur={(e) => handlePercentageErrorBlur('elongation_transverse_error_percent', e.target.value)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700">Test Strip Length</label>
                      <div className="mt-2 flex items-center space-x-4">
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="stretch_test_length"
                            value="5cm"
                            checked={formData.stretch_test_length === '5cm'}
                            onChange={(e) => setFormData({ ...formData, stretch_test_length: e.target.value })}
                            className="mr-2"
                          />
                          <span className="text-sm text-gray-700">5cm</span>
                        </label>
                        <label className="flex items-center">
                          <input
                            type="radio"
                            name="stretch_test_length"
                            value="2.5cm"
                            checked={formData.stretch_test_length === '2.5cm'}
                            onChange={(e) => setFormData({ ...formData, stretch_test_length: e.target.value })}
                            className="mr-2"
                          />
                          <span className="text-sm text-gray-700">2.5cm</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
              {formData.material_class === 'compressed_plate' && (
                <div className="md:col-span-2">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Fabric Composition</h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Select Fabrics</label>
                    <div className="mt-2 space-y-2 max-h-48 overflow-y-auto border rounded-md p-2">
                      {materials?.filter(m => 
                        m.material_class === 'fabric' || 
                        m.material_class === 'aramid' || 
                        m.material_class === 'UHMWPE'
                      ).map(fabric => (
                        <label key={fabric.id} className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={formData.fabric_composition_ids?.includes(fabric.id) || false}
                            onChange={(e) => {
                              const currentIds = formData.fabric_composition_ids || [];
                              if (e.target.checked) {
                                setFormData({ ...formData, fabric_composition_ids: [...currentIds, fabric.id] });
                              } else {
                                setFormData({ ...formData, fabric_composition_ids: currentIds.filter(id => id !== fabric.id) });
                              }
                            }}
                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="text-sm text-gray-700">{fabric.name}</span>
                          <span className="text-xs text-gray-500">({fabric.material_class})</span>
                        </label>
                      ))}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">Select the fabrics that make up this compressed plate</p>
                  </div>
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
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('name')}
              >
                Name {sortField === 'name' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('material_class')}
              >
                <div className="flex items-center gap-1">
                  <span>Class</span>
                  <span>{sortField === 'material_class' && (sortDirection === 'asc' ? '↑' : '↓')}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setFilterField('material_class');
                      setSelectedFilters(activeFilterField === 'material_class' ? [...activeFilters] : []);
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
                onClick={() => handleSort('manufacturer')}
              >
                <div className="flex items-center gap-1">
                  <span>Manufacturer</span>
                  <span>{sortField === 'manufacturer' && (sortDirection === 'asc' ? '↑' : '↓')}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setFilterField('manufacturer');
                      setSelectedFilters(activeFilterField === 'manufacturer' ? [...activeFilters] : []);
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
                onClick={() => handleSort('areal_density_g_m2')}
              >
                Areal Density (g/m²) {sortField === 'areal_density_g_m2' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th 
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort('thickness_mm')}
              >
                Thickness (mm) {sortField === 'thickness_mm' && (sortDirection === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ply</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Files</th>
              {canViewComplete && !isViewerMode && (
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Complete</th>
              )}
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {getFilteredAndSortedMaterials(materials)?.map((material) => (
              <tr 
                key={material.id} 
                className="hover:bg-gray-50 cursor-pointer"
                onClick={() => handleMaterialClick(material)}
              >
                <td className="px-6 py-4 text-sm font-medium text-gray-900 break-words">{material.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {normalizeString(material.material_class) || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.manufacturer || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.areal_density_g_m2 ? Math.round(Number(material.areal_density_g_m2)) : '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.thickness_mm ? Number(material.thickness_mm).toFixed(2) : '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{material.ply_count ?? '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  <div className="space-x-2">
                    {material.mss_file_path && (
                      <a
                        href={`/api/v1/materials/${material.id}/download/mss`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-600 hover:text-indigo-900"
                        onClick={(e) => e.stopPropagation()}
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
                        onClick={(e) => e.stopPropagation()}
                      >
                        SDS
                      </a>
                    )}
                    {!material.mss_file_path && !material.sds_file_path && '-'}
                  </div>
                </td>
                {canViewComplete && !isViewerMode && (
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {isMaterialComplete(material) && (
                      <span className="text-green-500 text-lg">✓</span>
                    )}
                  </td>
                )}
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  {role !== 'viewer' && (
                    <>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startEdit(material);
                        }}
                        className="text-indigo-600 hover:text-indigo-900 mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(material);
                        }}
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
                <td colSpan={canViewComplete && !isViewerMode ? 9 : 8} className="px-6 py-4 text-center text-sm text-gray-500">
                  No materials found. Click "Add Material" to create one.
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
      {filterField && (
        <ConfirmModal
          title={`Filter by ${filterField === 'material_class' ? 'Class' : 'Manufacturer'}`}
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
                  <span className="text-sm text-gray-700">{normalizeFilterValue(value, filterField)}</span>
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
      {showDetailsModal && selectedMaterial && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={handleCloseDetailsModal} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Material Details</h3>
              <button
                onClick={handleCloseDetailsModal}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            
            {/* Material Info */}
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Material Information</h4>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Name:</span>
                  <span className="ml-2 font-medium">{selectedMaterial.name}</span>
                </div>
                <div>
                  <span className="text-gray-500">Class:</span>
                  <span className="ml-2 font-medium">{normalizeString(selectedMaterial.material_class) || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Manufacturer:</span>
                  <span className="ml-2 font-medium">{selectedMaterial.manufacturer || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Function:</span>
                  <span className="ml-2 font-medium">{selectedMaterial.material_function || '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Thickness:</span>
                  <span className="ml-2 font-medium">{selectedMaterial.thickness_mm ? `${selectedMaterial.thickness_mm} mm` : '-'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Ply Count:</span>
                  <span className="ml-2 font-medium">{selectedMaterial.ply_count ?? '-'}</span>
                </div>
                {selectedMaterial.ply_count && selectedMaterial.ply_count > 1 && (
                  <div>
                    <span className="text-gray-500">Ply Orientations:</span>
                    <span className="ml-2 font-medium">{selectedMaterial.ply_orientations ? selectedMaterial.ply_orientations.join(', ') : '-'}</span>
                  </div>
                )}
                <div className="md:col-start-3">
                  <span className="text-gray-500">Areal Density:</span>
                  <span className="ml-2 font-medium">
                    {selectedMaterial.areal_density_g_m2 ? `${selectedMaterial.areal_density_g_m2} g/m² (${(selectedMaterial.areal_density_g_m2 * 0.00204816).toFixed(3)} lb/ft²)` : '-'}
                  </span>
                </div>
              </div>
              
              {shouldShowElongationFields(selectedMaterial.material_class) && (
                <div className="mt-4 pt-4 border-t">
                  <h5 className="text-xs font-medium text-gray-600 mb-2">Elongation & Force Measurements</h5>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                    <div>
                      <span className="text-gray-500">Longitudinal Force:</span>
                      <span className="ml-1">{selectedMaterial.force_longitudinal_newtons ? `${selectedMaterial.force_longitudinal_newtons} N` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Longitudinal Force Error:</span>
                      <span className="ml-1">{selectedMaterial.force_longitudinal_error_percent ? `${selectedMaterial.force_longitudinal_error_percent}%` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Longitudinal Elongation:</span>
                      <span className="ml-1">{selectedMaterial.elongation_longitudinal_percent ? `${selectedMaterial.elongation_longitudinal_percent}%` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Longitudinal Error:</span>
                      <span className="ml-1">{selectedMaterial.elongation_longitudinal_error_percent ? `${selectedMaterial.elongation_longitudinal_error_percent}%` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Transverse Force:</span>
                      <span className="ml-1">{selectedMaterial.force_transverse_newtons ? `${selectedMaterial.force_transverse_newtons} N` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Transverse Force Error:</span>
                      <span className="ml-1">{selectedMaterial.force_transverse_error_percent ? `${selectedMaterial.force_transverse_error_percent}%` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Transverse Elongation:</span>
                      <span className="ml-1">{selectedMaterial.elongation_transverse_percent ? `${selectedMaterial.elongation_transverse_percent}%` : '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Transverse Error:</span>
                      <span className="ml-1">{selectedMaterial.elongation_transverse_error_percent ? `${selectedMaterial.elongation_transverse_error_percent}%` : '-'}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Vest Usage */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">Vest Usage</h4>
              {loadingVestUsage ? (
                <div className="text-sm text-gray-500">Loading vest usage...</div>
              ) : vestUsage && vestUsage.total_vests > 0 ? (
                <div>
                  <div className="text-sm text-gray-600 mb-2">Used in {vestUsage.total_vests} vest(s)</div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full border border-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Vest Code</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Vest Name</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Type</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Threat Level</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Layers</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vestUsage.vest_usage.map((vest) => (
                          <tr key={vest.vest_id} className="border-b">
                            <td className="px-4 py-2 text-sm">{vest.vest_code}</td>
                            <td className="px-4 py-2 text-sm">{vest.vest_name || '-'}</td>
                            <td className="px-4 py-2 text-sm">{vest.vest_type || '-'}</td>
                            <td className="px-4 py-2 text-sm">{vest.threat_level || '-'}</td>
                            <td className="px-4 py-2 text-sm font-medium">{vest.layer_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-gray-500">This material is not used in any vests.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
