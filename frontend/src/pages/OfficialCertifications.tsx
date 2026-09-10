import { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTestSessions, useDeleteTestSession, useUploadExcel, useCreateFromExcel, useUpdateTestSession } from '../hooks/useTestSessions';
import { useLocations, useCreateLocation, useDeleteLocation, useUpdateLocation } from '../hooks/useLocations';
import { useProtocols, useCreateProtocol, useDeleteProtocol, useUpdateProtocol } from '../hooks/useProtocols';
import { useVests } from '../hooks/useVests';
import { useGeometries } from '../hooks/useGeometries';
import { useAuth } from '../hooks/useAuth';
import { TestSession, testSessionsApi } from '../api/test_session';
import { apiClient, API_BASE_URL } from '../api/client';
import { useQueryClient } from '@tanstack/react-query';
import { ConfirmModal } from '../components/ConfirmModal';
import { LocationManagementModal } from '../components/LocationManagementModal';
import { ProtocolManagementModal } from '../components/ProtocolManagementModal';

export function OfficialCertifications() {
  const navigate = useNavigate();
  const { data: testSessions, isLoading, error } = useTestSessions({ is_official: true });
  const { data: locations } = useLocations();
  const { data: protocols } = useProtocols();
  const { data: vests } = useVests();
  const { data: geometries } = useGeometries();
  const { isAdmin, role } = useAuth();
  const createLocationMutation = useCreateLocation();
  const deleteLocationMutation = useDeleteLocation();
  const updateLocationMutation = useUpdateLocation();
  const createProtocolMutation = useCreateProtocol();
  const deleteProtocolMutation = useDeleteProtocol();
  const updateProtocolMutation = useUpdateProtocol();
  const deleteMutation = useDeleteTestSession();
  const updateMutation = useUpdateTestSession();
  const uploadExcelMutation = useUploadExcel();
  const createFromExcelMutation = useCreateFromExcel();

  const formatConditioning = (value: string | null | undefined) => {
    if (!value) return '-';
    if (value === 'ballistic_limit') return 'Ballistic Limit';
    // Replace underscores with spaces and capitalize each word
    return value
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  const [deleteTarget, setDeleteTarget] = useState<TestSession | null>(null);
  const [uploadTarget, setUploadTarget] = useState<TestSession | null>(null);
  const [editTarget, setEditTarget] = useState<TestSession | null>(null);
  const [showCreateFromExcel, setShowCreateFromExcel] = useState(false);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [testName, setTestName] = useState('');
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [protocol, setProtocol] = useState('');
  const [selectedVestId, setSelectedVestId] = useState('');
  const [selectedGeometryId, setSelectedGeometryId] = useState('');
  const defaultGeometryId = useMemo(() => geometries?.find((g) => g.name === 'F')?.id || '', [geometries]);
  useEffect(() => {
    if (defaultGeometryId && !selectedGeometryId) {
      setSelectedGeometryId(defaultGeometryId);
    }
  }, [defaultGeometryId]);
  const [testDate, setTestDate] = useState(new Date().toISOString().split('T')[0]);
  const [certificationNumber, setCertificationNumber] = useState('');
  const [isOfficial, setIsOfficial] = useState(true);
  const [showAdminModal, setShowAdminModal] = useState(false);
  const [adminModalType, setAdminModalType] = useState<'locations' | 'protocols' | 'bulk-reupload'>('locations');
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleteTargetType, setDeleteTargetType] = useState<'location' | 'protocol'>('location');
  const [editTargetId, setEditTargetId] = useState<string | null>(null);
  const [editTargetType, setEditTargetType] = useState<'location' | 'protocol'>('location');
  const [newLocationName, setNewLocationName] = useState('');
  const [newLocationAddress, setNewLocationAddress] = useState('');
  const [newProtocolName, setNewProtocolName] = useState('');
  const [newProtocolDescription, setNewProtocolDescription] = useState('');
  const [showAmmoModal, setShowAmmoModal] = useState(false);
  const [missingCalibers, setMissingCalibers] = useState<string[]>([]);
  const [showDateFormatModal, setShowDateFormatModal] = useState(false);
  const [dateInfo, setDateInfo] = useState<any>(null);
  const [showBulkUpload, setShowBulkUpload] = useState(false);
  const [bulkFiles, setBulkFiles] = useState<File[]>([]);
  const [selectedBulkGeometryId, setSelectedBulkGeometryId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProtectionLevels, setSelectedProtectionLevels] = useState<string[]>([]);
  const [selectedSession, setSelectedSession] = useState<TestSession | null>(null);
  const queryClient = useQueryClient();
  const pdfInputRef = useRef<HTMLInputElement>(null);

  // Fetch child stats when a session is selected
  const { data: childStats } = useQuery({
    queryKey: ['childStats', selectedSession?.id],
    queryFn: () => testSessionsApi.getChildStats(selectedSession!.id),
    enabled: !!selectedSession,
  });

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedSession(null);
        setDeleteTarget(null);
        setUploadTarget(null);
        setEditTarget(null);
        setShowCreateFromExcel(false);
        setShowAdminModal(false);
        setShowAmmoModal(false);
        setShowDateFormatModal(false);
        setShowBulkUpload(false);
        setDeleteTargetId(null);
        setEditTargetId(null);
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, []);

  const refreshSession = async (sessionId: string) => {
    const updated = await testSessionsApi.get(sessionId);
    setSelectedSession(updated);
    queryClient.invalidateQueries({ queryKey: ['test-sessions'] });
  };

  const handleUploadPdf = async (file: File) => {
    if (!selectedSession) return;
    try {
      await testSessionsApi.uploadPdf(selectedSession.id, file);
      await refreshSession(selectedSession.id);
    } catch (err: any) {
      alert(`Failed to upload PDF: ${err.message || err.detail}`);
    }
  };

  const handleDeletePdf = async (index: number) => {
    if (!selectedSession) return;
    try {
      await testSessionsApi.deletePdf(selectedSession.id, index);
      await refreshSession(selectedSession.id);
    } catch (err: any) {
      alert(`Failed to delete PDF: ${err.message || err.detail}`);
    }
  };

  const handlePdfDownload = async (sessionId: string, index: number, filename?: string) => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(testSessionsApi.downloadPdf(sessionId, index), {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!response.ok) throw new Error('Failed to download PDF');
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || 'document.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to download PDF:', err);
      alert('Failed to download PDF. Please try again.');
    }
  };
  useEffect(() => {
    if (defaultGeometryId && !selectedBulkGeometryId && showBulkUpload) {
      setSelectedBulkGeometryId(defaultGeometryId);
    }
  }, [defaultGeometryId, selectedBulkGeometryId, showBulkUpload]);

  const groupedTests = testSessions?.reduce((acc, session) => {
    if (session.parent_test_group_id) {
      if (!acc[session.parent_test_group_id]) {
        acc[session.parent_test_group_id] = [];
      }
      acc[session.parent_test_group_id].push(session);
    }
    return acc;
  }, {} as Record<string, TestSession[]>) || {};

  const parentSessions = testSessions?.filter(s => !s.parent_test_group_id) || [];

  const normalizeProtectionLevel = (level: string): string => {
    const match = level.match(/RB(\d+)/i);
    return match ? `RB${match[1]}`.toUpperCase() : level;
  };

  // Collect all unique protection levels from parent sessions and their children
  const allProtectionLevels = useMemo(() => {
    const levels = new Set<string>();
    parentSessions.forEach(parent => {
      const children = groupedTests[parent.id] || [];
      children.forEach(child => {
        child.protection_levels?.forEach(pl => levels.add(pl));
      });
    });
    return Array.from(levels);
  }, [parentSessions, groupedTests]);

  // Group protection levels by RBX pattern (like analytics)
  const { groups: protectionGroups, nonGrouped: nonGroupedProtectionLevels } = useMemo(() => {
    const groups = new Map<string, string[]>();
    const nonGrouped: string[] = [];
    allProtectionLevels.forEach(level => {
      const match = level.match(/RB(\d+)/i);
      if (match) {
        const rbLevel = `RB${match[1]}`.toUpperCase();
        if (!groups.has(rbLevel)) groups.set(rbLevel, []);
        groups.get(rbLevel)!.push(level);
      } else {
        nonGrouped.push(level);
      }
    });
    return { groups, nonGrouped };
  }, [allProtectionLevels]);

  // Expand selected group levels (e.g. "RB3") to all matching protection levels
  const getExpandedProtectionLevels = (selected: string[]) => {
    const expanded: string[] = [];
    selected.forEach(level => {
      if (level.startsWith('RB') && level.length === 3 && level.match(/RB\d+/)) {
        const groupMembers = protectionGroups.get(level);
        if (groupMembers) expanded.push(...groupMembers);
      } else {
        expanded.push(level);
      }
    });
    return expanded;
  };

  const filteredParentSessions = (() => {
    const expandedLevels = getExpandedProtectionLevels(selectedProtectionLevels);
    return parentSessions.filter(parent => {
      const children = groupedTests[parent.id] || [];

      // Filter by protection level
      if (selectedProtectionLevels.length > 0) {
        const allLevels = new Set<string>();
        children.forEach(child => {
          child.protection_levels?.forEach(pl => allLevels.add(pl));
        });
        const hasMatch = expandedLevels.some(lvl => allLevels.has(lvl));
        if (!hasMatch) return false;
      }

      // Filter by search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const parentMatch =
          parent.name?.toLowerCase().includes(q) ||
          parent.lab_name?.toLowerCase().includes(q) ||
          parent.protocol?.toLowerCase().includes(q) ||
          parent.vest_name?.toLowerCase().includes(q) ||
          parent.vest_code?.toLowerCase().includes(q) ||
          parent.geometry_name?.toLowerCase().includes(q) ||
          parent.certification_number?.toLowerCase().includes(q);
        const childMatch = children.some(child =>
          child.name?.toLowerCase().includes(q) ||
          child.vest_name?.toLowerCase().includes(q) ||
          child.vest_code?.toLowerCase().includes(q) ||
          child.geometry_name?.toLowerCase().includes(q) ||
          (child.protection_levels || []).some(pl => pl?.toLowerCase().includes(q))
        );
        // Also search by protection level group name (e.g. "RB3")
        const protectionLevelMatch = children.some(child =>
          (child.protection_levels || []).some(pl => {
            if (!pl) return false;
            const match = pl.match(/RB(\d+)/i);
            if (match) {
              const rbLevel = `RB${match[1]}`.toLowerCase();
              return rbLevel.includes(q);
            }
            return pl.toLowerCase().includes(q);
          })
        );
        if (!parentMatch && !childMatch && !protectionLevelMatch) return false;
      }

      return true;
    });
  })();

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading test sessions</div>;

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
    } catch (err) {
      console.error('Failed to delete test session:', err);
    } finally {
      setDeleteTarget(null);
    }
  };

  
  const handleExcelUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadTarget || !excelFile) return;
    try {
      await uploadExcelMutation.mutateAsync({ id: uploadTarget.id, file: excelFile });
      setUploadTarget(null);
      setExcelFile(null);
    } catch (err: any) {
      console.error('Failed to upload Excel:', err);
      // Check if error is due to missing ammunition
      if (err?.message?.includes('missing_ammunition') || err?.detail?.error === 'missing_ammunition') {
        const missingCalibers = err.detail?.missing_calibers || [];
        setMissingCalibers(missingCalibers);
        setShowAmmoModal(true);
      }
    }
  };

  const handleFileSelection = async (file: File) => {
    setExcelFile(file);
    if (!file) return;

    // Auto-fill test name from filename if not set
    if (!testName) {
      const fileName = file.name.replace(/\.[^/.]+$/, '').replace(/_/g, '/');
      setTestName(fileName);
    }

    // Extract date from file using the API
    try {
      const formData = new FormData();
      formData.append('excel_file', file);
      formData.append('test_name', testName || file.name.replace(/\.[^/.]+$/, ''));

      const response = await fetch(`${API_BASE_URL}/api/v1/test-sessions/extract-date`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      if (response.ok) {
        const dateInfo = await response.json();
        if (dateInfo.date) {
          if (dateInfo.ambiguous) {
            setDateInfo(dateInfo);
            setShowDateFormatModal(true);
          } else {
            // Date input expects YYYY-MM-DD format (ISO format)
            setTestDate(dateInfo.date);
          }
        }
      }
    } catch (err) {
      console.error('Failed to extract date from file:', err);
    }
  };

  const handleCreateFromExcel = async (e: React.FormEvent, dateFormat?: string) => {
    e.preventDefault();
    if (!excelFile || !testName || !selectedVestId) {
      alert('Please select a vest');
      return;
    }
    if (!selectedGeometryId) {
      alert('Please select a geometry');
      return;
    }
    try {
      await createFromExcelMutation.mutateAsync({
        file: excelFile,
        testName,
        locationId: selectedLocationId || undefined,
        protocol: protocol || undefined,
        vestId: selectedVestId,
        geometryId: selectedGeometryId,
        testDate: testDate || undefined,
        dateFormat: dateFormat || undefined,
        isOfficial: isOfficial,
        certificationNumber: certificationNumber || undefined,
      });
      setShowCreateFromExcel(false);
      setExcelFile(null);
      setTestName('');
      setCertificationNumber('');
      setSelectedLocationId('');
      setProtocol('');
      setSelectedVestId('');
      setSelectedGeometryId(defaultGeometryId);
      setTestDate(new Date().toISOString().split('T')[0]);
      setIsOfficial(true);
      setShowDateFormatModal(false);
      setDateInfo(null);
    } catch (err: any) {
      console.error('Failed to create test session from Excel:', err);
      // Check if error is due to missing ammunition
      if (err?.message?.includes('missing_ammunition') || err?.detail?.error === 'missing_ammunition') {
        const missingCalibers = err.detail?.missing_calibers || [];
        setMissingCalibers(missingCalibers);
        setShowAmmoModal(true);
      }
    }
  };

  const handleBulkReupload = async () => {
    try {
      await apiClient.post('/api/v1/test-sessions/admin/bulk-reupload-all', {});

      setShowAdminModal(false);
      window.location.reload();
    } catch (err: any) {
      console.error('Failed to bulk re-upload:', err);
      alert(err?.detail || 'Failed to bulk re-upload. Check console for details.');
    }
  };

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (bulkFiles.length === 0) return;
    if (!selectedBulkGeometryId) {
      alert('Please select a geometry');
      return;
    }

    try {
      const formData = new FormData();
      bulkFiles.forEach(file => {
        formData.append('excel_files', file);
      });
      formData.append('geometry_id', selectedBulkGeometryId);

      await apiClient.post('/api/v1/test-sessions/bulk-upload', formData);
      setShowBulkUpload(false);
      setBulkFiles([]);
      window.location.reload();
    } catch (err: any) {
      console.error('Failed to bulk upload:', err);
      alert(err?.detail || 'Failed to bulk upload. Check console for details.');
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Official Certifications</h1>
        <div className="flex gap-2">
          {isAdmin && (
            <>
              <button
                onClick={() => {
                  setAdminModalType('locations');
                  setShowAdminModal(true);
                }}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                Manage Labs
              </button>
              <button
                onClick={() => {
                  setAdminModalType('protocols');
                  setShowAdminModal(true);
                }}
                className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
              >
                Manage Protocols
              </button>
              <button
                onClick={() => {
                  setAdminModalType('bulk-reupload');
                  setShowAdminModal(true);
                }}
                className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700"
              >
                Bulk Re-upload
              </button>
            </>
          )}
          {role !== 'viewer' && (
            <button
              onClick={() => setShowCreateFromExcel(true)}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              Upload Excel
            </button>
          )}
          {isAdmin && (
            <button
              onClick={() => setShowBulkUpload(true)}
              className="px-4 py-2 bg-teal-600 text-white rounded-md hover:bg-teal-700"
            >
              Bulk Upload
            </button>
          )}
        </div>
      </div>

      <div className="mb-4 space-y-2">
        <input
          type="text"
          placeholder="Search certifications... (e.g. RB3, vest code, name)"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
        />
        {allProtectionLevels.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-700">Protection Level:</span>
            {Array.from(protectionGroups.keys()).sort().map(rbLevel => (
              <button
                key={rbLevel}
                onClick={() => {
                  if (selectedProtectionLevels.includes(rbLevel)) {
                    setSelectedProtectionLevels(selectedProtectionLevels.filter(l => l !== rbLevel));
                  } else {
                    setSelectedProtectionLevels([...selectedProtectionLevels, rbLevel]);
                  }
                }}
                className={`px-2 py-1 text-xs rounded-md border ${
                  selectedProtectionLevels.includes(rbLevel)
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {rbLevel}
              </button>
            ))}
            {nonGroupedProtectionLevels.map(level => (
              <button
                key={level}
                onClick={() => {
                  if (selectedProtectionLevels.includes(level)) {
                    setSelectedProtectionLevels(selectedProtectionLevels.filter(l => l !== level));
                  } else {
                    setSelectedProtectionLevels([...selectedProtectionLevels, level]);
                  }
                }}
                className={`px-2 py-1 text-xs rounded-md border ${
                  selectedProtectionLevels.includes(level)
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {level}
              </button>
            ))}
            {selectedProtectionLevels.length > 0 && (
              <button
                onClick={() => setSelectedProtectionLevels([])}
                className="text-sm text-indigo-600 hover:text-indigo-800"
              >
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-xs truncate">Name</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-24 truncate">Lab</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-32 truncate">Protocol</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Geometry</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Sizes</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Protection</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-32 truncate">N° of shots</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cert. #</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Excel</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredParentSessions.map((parent) => {
              const children = groupedTests[parent.id] || [];
              const totalShotCount = children.reduce((sum, child) => sum + (child.shot_count || 0), 0);
              const childSizes = [...new Set(children.map(c => c.size).filter(Boolean))].join(', ');

              return (
                <tr
                  key={parent.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedSession(parent)}
                >
                  <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900 max-w-xs truncate" title={parent.name}>
                    {parent.name.length > 30 ? parent.name.substring(0, 30) + '...' : parent.name}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{parent.test_date || '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 max-w-24 truncate" title={parent.lab_name || ''}>{parent.lab_name || '-'}</td>
                  <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate" title={parent.protocol || ''}>{parent.protocol || '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500" title={parent.geometry_name || ''}>
                    {parent.geometry_name ? (parent.geometry_name.length > 15 ? parent.geometry_name.substring(0, 15) + '...' : parent.geometry_name) : '-'}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate" title={childSizes || ''}>{childSizes || '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate" title={(() => { const allLevels = new Set<string>(); children.forEach(c => c.protection_levels?.forEach(pl => allLevels.add(normalizeProtectionLevel(pl)))); return Array.from(allLevels).join(', '); })()}>
                    {(() => {
                      const allLevels = new Set<string>();
                      children.forEach(c => c.protection_levels?.forEach(pl => allLevels.add(normalizeProtectionLevel(pl))));
                      const levels = Array.from(allLevels);
                      return levels.length > 0 ? levels.join(', ') : '-';
                    })()}
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate">{children.length > 0 ? totalShotCount : '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{parent.certification_number || '-'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                    {role !== 'viewer' && (
                      parent.excel_file_path ? (
                        <span className="text-green-600">Uploaded</span>
                      ) : (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploadTarget(parent);
                          }}
                          className="text-indigo-600 hover:text-indigo-900"
                        >
                          Upload
                        </button>
                      )
                    )}
                    {role === 'viewer' && (
                      parent.excel_file_path ? (
                        <span className="text-green-600">Uploaded</span>
                      ) : '-'
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-right text-sm font-medium">
                    {role !== 'viewer' && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditTarget(parent);
                          }}
                          className="text-indigo-600 hover:text-indigo-900 mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(parent);
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
              );
            })}
            {testSessions?.length === 0 && (
              <tr>
                <td colSpan={11} className="px-6 py-4 text-center text-sm text-gray-500">
                  No official certifications found. Click "Upload Excel" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </div>

      {deleteTarget && (
        <ConfirmModal
          title="Delete Test Session"
          message={`Are you sure you want to delete "${deleteTarget.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {uploadTarget && (
        <ConfirmModal
          title="Upload Excel File"
          message={
            <div>
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
              />
            </div>
          }
          confirmLabel="Upload"
          variant="default"
          onConfirm={handleExcelUpload}
          onCancel={() => {
            setUploadTarget(null);
            setExcelFile(null);
          }}
        />
      )}

      {showCreateFromExcel && (
        <ConfirmModal
          title="Create Official Certification"
          message={
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Excel File</label>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    if (file) {
                      handleFileSelection(file);
                    }
                  }}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Test Name</label>
                <input
                  type="text"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  placeholder="Enter test name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Certification Number</label>
                <input
                  type="text"
                  value={certificationNumber}
                  onChange={(e) => setCertificationNumber(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  placeholder="Enter certification number"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
                <select
                  value={selectedLocationId}
                  onChange={(e) => setSelectedLocationId(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select location (optional)</option>
                  {locations?.map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
                <select
                  value={protocol}
                  onChange={(e) => setProtocol(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select protocol (optional)</option>
                  {protocols?.map((prot) => (
                    <option key={prot.id} value={prot.name}>
                      {prot.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Vest *</label>
                <select
                  value={selectedVestId}
                  onChange={(e) => setSelectedVestId(e.target.value)}
                  required
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select vest...</option>
                  {vests?.sort((a, b) => a.vest_code.localeCompare(b.vest_code)).map((vest) => (
                    <option key={vest.id} value={vest.id}>
                      {vest.vest_code} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Geometry *</label>
                <select
                  value={selectedGeometryId}
                  onChange={(e) => setSelectedGeometryId(e.target.value)}
                  required
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select geometry...</option>
                  {geometries?.sort((a, b) => a.name.localeCompare(b.name)).map((geometry) => (
                    <option key={geometry.id} value={geometry.id}>
                      {geometry.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Test Date</label>
                <input
                  type="date"
                  value={testDate}
                  onChange={(e) => setTestDate(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
            </div>
          }
          confirmLabel="Create"
          variant="default"
          onConfirm={handleCreateFromExcel}
          onCancel={() => {
            setShowCreateFromExcel(false);
            setExcelFile(null);
            setTestName('');
            setCertificationNumber('');
            setSelectedLocationId('');
            setProtocol('');
            setSelectedVestId('');
            setSelectedGeometryId(defaultGeometryId);
            setTestDate(new Date().toISOString().split('T')[0]);
            setIsOfficial(true);
          }}
        />
      )}

      {showAdminModal && adminModalType === 'locations' && (
        <LocationManagementModal
          isOpen={showAdminModal}
          locations={locations || []}
          newLocationName={newLocationName}
          newLocationAddress={newLocationAddress}
          onNameChange={setNewLocationName}
          onAddressChange={setNewLocationAddress}
          onEdit={(loc) => {
            setEditTargetId(loc.id);
            setEditTargetType('location');
            setNewLocationName(loc.name);
            setNewLocationAddress(loc.address || '');
            setShowAdminModal(false);
          }}
          onDelete={(locationId) => {
            setDeleteTargetId(locationId);
            setDeleteTargetType('location');
            setShowAdminModal(false);
          }}
          onAdd={async () => {
            try {
              if (newLocationName) {
                await createLocationMutation.mutateAsync({
                  name: newLocationName,
                  address: newLocationAddress || undefined,
                });
              }
              setShowAdminModal(false);
              setNewLocationName('');
              setNewLocationAddress('');
            } catch (err) {
              console.error('Failed to create location:', err);
            }
          }}
          onCancel={() => {
            setShowAdminModal(false);
            setNewLocationName('');
            setNewLocationAddress('');
          }}
        />
      )}

      {showAdminModal && adminModalType === 'protocols' && (
        <ProtocolManagementModal
          isOpen={showAdminModal}
          protocols={protocols || []}
          newProtocolName={newProtocolName}
          newProtocolDescription={newProtocolDescription}
          onNameChange={setNewProtocolName}
          onDescriptionChange={setNewProtocolDescription}
          onEdit={(prot) => {
            setEditTargetId(prot.id);
            setEditTargetType('protocol');
            setNewProtocolName(prot.name);
            setNewProtocolDescription(prot.description || '');
            setShowAdminModal(false);
          }}
          onDelete={(protocolId) => {
            setDeleteTargetId(protocolId);
            setDeleteTargetType('protocol');
            setShowAdminModal(false);
          }}
          onAdd={async () => {
            try {
              if (newProtocolName) {
                await createProtocolMutation.mutateAsync({
                  name: newProtocolName,
                  description: newProtocolDescription || undefined,
                });
              }
              setShowAdminModal(false);
              setNewProtocolName('');
              setNewProtocolDescription('');
            } catch (err) {
              console.error('Failed to create protocol:', err);
            }
          }}
          onCancel={() => {
            setShowAdminModal(false);
            setNewProtocolName('');
            setNewProtocolDescription('');
          }}
        />
      )}

      {deleteTargetId && (
        <ConfirmModal
          title={`Delete ${deleteTargetType === 'location' ? 'Lab' : 'Protocol'}`}
          message={`Are you sure you want to delete this ${deleteTargetType}? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={async () => {
            try {
              if (deleteTargetType === 'location') {
                await deleteLocationMutation.mutateAsync(deleteTargetId);
              } else {
                await deleteProtocolMutation.mutateAsync(deleteTargetId);
              }
              setDeleteTargetId(null);
            } catch (err) {
              console.error('Failed to delete:', err);
            }
          }}
          onCancel={() => setDeleteTargetId(null)}
        />
      )}

      {editTargetId && (
        <ConfirmModal
          title={`Edit ${editTargetType === 'location' ? 'Lab' : 'Protocol'}`}
          message={
            <div className="space-y-4">
              {editTargetType === 'location' ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Lab Name</label>
                    <input
                      type="text"
                      value={newLocationName}
                      onChange={(e) => setNewLocationName(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                      placeholder="Lab name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                    <input
                      type="text"
                      value={newLocationAddress}
                      onChange={(e) => setNewLocationAddress(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                      placeholder="Address (optional)"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Protocol Name</label>
                    <input
                      type="text"
                      value={newProtocolName}
                      onChange={(e) => setNewProtocolName(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                      placeholder="Protocol name"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <input
                      type="text"
                      value={newProtocolDescription}
                      onChange={(e) => setNewProtocolDescription(e.target.value)}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                      placeholder="Description (optional)"
                    />
                  </div>
                </>
              )}
            </div>
          }
          confirmLabel="Save"
          variant="default"
          onConfirm={async () => {
            try {
              if (editTargetType === 'location') {
                await updateLocationMutation.mutateAsync({
                  id: editTargetId,
                  location: { name: newLocationName, address: newLocationAddress || undefined },
                });
              } else {
                await updateProtocolMutation.mutateAsync({
                  id: editTargetId,
                  protocol: { name: newProtocolName, description: newProtocolDescription || undefined },
                });
              }
              setEditTargetId(null);
              setNewLocationName('');
              setNewLocationAddress('');
              setNewProtocolName('');
              setNewProtocolDescription('');
            } catch (err) {
              console.error('Failed to update:', err);
            }
          }}
          onCancel={() => {
            setEditTargetId(null);
            setNewLocationName('');
            setNewLocationAddress('');
            setNewProtocolName('');
            setNewProtocolDescription('');
          }}
        />
      )}

      {showAdminModal && adminModalType === 'bulk-reupload' && (
        <ConfirmModal
          title="Bulk Re-upload All Test Sessions"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                This will delete all test sessions with associated Excel files and re-upload them using the corrected parsing logic.
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                <p className="text-sm text-yellow-800">
                  <strong>Warning:</strong> This action will delete and recreate all test sessions that were created from Excel uploads.
                </p>
              </div>
            </div>
          }
          confirmLabel="Re-upload All"
          variant="danger"
          onConfirm={handleBulkReupload}
          onCancel={() => {
            setShowAdminModal(false);
          }}
        />
      )}

      {showAmmoModal && (
        <ConfirmModal
          title="Missing Ammunition"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                The following calibers are not in the ammunition database and cannot be matched:
              </p>
              <ul className="list-disc list-inside text-sm text-gray-700 bg-gray-50 p-3 rounded-md">
                {missingCalibers.map((caliber, index) => (
                  <li key={index} className="font-medium">{caliber}</li>
                ))}
              </ul>
              <p className="text-sm text-gray-600">
                Please create the missing ammunition before uploading the Excel file.
              </p>
            </div>
          }
          confirmLabel="Go to Ammunition"
          variant="default"
          onConfirm={() => {
            setShowAmmoModal(false);
            window.location.href = '/ammunition';
          }}
          onCancel={() => {
            setShowAmmoModal(false);
          }}
        />
      )}

      {showDateFormatModal && dateInfo && (
        <ConfirmModal
          title="Ambiguous Date Format"
          message={
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                The date extracted from the Excel file is ambiguous. Please choose the correct format:
              </p>
              <div className="bg-gray-50 p-3 rounded-md space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">Spanish (DD/MM/YY):</span>
                  <span className="text-sm text-gray-600">{dateInfo.spanish_date}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">English (MM/DD/YY):</span>
                  <span className="text-sm text-gray-600">{dateInfo.english_date}</span>
                </div>
              </div>
            </div>
          }
          confirmLabel="Spanish Format"
          cancelLabel="English Format"
          variant="default"
          onConfirm={(e) => {
            setTestDate(dateInfo.spanish_date);
            setShowDateFormatModal(false);
            setDateInfo(null);
          }}
          onCancel={() => {
            setTestDate(dateInfo.english_date);
            setShowDateFormatModal(false);
            setDateInfo(null);
          }}
        />
      )}

      {editTarget && (
        <ConfirmModal
          title="Edit Test Session"
          maxWidth="max-w-2xl"
          message={
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Excel File</label>
                {editTarget.excel_file_path && (
                  <div className="mb-2 text-sm text-gray-600">
                    Current file: <span className="font-medium">{editTarget.excel_file_path}</span>
                  </div>
                )}
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={(e) => setEditTarget({ ...editTarget, excel_file: e.target.files?.[0] || null })}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Session Name</label>
                <input
                  type="text"
                  value={editTarget.name}
                  onChange={(e) => setEditTarget({ ...editTarget, name: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              {!editTarget.parent_test_group_id && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Test Date</label>
                    <input
                      type="date"
                      value={editTarget.test_date || ''}
                      onChange={(e) => setEditTarget({ ...editTarget, test_date: e.target.value || null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Lab Name</label>
                    <select
                      value={editTarget.lab_name || ''}
                      onChange={(e) => setEditTarget({ ...editTarget, lab_name: e.target.value || null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                    >
                      <option value="">Select lab...</option>
                      {locations?.map((location) => (
                        <option key={location.id} value={location.name}>
                          {location.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}
              {!editTarget.parent_test_group_id && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
                  <select
                    value={editTarget.protocol || ''}
                    onChange={(e) => setEditTarget({ ...editTarget, protocol: e.target.value || null })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select protocol...</option>
                    {protocols?.map((protocol) => (
                      <option key={protocol.id} value={protocol.name}>
                        {protocol.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Vest</label>
                  <select
                    value={editTarget.vest_id || ''}
                    onChange={(e) => setEditTarget({ ...editTarget, vest_id: e.target.value || null })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select vest...</option>
                    {vests?.map((vest) => (
                      <option key={vest.id} value={vest.id}>
                        {vest.vest_code} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Geometry</label>
                  <select
                    value={editTarget.geometry_id || ''}
                    onChange={(e) => setEditTarget({ ...editTarget, geometry_id: e.target.value || null })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select geometry (optional)</option>
                    {geometries?.sort((a, b) => a.name.localeCompare(b.name)).map((geometry) => (
                      <option key={geometry.id} value={geometry.id}>
                        {geometry.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              {editTarget.parent_test_group_id && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Conditioning</label>
                  <select
                    value={editTarget.conditioning || ''}
                    onChange={(e) => setEditTarget({ ...editTarget, conditioning: e.target.value || null })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select conditioning...</option>
                    <option value="ambient">Ambient</option>
                    <option value="wet">Wet</option>
                    <option value="tumbled">Tumbled</option>
                    <option value="ballistic_limit">Ballistic Limit</option>
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Certification Number</label>
                <input
                  type="text"
                  value={editTarget.certification_number || ''}
                  onChange={(e) => setEditTarget({ ...editTarget, certification_number: e.target.value || null })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              {editTarget.parent_test_group_id && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Ambient Temperature (°C)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={editTarget.ambient_temperature_c ?? ''}
                      onChange={(e) => setEditTarget({ ...editTarget, ambient_temperature_c: e.target.value ? parseFloat(e.target.value) : null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Humidity (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={editTarget.humidity_percent ?? ''}
                      onChange={(e) => setEditTarget({ ...editTarget, humidity_percent: e.target.value ? parseFloat(e.target.value) : null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                    />
                  </div>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
                <textarea
                  rows={3}
                  value={editTarget.notes || ''}
                  onChange={(e) => setEditTarget({ ...editTarget, notes: e.target.value || null })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
            </div>
          }
          confirmLabel="Save"
          variant="default"
          onConfirm={async () => {
            try {
              await updateMutation.mutateAsync({
                id: editTarget.id,
                testSession: {
                  name: editTarget.name,
                  test_date: editTarget.test_date,
                  lab_name: editTarget.lab_name,
                  protocol: editTarget.protocol,
                  vest_id: editTarget.vest_id,
                  geometry_id: editTarget.geometry_id,
                  conditioning: editTarget.conditioning,
                  ambient_temperature_c: editTarget.ambient_temperature_c,
                  humidity_percent: editTarget.humidity_percent,
                  notes: editTarget.notes,
                  certification_number: editTarget.certification_number,
                },
                cascade: !editTarget.parent_test_group_id,
              });
              setEditTarget(null);
            } catch (err) {
              console.error('Failed to update test session:', err);
            }
          }}
          onCancel={() => setEditTarget(null)}
        />
      )}

      {showBulkUpload && (
        <ConfirmModal
          title="Bulk Upload Excel Files"
          message={
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Geometry *</label>
                <select
                  value={selectedBulkGeometryId}
                  onChange={(e) => setSelectedBulkGeometryId(e.target.value)}
                  required
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select geometry...</option>
                  {geometries?.sort((a, b) => a.name.localeCompare(b.name)).map((geometry) => (
                    <option key={geometry.id} value={geometry.id}>
                      {geometry.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Select Excel Files</label>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  multiple
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    setBulkFiles(files);
                  }}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </div>
              {bulkFiles.length > 0 && (
                <div className="bg-gray-50 p-3 rounded-md">
                  <p className="text-sm text-gray-700 font-medium mb-2">Selected Files ({bulkFiles.length}):</p>
                  <ul className="text-sm text-gray-600 space-y-1 max-h-40 overflow-y-auto">
                    {bulkFiles.map((file, index) => (
                      <li key={index}>{file.name}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          }
          confirmLabel="Upload All"
          cancelLabel="Cancel"
          variant="default"
          onConfirm={handleBulkUpload}
          onCancel={() => {
            setShowBulkUpload(false);
            setBulkFiles([]);
            setSelectedBulkGeometryId('');
          }}
        />
      )}

      {selectedSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={() => setSelectedSession(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-7xl mx-4 p-6 max-h-[92vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{selectedSession.name}</h3>
                <p className="text-sm text-gray-500">
                  {selectedSession.certification_number && `Cert. #${selectedSession.certification_number} - `}
                  {selectedSession.test_date || 'No date'}
                </p>
              </div>
              <button onClick={() => setSelectedSession(null)} className="text-gray-400 hover:text-gray-600 text-xl">x</button>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              <div><span className="text-gray-500">Lab:</span> <span className="ml-2 font-medium">{selectedSession.lab_name || '-'}</span></div>
              <div><span className="text-gray-500">Protocol:</span> <span className="ml-2 font-medium">{selectedSession.protocol || '-'}</span></div>
              <div><span className="text-gray-500">Geometry:</span> <span className="ml-2 font-medium">{selectedSession.geometry_name || '-'}</span></div>
              <div><span className="text-gray-500">Shots:</span> <span className="ml-2 font-medium">{(() => { const children = groupedTests[selectedSession.id] || []; const total = children.reduce((sum, child) => sum + (child.shot_count || 0), 0); return children.length > 0 ? total : (selectedSession.shot_count ?? '-'); })()}</span></div>
              <div><span className="text-gray-500">Conditioning:</span> <span className="ml-2 font-medium">{formatConditioning(selectedSession.conditioning)}</span></div>
              <div><span className="text-gray-500">Sizes:</span> <span className="ml-2 font-medium">{(() => { const children = groupedTests[selectedSession.id] || []; const sizes = [...new Set(children.map(c => c.size).filter(Boolean))]; return sizes.length > 0 ? sizes.join(', ') : (selectedSession.size || '-'); })()}</span></div>
              <div><span className="text-gray-500">Ambient Temp:</span> <span className="ml-2 font-medium">{selectedSession.ambient_temperature_c ? `${selectedSession.ambient_temperature_c} C` : '-'}</span></div>
              <div><span className="text-gray-500">Humidity:</span> <span className="ml-2 font-medium">{selectedSession.humidity_percent ? `${selectedSession.humidity_percent}%` : '-'}</span></div>
              <div><span className="text-gray-500">Ballistic Limit:</span> <span className="ml-2 font-medium">{selectedSession.ballistic_limit ? 'Yes' : 'No'}</span></div>
              <div><span className="text-gray-500">Protection:</span> <span className="ml-2 font-medium">{(() => { const children = groupedTests[selectedSession.id] || []; const allLevels = new Set<string>(); children.forEach(c => c.protection_levels?.forEach(pl => allLevels.add(normalizeProtectionLevel(pl)))); const levels = Array.from(allLevels); return levels.length > 0 ? levels.join(', ') : '-'; })()}</span></div>
              <div><span className="text-gray-500">Excel:</span> <span className="ml-2 font-medium">{selectedSession.excel_file_path ? 'Uploaded' : '-'}</span></div>
            </div>

            {selectedSession.notes && (
              <div className="mt-4 pt-4 border-t">
                <span className="text-gray-500 text-sm">Notes:</span>
                <p className="mt-1 text-sm text-gray-700">{selectedSession.notes}</p>
              </div>
            )}

            {/* PDF documents (multiple) */}
            <div className="mt-4 pt-4 border-t">
              <span className="text-gray-500 text-sm">PDF Documents:</span>
              {selectedSession.pdf_documents && selectedSession.pdf_documents.length > 0 ? (
                <div className="mt-1 space-y-1">
                  {selectedSession.pdf_documents.map((doc, index) => (
                    <div key={index} className="flex items-center gap-3">
                      <button
                        onClick={() => handlePdfDownload(selectedSession.id, index, doc.original_name)}
                        className="text-sm text-indigo-600 hover:text-indigo-900"
                      >
                        {doc.original_name}
                      </button>
                      {role !== 'viewer' && (
                        <button
                          onClick={() => handleDeletePdf(index)}
                          className="text-sm text-red-600 hover:text-red-900"
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              ) : null}
              {role !== 'viewer' && (
                <div className="mt-2">
                  <input
                    ref={pdfInputRef}
                    type="file"
                    accept=".pdf"
                    multiple
                    className="hidden"
                    onChange={e => {
                      if (e.target.files) {
                        Array.from(e.target.files).forEach(f => handleUploadPdf(f));
                      }
                      e.target.value = '';
                    }}
                  />
                  <button
                    onClick={() => pdfInputRef.current?.click()}
                    className="text-sm text-indigo-600 hover:text-indigo-900"
                  >
                    Upload PDF{selectedSession.pdf_documents && selectedSession.pdf_documents.length > 0 ? ' (more)' : ''}
                  </button>
                </div>
              )}
              {(!selectedSession.pdf_documents || selectedSession.pdf_documents.length === 0) && role === 'viewer' && (
                <span className="ml-2 text-sm text-gray-400">-</span>
              )}
            </div>

            {/* Child sessions (at the bottom) */}
            {(() => {
              const children = groupedTests[selectedSession.id] || [];
              if (children.length === 0) return null;
              const sortedChildren = [...children].sort((a, b) => {
                const extractTestNumber = (name: string, parentName: string) => {
                  const suffix = name.replace(parentName + ' - ', '');
                  const match = suffix.match(/^(\d+)/);
                  return match ? parseInt(match[1], 10) : 0;
                };
                const numA = extractTestNumber(a.name, selectedSession.name);
                const numB = extractTestNumber(b.name, selectedSession.name);
                return numA - numB;
              });
              return (
                <div className="mt-4 pt-4 border-t">
                  <span className="text-gray-500 text-sm">Child Sessions:</span>
                  <div className="mt-2 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Vest</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Size</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Ambient</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Humidity</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Cond.</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Shots</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Highest Trauma</th>
                          <th className="px-3 py-1 text-left text-xs font-medium text-gray-500 uppercase">Avg First 3</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {sortedChildren.map(child => {
                          const childName = child.name.replace(selectedSession.name + ' - ', '');
                          return (
                            <tr
                              key={child.id}
                              className="hover:bg-indigo-50 cursor-pointer"
                              onClick={() => navigate(`/test-sessions/${child.id}`)}
                            >
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-900 max-w-xs truncate" title={childName}>{childName}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500" title={child.vest_code || ''}>{child.vest_code || '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{child.size || '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{child.ambient_temperature_c ? `${child.ambient_temperature_c} C` : '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{child.humidity_percent ? `${child.humidity_percent}%` : '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{formatConditioning(child.conditioning)}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{child.shot_count ?? '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{childStats?.[child.id]?.highest_trauma != null ? `${childStats[child.id].highest_trauma} mm` : '-'}</td>
                              <td className="px-3 py-1.5 whitespace-nowrap text-sm text-gray-500">{childStats?.[child.id]?.avg_first_three != null ? `${childStats[child.id].avg_first_three} mm` : '-'}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}

            <div className="mt-4 pt-4 border-t flex justify-end gap-3">
              {selectedSession.pdf_documents && selectedSession.pdf_documents.length > 0 && (
                <button
                  onClick={() => handlePdfDownload(selectedSession.id, 0, selectedSession.pdf_documents?.[0]?.original_name)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm"
                >
                  Download First PDF
                </button>
              )}
              {role !== 'viewer' && (
                <>
                  <button onClick={() => { setEditTarget(selectedSession); setSelectedSession(null); }} className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 text-sm">Edit</button>
                  <button onClick={() => { setDeleteTarget(selectedSession); setSelectedSession(null); }} className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm">Delete</button>
                </>
              )}
              <button onClick={() => setSelectedSession(null)} className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 text-sm">Close</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
