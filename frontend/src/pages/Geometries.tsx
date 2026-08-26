import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { GeometryListTab } from './GeometryListTab';
import { GeometryCompatibilityTab } from './GeometryCompatibilityTab';
import { geometriesApi } from '../hooks/useGeometries';

type Tab = 'list' | 'compatibility';

export function Geometries() {
  const [activeTab, setActiveTab] = useState<Tab>('list');
  const [excelUploading, setExcelUploading] = useState<boolean>(false);
  const queryClient = useQueryClient();

  const handleExcelUpload = async (file: File) => {
    setExcelUploading(true);
    try {
      const result = await geometriesApi.uploadExcel(file);
      alert(result.message);
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    } catch (err) {
      console.error('Failed to upload geometries Excel:', err);
      alert('Failed to upload geometries Excel. Please try again.');
    } finally {
      setExcelUploading(false);
    }
  };

  const handleDownloadExcel = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(geometriesApi.downloadExcel(), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) throw new Error('Failed to download master Excel');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'geometries.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download geometries Excel:', err);
      alert('Failed to download geometries Excel. Please try again.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center">
        <h1 className="text-2xl font-bold text-gray-900 flex-shrink-0">Geometries</h1>
        <div className="flex-1 flex justify-center">
          <div className="flex gap-1 border-b border-gray-200">
            <button
              onClick={() => setActiveTab('list')}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
                activeTab === 'list'
                  ? 'bg-indigo-50 text-indigo-700 border-b-2 border-indigo-500'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              Geometries
            </button>
            <button
              onClick={() => setActiveTab('compatibility')}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
                activeTab === 'compatibility'
                  ? 'bg-indigo-50 text-indigo-700 border-b-2 border-indigo-500'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              Compatibility
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={handleDownloadExcel}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
          >
            Download Master Excel
          </button>
          <label className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 cursor-pointer disabled:opacity-50">
            {excelUploading ? 'Uploading...' : 'Upload Master Excel'}
            <input
              type="file"
              accept=".xlsx,.xls"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handleExcelUpload(file);
                e.target.value = '';
              }}
              disabled={excelUploading}
              className="hidden"
            />
          </label>
        </div>
      </div>

      {activeTab === 'list' && <GeometryListTab />}
      {activeTab === 'compatibility' && <GeometryCompatibilityTab />}
    </div>
  );
}
