import { useState, useRef, useEffect, useMemo } from 'react';
import { useGeometries } from '../hooks/useGeometries';
import { useVestModels, useUploadDocument, useDeleteDocument } from '../hooks/useVestModels';
import { API_BASE_URL } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { exportGeometryPdf } from '../utils/geometryPdfExport';

const MEASUREMENT_KEYS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N'];

function normalizeText(value: string | null | undefined): string {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function getModelsFromCompat(compat: string | null | undefined): string[] {
  if (!compat) return [];
  const clean = normalizeText(compat)
    .replace(/^Compatible con:\s*/i, '')
    .replace(/EX PF II - PF III - FB II/gi, '');
  return clean
    .split(/[-–/()]/)
    .map(x => normalizeText(x))
    .filter(x => x.length > 1);
}

function imageUrl(url: string | null): string {
  if (!url) return '';
  if (url.startsWith('/api/')) return `${API_BASE_URL}${url}`;
  return url;
}

export function GeometryCompatibilityTab() {
  const { data: geometries, isLoading, error } = useGeometries();
  const { data: vestModels } = useVestModels();
  const uploadDocMutation = useUploadDocument();
  const deleteDocMutation = useDeleteDocument();
  const { role } = useAuth();

  const isAdmin = role === 'admin';

  const [selectedGeometryId, setSelectedGeometryId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [zoom, setZoom] = useState<number>(1);
  const [pdfExporting, setPdfExporting] = useState<boolean>(false);
  const [docUploading, setDocUploading] = useState<boolean>(false);
  const imageBoxRef = useRef<HTMLDivElement>(null);

  const modelsMap = useMemo(() => {
    const map: Record<string, string[]> = {};
    geometries?.forEach(g => {
      getModelsFromCompat(g.compatibility).forEach(model => {
        if (!map[model]) map[model] = [];
        if (!map[model].includes(g.id)) map[model].push(g.id);
      });
    });
    return map;
  }, [geometries]);

  const allModels = useMemo(() => {
    const set = new Set<string>([
      ...Object.keys(modelsMap),
      ...(vestModels?.map(m => m.name) || []),
    ]);
    return [...set].sort((a, b) => a.localeCompare(b, 'es'));
  }, [modelsMap, vestModels]);

  const selectedGeometry = useMemo(() => {
    return geometries?.find(g => g.id === selectedGeometryId) || null;
  }, [geometries, selectedGeometryId]);

  const selectedVestModel = useMemo(() => {
    return vestModels?.find(m => m.name === selectedModel) || null;
  }, [vestModels, selectedModel]);

  useEffect(() => {
    if (geometries && geometries.length > 0 && !selectedGeometryId) {
      setSelectedGeometryId(geometries[0].id);
    }
  }, [geometries, selectedGeometryId]);

  const setZoomValue = (value: number) => {
    setZoom(Math.max(0.55, Math.min(2.5, value)));
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (!selectedGeometry?.image_url) return;
    e.preventDefault();
    setZoomValue(zoom + (e.deltaY < 0 ? 0.08 : -0.08));
  };

  const handleExportPdf = async () => {
    if (!selectedGeometry) {
      alert('Select a geometral before generating the PDF.');
      return;
    }
    setPdfExporting(true);
    try {
      const sizes = selectedGeometry.available_sizes || [];
      const rows = MEASUREMENT_KEYS.map(key => {
        const row: string[] = [key];
        sizes.forEach(size => {
          const frontVal = selectedGeometry.size_measurements?.[size]?.front?.[key];
          const backVal = selectedGeometry.size_measurements?.[size]?.back?.[key];
          row.push(frontVal != null ? String(frontVal) : '---');
          row.push(backVal != null ? String(backVal) : '---');
        });
        return row;
      });

      const area: string[] = [];
      sizes.forEach(size => {
        area.push(String(selectedGeometry.surface_areas?.[size]?.front ?? '---'));
        area.push(String(selectedGeometry.surface_areas?.[size]?.back ?? '---'));
      });

      const totals = sizes.map(size =>
        String(selectedGeometry.surface_areas?.[size]?.total ?? '---')
      );

      const compatText = normalizeText(selectedGeometry.compatibility)
        .replace(/^Compatible con:\s*/i, '');

      await exportGeometryPdf({
        title: selectedGeometry.name,
        sheetId: selectedGeometry.id.slice(0, 8),
        compatText,
        selectedModel,
        imageUrl: imageUrl(selectedGeometry.image_url),
        sizes,
        rows,
        area,
        totals,
      });
    } catch (err) {
      console.error('PDF export failed:', err);
      alert('Failed to generate PDF: ' + (err as Error).message);
    } finally {
      setPdfExporting(false);
    }
  };

  const handleModelSelect = (model: string) => {
    setSelectedModel(model);
    if (model) {
      const matches = modelsMap[model];
      if (matches && matches.length > 0) {
        setSelectedGeometryId(matches[0]);
      }
    }
  };

  const handleDocUpload = async (file: File) => {
    if (!selectedVestModel) return;
    setDocUploading(true);
    try {
      await uploadDocMutation.mutateAsync({ modelId: selectedVestModel.id, file });
    } catch (err) {
      console.error('Failed to upload document:', err);
      alert('Failed to upload document. Please try again.');
    } finally {
      setDocUploading(false);
    }
  };

  const handleDocDelete = async (docId: string) => {
    if (!selectedVestModel) return;
    if (!confirm('Delete this document?')) return;
    try {
      await deleteDocMutation.mutateAsync({ modelId: selectedVestModel.id, docId });
    } catch (err) {
      console.error('Failed to delete document:', err);
      alert('Failed to delete document. Please try again.');
    }
  };

  const resetFilters = () => {
    if (geometries && geometries.length > 0) {
      setSelectedGeometryId(geometries[0].id);
    }
    setSelectedModel('');
  };

  if (isLoading) return <div className="p-6">Loading geometries...</div>;
  if (error) return <div className="p-6 text-red-600">Error loading geometries.</div>;

  return (
    <>
      <div className="flex items-center gap-4 mb-6">
        <div className="bg-white shadow rounded-lg px-4 py-3">
          <div className="text-xs font-medium text-gray-500">Geometrales</div>
          <div className="mt-0.5 text-lg font-semibold text-gray-900">{geometries?.length ?? 0}</div>
        </div>
        <div className="bg-white shadow rounded-lg px-4 py-3">
          <div className="text-xs font-medium text-gray-500">Modelos compatibles</div>
          <div className="mt-0.5 text-lg font-semibold text-gray-900">{allModels.length}</div>
        </div>
        <button
          onClick={handleExportPdf}
          disabled={pdfExporting || !selectedGeometry}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pdfExporting ? 'Generating PDF...' : 'Generate A4 PDF'}
        </button>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block mb-1 text-sm font-medium text-gray-700">Geometral</label>
            <select
              value={selectedGeometryId}
              onChange={e => {
                setSelectedGeometryId(e.target.value);
                setSelectedModel('');
              }}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            >
              <option value="">Select a geometral...</option>
              {geometries?.map(g => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block mb-1 text-sm font-medium text-gray-700">Modelo compatible</label>
            <select
              value={selectedModel}
              onChange={e => handleModelSelect(e.target.value)}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            >
              <option value="">Todos los modelos</option>
              {allModels.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
          <button
            onClick={resetFilters}
            className="self-end px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-700 hover:bg-gray-50"
          >
            Reset Filters
          </button>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-sm text-gray-500">Documentation</div>
            <h3 className="text-lg font-medium text-gray-900">Model Document Library</h3>
          </div>
          <div className="text-sm font-medium text-indigo-600">
            {selectedVestModel?.documents?.length ?? 0} documents
          </div>
        </div>
        {!selectedModel ? (
          <div className="text-sm text-gray-500 p-4 border border-dashed border-gray-300 rounded-md">
            Select a model to view its documentation.
          </div>
        ) : (selectedVestModel?.documents?.length ?? 0) === 0 ? (
          <div className="text-sm text-gray-500 p-4 border border-dashed border-gray-300 rounded-md">
            No documents loaded for {selectedModel}.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {selectedVestModel?.documents?.map(doc => (
              <div key={doc.id} className="flex items-center gap-3 p-3 border border-gray-200 rounded-md hover:bg-gray-50">
                <span className="text-lg">PDF</span>
                <a
                  href={`${API_BASE_URL}/api/v1/vest-models/${selectedVestModel.id}/documents/${doc.id}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 min-w-0 text-sm font-medium text-gray-900 hover:text-indigo-600 truncate"
                >
                  {doc.name || doc.original_name}
                </a>
                {isAdmin && (
                  <button
                    onClick={() => handleDocDelete(doc.id)}
                    className="text-red-600 hover:text-red-900 text-sm"
                  >
                    Delete
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {isAdmin && selectedVestModel && (
          <div className="mt-4">
            <label className="inline-flex items-center px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 cursor-pointer disabled:opacity-50">
              {docUploading ? 'Uploading...' : 'Upload Document'}
              <input
                type="file"
                accept=".pdf"
                onChange={e => {
                  const file = e.target.files?.[0];
                  if (file) handleDocUpload(file);
                  e.target.value = '';
                }}
                disabled={docUploading}
                className="hidden"
              />
            </label>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div>
              <div className="text-sm text-gray-500">Representation</div>
              <h2 className="text-lg font-medium text-gray-900">
                {selectedGeometry?.name || 'Select a geometral'}
              </h2>
            </div>
          </div>
          <div className="p-6 space-y-4">
            {selectedGeometry && (
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-md text-sm text-gray-900">
                <strong className="text-indigo-600">Compatibility</strong>
                <br />
                {normalizeText(selectedGeometry.compatibility).replace(/^Compatible con:\s*/i, '') || '---'}
              </div>
            )}

            {selectedModel && (
              <div className="p-3 border border-gray-200 rounded-md">
                <h3 className="text-sm font-medium text-gray-900 mb-1">Composition</h3>
                <div className="text-sm text-gray-700">
                  {selectedVestModel?.composition || 'No composition specified for this model.'}
                </div>
              </div>
            )}

            <div
              ref={imageBoxRef}
              onWheel={handleWheel}
              className="relative min-h-[420px] grid place-items-center overflow-hidden border border-gray-200 rounded-md"
              style={{
                background: selectedGeometry?.image_url
                  ? undefined
                  : 'repeating-conic-gradient(#edf2f7 0% 25%, transparent 0% 50%) 50% / 28px 28px',
              }}
            >
              {selectedGeometry?.image_url ? (
                <>
                  <img
                    src={imageUrl(selectedGeometry.image_url)}
                    alt={selectedGeometry.name}
                    draggable={false}
                    className="max-w-[92%] max-h-[400px] object-contain transition-transform"
                    style={{ transform: `scale(${zoom})` }}
                  />
                  <div className="absolute right-3 bottom-3 flex gap-1.5 p-1.5 bg-gray-900/80 rounded-md backdrop-blur">
                    <button
                      onClick={() => setZoomValue(zoom - 0.1)}
                      className="w-8 h-8 text-white rounded hover:bg-white/10 font-bold"
                    >
                      -
                    </button>
                    <div className="w-12 grid place-items-center text-xs font-bold text-gray-200">
                      {Math.round(zoom * 100)}%
                    </div>
                    <button
                      onClick={() => setZoomValue(zoom + 0.1)}
                      className="w-8 h-8 text-white rounded hover:bg-white/10 font-bold"
                    >
                      +
                    </button>
                    <button
                      onClick={() => setZoomValue(1)}
                      className="w-8 h-8 text-white rounded hover:bg-white/10 font-bold text-xs"
                    >
                      1:1
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-gray-500 text-sm">
                  {selectedGeometry ? 'No image available for this geometral.' : 'Select a geometral to view.'}
                </div>
              )}
            </div>
            <div className="text-xs text-gray-500 text-right">Use + / - or scroll to zoom.</div>
          </div>
        </div>

        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div>
              <div className="text-sm text-gray-500">Dimensional specification</div>
              <h2 className="text-lg font-medium text-gray-900">Measurements Table</h2>
            </div>
            <div className="text-sm text-gray-500">Frente / Espalda</div>
          </div>
          <div className="max-h-[600px] overflow-auto">
            {selectedGeometry && selectedGeometry.available_sizes?.length > 0 ? (
              <table className="w-full border-collapse text-xs text-center">
                <thead>
                  <tr>
                    <th rowSpan={2} className="border border-gray-300 px-2 py-2 bg-gray-900 text-white text-xs font-bold uppercase sticky top-0 left-0 z-10">
                      Cota
                    </th>
                    {selectedGeometry.available_sizes.map(size => (
                      <th key={size} colSpan={2} className="border border-gray-300 px-2 py-1 bg-gray-900 text-white text-sm font-bold">
                        {size}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    {selectedGeometry.available_sizes.flatMap(size => [
                      <th key={`${size}-front`} className="border border-gray-300 px-2 py-1 bg-gray-800 text-white text-xs font-medium uppercase w-24">
                        Front
                      </th>,
                      <th key={`${size}-back`} className="border border-gray-300 px-2 py-1 bg-gray-800 text-white text-xs font-medium uppercase w-24">
                        Back
                      </th>,
                    ])}
                  </tr>
                </thead>
                <tbody>
                  {MEASUREMENT_KEYS.map((key, idx) => {
                    const hasData = selectedGeometry.available_sizes?.some(
                      size => selectedGeometry.size_measurements?.[size]?.front?.[key] != null ||
                                      selectedGeometry.size_measurements?.[size]?.back?.[key] != null
                    );
                    if (!hasData) return null;
                    return (
                      <tr key={key} className={idx % 2 ? 'bg-gray-50' : 'bg-white'}>
                        <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">
                          {key}
                        </td>
                        {selectedGeometry.available_sizes?.flatMap(size => [
                          <td key={`${size}-${key}-front`} className="border border-gray-300 px-2 py-1 text-gray-700">
                            {selectedGeometry.size_measurements?.[size]?.front?.[key] ?? '---'}
                          </td>,
                          <td key={`${size}-${key}-back`} className="border border-gray-300 px-2 py-1 text-gray-700">
                            {selectedGeometry.size_measurements?.[size]?.back?.[key] ?? '---'}
                          </td>,
                        ])}
                      </tr>
                    );
                  })}
                  <tr className="bg-indigo-50">
                    <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">
                      Area (m2)
                    </td>
                    {selectedGeometry.available_sizes?.flatMap(size => [
                      <td key={`${size}-area-front`} className="border border-gray-300 px-2 py-1 text-gray-700">
                        {selectedGeometry.surface_areas?.[size]?.front ?? '---'}
                      </td>,
                      <td key={`${size}-area-back`} className="border border-gray-300 px-2 py-1 text-gray-700">
                        {selectedGeometry.surface_areas?.[size]?.back ?? '---'}
                      </td>,
                    ])}
                  </tr>
                  <tr className="bg-indigo-100">
                    <td className="border border-gray-300 px-2 py-1 font-bold text-gray-900 sticky left-0 bg-inherit">
                      Total area
                    </td>
                    {selectedGeometry.available_sizes?.map(size => (
                      <td key={`${size}-total`} colSpan={2} className="border border-gray-300 px-2 py-1 font-bold text-gray-900">
                        {selectedGeometry.surface_areas?.[size]?.total ?? '---'}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            ) : (
              <div className="p-6 text-center text-sm text-gray-500">
                {selectedGeometry ? 'No measurement data for this geometral.' : 'Select a geometral to view measurements.'}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
