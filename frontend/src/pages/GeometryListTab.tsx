import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useGeometries, useCreateGeometry, useUpdateGeometry, useDeleteGeometry, Geometry, GeometryCreate, GeometryUpdate, GeometrySizeMeasurements, geometriesApi } from '../hooks/useGeometries';
import { API_BASE_URL } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { ConfirmModal } from '../components/ConfirmModal';

const SIZE_OPTIONS = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL'];
const MEASUREMENT_KEYS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N'];

function emptyGeometryCreate(): GeometryCreate {
  return {
    name: '',
    description: null,
    vest_type: '',
    surface_areas: {},
    available_sizes: [],
    includes_hard_plates: false,
    is_approved: true,
    size_measurements: {},
    pdf_document: null,
    image_url: null,
    compatibility: null,
  };
}

function buildGeometryCreateFromGeometry(g: Geometry): GeometryCreate {
  return {
    name: g.name,
    description: g.description,
    vest_type: g.vest_type,
    surface_areas: g.surface_areas || {},
    available_sizes: g.available_sizes || [],
    includes_hard_plates: g.includes_hard_plates,
    is_approved: g.is_approved,
    size_measurements: g.size_measurements || {},
    pdf_document: g.pdf_document,
    image_url: g.image_url,
    compatibility: g.compatibility,
  };
}

function imageUrl(url: string | null): string {
  if (!url) return '';
  if (url.startsWith('/api/')) return `${API_BASE_URL}${url}`;
  return url;
}

export function GeometryListTab() {
  const { data: geometries, isLoading, error } = useGeometries();
  const createMutation = useCreateGeometry();
  const updateMutation = useUpdateGeometry();
  const deleteMutation = useDeleteGeometry();
  const { role } = useAuth();
  const queryClient = useQueryClient();

  const canEdit = role !== 'viewer';

  const [editing, setEditing] = useState<Geometry | null>(null);
  const [formData, setFormData] = useState<GeometryCreate>(emptyGeometryCreate());
  const [selectedSize, setSelectedSize] = useState<string>('');
  const [deleteTarget, setDeleteTarget] = useState<Geometry | null>(null);
  const [pdfUploading, setPdfUploading] = useState<boolean>(false);
  const [imageUploading, setImageUploading] = useState<boolean>(false);
  const [viewing, setViewing] = useState<Geometry | null>(null);

  useEffect(() => {
    if (!viewing) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setViewing(null);
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [viewing]);

  const ensureSize = (size: string) => {
    if (!size) return;
    setFormData(prev => {
      const available = new Set(prev.available_sizes || []);
      available.add(size);
      const measurements = { ...prev.size_measurements };
      if (!measurements[size]) {
        measurements[size] = { front: {}, back: {} };
      }
      const surface = { ...prev.surface_areas };
      if (!surface[size]) {
        surface[size] = { front: 0, back: 0, total: 0 };
      }
      return { ...prev, available_sizes: Array.from(available), size_measurements: measurements, surface_areas: surface };
    });
  };

  const removeSize = (size: string) => {
    setFormData(prev => {
      const available = prev.available_sizes?.filter(s => s !== size) || [];
      const measurements = { ...prev.size_measurements };
      delete measurements[size];
      const surface = { ...prev.surface_areas };
      delete surface[size];
      return { ...prev, available_sizes: available, size_measurements: measurements, surface_areas: surface };
    });
    if (selectedSize === size) setSelectedSize('');
  };

  const updateSizeMeasurement = (size: string, panel: 'front' | 'back', key: string, value: number | null) => {
    setFormData(prev => {
      const measurements = { ...prev.size_measurements };
      const panelData = { ...measurements[size]?.[panel] };
      if (value === null) {
        delete panelData[key];
      } else {
        panelData[key] = value;
      }
      measurements[size] = { ...measurements[size], [panel]: panelData } as GeometrySizeMeasurements;
      return { ...prev, size_measurements: measurements };
    });
  };

  const updateSurfaceArea = (size: string, field: 'front' | 'back' | 'total', value: number | null) => {
    setFormData(prev => {
      const surface = { ...prev.surface_areas };
      surface[size] = { ...surface[size], [field]: value === null ? 0 : value };
      return { ...prev, surface_areas: surface };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || formData.available_sizes.length === 0) return;
    try {
      if (editing) {
        const update: GeometryUpdate = { ...formData };
        await updateMutation.mutateAsync({ id: editing.id, geometry: update });
      } else {
        await createMutation.mutateAsync(formData);
      }
      resetForm();
    } catch (err) {
      console.error('Failed to save geometry:', err);
    }
  };

  const resetForm = () => {
    setEditing(null);
    setFormData(emptyGeometryCreate());
    setSelectedSize('');
  };

  const startEdit = (g: Geometry) => {
    setEditing(g);
    setFormData(buildGeometryCreateFromGeometry(g));
    setSelectedSize(g.available_sizes?.[0] || '');
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch (err) {
      console.error('Failed to delete geometry:', err);
    } finally {
      setDeleteTarget(null);
    }
  };

  const handlePdfUpload = async (file: File) => {
    if (!editing?.id) return;
    setPdfUploading(true);
    try {
      const updated = await geometriesApi.uploadPdf(editing.id, file);
      setFormData(prev => ({ ...prev, pdf_document: updated.pdf_document }));
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    } catch (err) {
      console.error('Failed to upload geometry PDF:', err);
      alert('Failed to upload geometry PDF. Please try again.');
    } finally {
      setPdfUploading(false);
    }
  };

  const handlePdfDelete = async () => {
    if (!editing?.id) return;
    if (!confirm('Remove this geometry PDF?')) return;
    try {
      const updated = await geometriesApi.deletePdf(editing.id);
      setFormData(prev => ({ ...prev, pdf_document: updated.pdf_document }));
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    } catch (err) {
      console.error('Failed to delete geometry PDF:', err);
      alert('Failed to delete geometry PDF. Please try again.');
    }
  };

  const handleImageUpload = async (file: File) => {
    if (!editing?.id) return;
    setImageUploading(true);
    try {
      const updated = await geometriesApi.uploadImage(editing.id, file);
      setFormData(prev => ({ ...prev, image_url: updated.image_url }));
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    } catch (err) {
      console.error('Failed to upload geometry image:', err);
      alert('Failed to upload geometry image. Please try again.');
    } finally {
      setImageUploading(false);
    }
  };

  const handleImageDelete = async () => {
    if (!editing?.id) return;
    if (!confirm('Remove this geometry image?')) return;
    try {
      const updated = await geometriesApi.deleteImage(editing.id);
      setFormData(prev => ({ ...prev, image_url: updated.image_url }));
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    } catch (err) {
      console.error('Failed to delete geometry image:', err);
      alert('Failed to delete geometry image. Please try again.');
    }
  };

  const handlePdfDownload = async (geometryId: string, filename?: string) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(geometriesApi.downloadPdf(geometryId), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) throw new Error('Failed to download PDF');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'geometry.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download geometry PDF:', err);
      alert('Failed to download PDF. Please try again.');
    }
  };

  if (isLoading) return <div className="p-6">Loading geometries...</div>;
  if (error) return <div className="p-6 text-red-600">Error loading geometries.</div>;

  return (
    <>
      <div className="flex justify-end items-center gap-3">
        {canEdit && !editing && (
          <button
            onClick={() => setEditing({} as Geometry)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Add Geometry
          </button>
        )}
      </div>

      {editing && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">{editing.id ? 'Edit Geometry' : 'Create Geometry'}</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Vest Type</label>
                <select
                  value={formData.vest_type || ''}
                  onChange={e => setFormData({ ...formData, vest_type: e.target.value || null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select...</option>
                  <option value="Soft">Soft</option>
                  <option value="Hard">Hard</option>
                  <option value="Hybrid">Hybrid</option>
                  <option value="IWC">IWC</option>
                </select>
              </div>
              <div className="md:col-span-3">
                <label className="block text-sm font-medium text-gray-700">Description</label>
                <input
                  type="text"
                  value={formData.description || ''}
                  onChange={e => setFormData({ ...formData, description: e.target.value || null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div className="md:col-span-3">
                <label className="block text-sm font-medium text-gray-700">Compatibility</label>
                <input
                  type="text"
                  placeholder="e.g., Compatible con: STOP II - STOP III - ULTRA STOP III"
                  value={formData.compatibility || ''}
                  onChange={e => setFormData({ ...formData, compatibility: e.target.value || null })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                />
              </div>
              <div className="md:col-span-3 flex gap-6">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.includes_hard_plates || false}
                    onChange={e => setFormData({ ...formData, includes_hard_plates: e.target.checked })}
                    className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-gray-700">Includes Hard Plates</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.is_approved ?? true}
                    onChange={e => setFormData({ ...formData, is_approved: e.target.checked })}
                    className="mr-2 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-gray-700">Approved</span>
                </label>
              </div>
            </div>

            <div className="border-t pt-4">
              <h3 className="text-md font-medium text-gray-900 mb-3">Geometry PDF</h3>
              {editing?.id ? (
                <div className="space-y-2">
                  {formData.pdf_document ? (
                    <div className="flex flex-wrap items-center gap-3 bg-gray-50 p-3 rounded-md">
                      <span className="text-sm text-gray-700 truncate max-w-xs">
                        {formData.pdf_document.original_name}
                      </span>
                      <button
                        type="button"
                        onClick={() => handlePdfDownload(editing.id, formData.pdf_document?.original_name)}
                        className="text-indigo-600 hover:text-indigo-900 text-sm"
                      >
                        Download
                      </button>
                      {canEdit && (
                        <button
                          type="button"
                          onClick={handlePdfDelete}
                          disabled={pdfUploading}
                          className="text-red-600 hover:text-red-900 text-sm disabled:opacity-50"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ) : (
                    <input
                      type="file"
                      accept=".pdf"
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) handlePdfUpload(file);
                      }}
                      disabled={pdfUploading}
                      className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
                    />
                  )}
                  {pdfUploading && <span className="text-sm text-gray-500">Uploading...</span>}
                </div>
              ) : (
                <p className="text-sm text-gray-500">Save the geometry before uploading a PDF.</p>
              )}
            </div>

            <div className="border-t pt-4">
              <h3 className="text-md font-medium text-gray-900 mb-3">Geometry Image</h3>
              {editing?.id ? (
                <div className="space-y-2">
                  {formData.image_url ? (
                    <div className="space-y-2">
                      <img
                        src={imageUrl(formData.image_url)}
                        alt={`${formData.name} preview`}
                        className="max-h-40 h-auto border rounded-md"
                      />
                      <div className="flex flex-wrap items-center gap-3 bg-gray-50 p-3 rounded-md">
                        {canEdit && (
                          <label className="text-indigo-600 hover:text-indigo-900 text-sm cursor-pointer">
                            Replace
                            <input
                              type="file"
                              accept=".png,.jpg,.jpeg,.gif,.webp"
                              onChange={e => {
                                const file = e.target.files?.[0];
                                if (file) handleImageUpload(file);
                              }}
                              disabled={imageUploading}
                              className="hidden"
                            />
                          </label>
                        )}
                        {canEdit && (
                          <button
                            type="button"
                            onClick={handleImageDelete}
                            disabled={imageUploading}
                            className="text-red-600 hover:text-red-900 text-sm disabled:opacity-50"
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    </div>
                  ) : (
                    <input
                      type="file"
                      accept=".png,.jpg,.jpeg,.gif,.webp"
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) handleImageUpload(file);
                      }}
                      disabled={imageUploading}
                      className="block w-full text-sm text-gray-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
                    />
                  )}
                  {imageUploading && <span className="text-sm text-gray-500">Uploading...</span>}
                </div>
              ) : (
                <p className="text-sm text-gray-500">Save the geometry before uploading an image.</p>
              )}
            </div>

            <div className="border-t pt-4">
              <h3 className="text-md font-medium text-gray-900 mb-3">Sizes, Surface Areas & Measurements</h3>
              <div className="flex items-center gap-2 mb-4">
                <select
                  value={selectedSize}
                  onChange={e => setSelectedSize(e.target.value)}
                  className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">Select size to edit...</option>
                  {formData.available_sizes?.map(size => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
                <select
                  onChange={e => {
                    const newSize = e.target.value;
                    if (newSize) {
                      ensureSize(newSize);
                      setSelectedSize(newSize);
                      e.currentTarget.value = '';
                    }
                  }}
                  className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                >
                  <option value="">+ Add size</option>
                  {SIZE_OPTIONS.filter(s => !formData.available_sizes?.includes(s)).map(size => (
                    <option key={size} value={size}>{size}</option>
                  ))}
                </select>
                {selectedSize && (
                  <button
                    type="button"
                    onClick={() => removeSize(selectedSize)}
                    className="text-red-600 hover:text-red-900 text-sm"
                  >
                    Remove {selectedSize}
                  </button>
                )}
              </div>

              {selectedSize && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-gray-50 p-4 rounded-md">
                    <div>
                      <label className="block text-xs font-medium text-gray-700">Front Area (m2)</label>
                      <input
                        type="number"
                        step="0.001"
                        value={formData.surface_areas?.[selectedSize]?.front ?? ''}
                        onChange={e => updateSurfaceArea(selectedSize, 'front', e.target.value ? parseFloat(e.target.value) : null)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700">Back Area (m2)</label>
                      <input
                        type="number"
                        step="0.001"
                        value={formData.surface_areas?.[selectedSize]?.back ?? ''}
                        onChange={e => updateSurfaceArea(selectedSize, 'back', e.target.value ? parseFloat(e.target.value) : null)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700">Total Area (m2)</label>
                      <input
                        type="number"
                        step="0.001"
                        value={formData.surface_areas?.[selectedSize]?.total ?? ''}
                        onChange={e => updateSurfaceArea(selectedSize, 'total', e.target.value ? parseFloat(e.target.value) : null)}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {(['front', 'back'] as const).map(panel => (
                      <div key={panel} className="border rounded-md p-4">
                        <h4 className="text-sm font-medium text-gray-900 mb-2 capitalize">{panel} Measurements (mm)</h4>
                        <div className="grid grid-cols-3 gap-2">
                          {MEASUREMENT_KEYS.map(key => (
                            <div key={key}>
                              <label className="block text-xs font-medium text-gray-700">{key}</label>
                              <input
                                type="number"
                                step="0.1"
                                value={formData.size_measurements?.[selectedSize]?.[panel]?.[key] ?? ''}
                                onChange={e =>
                                  updateSizeMeasurement(
                                    selectedSize,
                                    panel,
                                    key,
                                    e.target.value ? parseFloat(e.target.value) : null
                                  )
                                }
                                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-1"
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={resetForm}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : editing?.id ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {!editing && (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sizes</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Compatibility</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Front Area M (m2)</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Back Area M (m2)</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Approved</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Image</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">PDF</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {geometries?.map(geometry => (
                <tr
                  key={geometry.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setViewing(geometry)}
                >
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{geometry.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{geometry.vest_type || '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{geometry.available_sizes?.join(', ') || '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">{geometry.compatibility || '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {geometry.available_sizes?.includes('M')
                      ? geometry.surface_areas?.['M']?.front ?? '-'
                      : '-'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {geometry.available_sizes?.includes('M')
                      ? geometry.surface_areas?.['M']?.back ?? '-'
                      : '-'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{geometry.is_approved ? 'Yes' : 'No'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{geometry.image_url ? 'Yes' : 'No'}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {geometry.pdf_document ? (
                      <span className="text-green-500 text-lg">&#10003;</span>
                    ) : (
                      <span className="text-red-500 text-lg">&#10007;</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right text-sm font-medium">
                    {canEdit && (
                      <>
                        <button
                          onClick={e => { e.stopPropagation(); startEdit(geometry); }}
                          className="text-indigo-600 hover:text-indigo-900 mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); setDeleteTarget(geometry); }}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {geometries?.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-6 py-4 text-center text-sm text-gray-500">
                    No geometries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewing(null)} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-auto p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="text-xl font-bold text-gray-900">{viewing.name}</h2>
                {viewing.description && <p className="text-sm text-gray-500 mt-1">{viewing.description}</p>}
              </div>
              <button
                onClick={() => setViewing(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="bg-gray-50 rounded-md p-3">
                <div className="text-xs font-medium text-gray-500 uppercase">Vest Type</div>
                <div className="text-sm text-gray-900 mt-1">{viewing.vest_type || '-'}</div>
              </div>
              <div className="bg-gray-50 rounded-md p-3">
                <div className="text-xs font-medium text-gray-500 uppercase">Sizes</div>
                <div className="text-sm text-gray-900 mt-1">{viewing.available_sizes?.join(', ') || '-'}</div>
              </div>
              <div className="bg-gray-50 rounded-md p-3">
                <div className="text-xs font-medium text-gray-500 uppercase">Approved</div>
                <div className="text-sm text-gray-900 mt-1">{viewing.is_approved ? 'Yes' : 'No'}</div>
              </div>
              <div className="bg-gray-50 rounded-md p-3">
                <div className="text-xs font-medium text-gray-500 uppercase">Hard Plates</div>
                <div className="text-sm text-gray-900 mt-1">{viewing.includes_hard_plates ? 'Yes' : 'No'}</div>
              </div>
            </div>

            {viewing.compatibility && (
              <div className="mb-4 p-3 bg-indigo-50 border border-indigo-200 rounded-md">
                <div className="text-xs font-medium text-indigo-600 uppercase">Compatibility</div>
                <div className="text-sm text-gray-900 mt-1">{viewing.compatibility}</div>
              </div>
            )}

            {viewing.image_url && (
              <div className="mb-4 bg-gray-50 rounded-md p-4">
                <img
                  src={imageUrl(viewing.image_url)}
                  alt={viewing.name}
                  className="max-h-64 h-auto rounded-md mx-auto"
                />
              </div>
            )}

            {viewing.available_sizes && viewing.available_sizes.length > 0 && viewing.size_measurements && (
              <div className="overflow-auto border rounded-lg">
                <table className="w-full border-collapse text-xs text-center">
                  <thead>
                    <tr>
                      <th rowSpan={2} className="border border-gray-300 px-2 py-2 bg-gray-900 text-white font-bold uppercase sticky top-0 left-0 z-10">Cota</th>
                      {viewing.available_sizes.map(size => (
                        <th key={size} colSpan={2} className="border border-gray-300 px-2 py-1 bg-gray-900 text-white text-sm font-bold">{size}</th>
                      ))}
                    </tr>
                    <tr>
                      {viewing.available_sizes.flatMap(size => [
                        <th key={`${size}-front`} className="border border-gray-300 px-2 py-1 bg-gray-800 text-white font-medium uppercase">Front</th>,
                        <th key={`${size}-back`} className="border border-gray-300 px-2 py-1 bg-gray-800 text-white font-medium uppercase">Back</th>,
                      ])}
                    </tr>
                  </thead>
                  <tbody>
                    {MEASUREMENT_KEYS.map((key, idx) => {
                      const hasData = viewing.available_sizes?.some(
                        size => viewing.size_measurements?.[size]?.front?.[key] != null ||
                                viewing.size_measurements?.[size]?.back?.[key] != null
                      );
                      if (!hasData) return null;
                      return (
                        <tr key={key} className={idx % 2 ? 'bg-gray-50' : 'bg-white'}>
                          <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">{key}</td>
                          {viewing.available_sizes?.flatMap(size => [
                            <td key={`${size}-${key}-front`} className="border border-gray-300 px-2 py-1 text-gray-700">{viewing.size_measurements?.[size]?.front?.[key] ?? '---'}</td>,
                            <td key={`${size}-${key}-back`} className="border border-gray-300 px-2 py-1 text-gray-700">{viewing.size_measurements?.[size]?.back?.[key] ?? '---'}</td>,
                          ])}
                        </tr>
                      );
                    })}
                    <tr className="bg-indigo-50">
                      <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">Area (m2)</td>
                      {viewing.available_sizes?.flatMap(size => [
                        <td key={`${size}-area-front`} className="border border-gray-300 px-2 py-1 text-gray-700">{viewing.surface_areas?.[size]?.front ?? '---'}</td>,
                        <td key={`${size}-area-back`} className="border border-gray-300 px-2 py-1 text-gray-700">{viewing.surface_areas?.[size]?.back ?? '---'}</td>,
                      ])}
                    </tr>
                    <tr className="bg-indigo-100">
                      <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">Total area</td>
                      {viewing.available_sizes?.map(size => (
                        <td key={`${size}-total`} colSpan={2} className="border border-gray-300 px-2 py-1 font-bold text-gray-900">{viewing.surface_areas?.[size]?.total ?? '---'}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            )}

            <div className="flex justify-end space-x-3 mt-4">
              {viewing.pdf_document && (
                <button
                  onClick={() => handlePdfDownload(viewing.id, viewing.pdf_document?.original_name)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm"
                >
                  Download PDF
                </button>
              )}
              {canEdit && (
                <button
                  onClick={() => { startEdit(viewing); setViewing(null); }}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm"
                >
                  Edit
                </button>
              )}
              <button
                onClick={() => setViewing(null)}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {deleteTarget && (
        <ConfirmModal
          title="Delete Geometry"
          message={`Delete "${deleteTarget.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
}
