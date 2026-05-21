import { useState, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTestSessions, useDeleteTestSession, useUploadExcel, useCreateFromExcel, useUpdateTestSession } from '../hooks/useTestSessions';
import { useLocations, useCreateLocation, useDeleteLocation, useUpdateLocation } from '../hooks/useLocations';
import { useProtocols, useCreateProtocol, useDeleteProtocol, useUpdateProtocol } from '../hooks/useProtocols';
import { useVests } from '../hooks/useVests';
import { useAuth } from '../hooks/useAuth';
import { TestSession } from '../api/test_session';
import { apiClient } from '../api/client';
import { ConfirmModal } from '../components/ConfirmModal';
import { LocationManagementModal } from '../components/LocationManagementModal';
import { ProtocolManagementModal } from '../components/ProtocolManagementModal';

export function TestSessions() {
  const navigate = useNavigate();
  const { data: testSessions, isLoading, error } = useTestSessions();
  const { data: locations } = useLocations();
  const { data: protocols } = useProtocols();
  const { data: vests } = useVests();
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
  const [testDate, setTestDate] = useState(new Date().toISOString().split('T')[0]);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
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

  // Group test sessions by parent_test_group_id
  const groupedTests = testSessions?.reduce((acc, session) => {
    if (session.parent_test_group_id) {
      if (!acc[session.parent_test_group_id]) {
        acc[session.parent_test_group_id] = [];
      }
      acc[session.parent_test_group_id].push(session);
    } else {
      // This is a parent session or has no parent
      if (!acc[session.id]) {
        acc[session.id] = [];
      }
    }
    return acc;
  }, {} as Record<string, TestSession[]>) || {};

  const parentSessions = testSessions?.filter(s => !s.parent_test_group_id) || [];

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
      const fileName = file.name.replace(/\.[^/.]+$/, '');
      setTestName(fileName);
    }

    // Extract date from file using the API
    try {
      const formData = new FormData();
      formData.append('excel_file', file);
      formData.append('test_name', testName || file.name.replace(/\.[^/.]+$/, ''));

      const response = await fetch('/api/v1/test-sessions/extract-date', {
        method: 'POST',
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
    if (!excelFile || !testName) return;
    try {
      await createFromExcelMutation.mutateAsync({
        file: excelFile,
        testName,
        locationId: selectedLocationId || undefined,
        protocol: protocol || undefined,
        vestId: selectedVestId || undefined,
        testDate: testDate || undefined,
        dateFormat: dateFormat || undefined,
      });
      setShowCreateFromExcel(false);
      setExcelFile(null);
      setTestName('');
      setSelectedLocationId('');
      setProtocol('');
      setSelectedVestId('');
      setTestDate(new Date().toISOString().split('T')[0]);
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

    try {
      const formData = new FormData();
      bulkFiles.forEach(file => {
        formData.append('excel_files', file);
      });

      await apiClient.post('/api/v1/test-sessions/bulk-upload', formData);
      setShowBulkUpload(false);
      setBulkFiles([]);
      window.location.reload();
    } catch (err: any) {
      console.error('Failed to bulk upload:', err);
      alert(err?.detail || 'Failed to bulk upload. Check console for details.');
    }
  };

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      if (newSet.has(groupId)) {
        newSet.delete(groupId);
      } else {
        newSet.add(groupId);
      }
      return newSet;
    });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Test Sessions</h1>
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

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Lab</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-32 truncate">Protocol</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vest</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider max-w-32 truncate">Characteristic</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Excel</th>
                <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {parentSessions.map((parent) => {
              const children = groupedTests[parent.id] || [];
              const hasChildren = children.length > 0;
              const isExpanded = expandedGroups.has(parent.id);
              
              const sortedChildren = [...children].sort((a, b) => {
                const extractTestNumber = (name: string, parentName: string) => {
                  const suffix = name.replace(parentName + ' - ', '');
                  const match = suffix.match(/^(\d+)/);
                  return match ? parseInt(match[1], 10) : 0;
                };
                const numA = extractTestNumber(a.name, parent.name);
                const numB = extractTestNumber(b.name, parent.name);
                return numA - numB;
              });

              return (
                <Fragment key={parent.id}>
                  <tr
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => hasChildren && toggleGroup(parent.id)}
                  >
                    <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">
                      {hasChildren && (
                        <span className="mr-2 text-gray-500">
                          {isExpanded ? '▼' : '▶'}
                        </span>
                      )}
                      {parent.name}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{parent.test_date || '-'}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{parent.lab_name || '-'}</td>
                    <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate">{parent.protocol || '-'}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{parent.vest_code || '-'}</td>
                    <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate">{formatConditioning(parent.conditioning)}</td>
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
                  {isExpanded && hasChildren && sortedChildren.map((child) => (
                    <tr key={child.id} className="bg-gray-50 hover:bg-gray-100">
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-600 pl-12">
                        {child.name.replace(parent.name + ' - ', '')}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{child.test_date || '-'}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{child.lab_name || '-'}</td>
                      <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate">{child.protocol || '-'}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">{child.vest_code || '-'}</td>
                      <td className="px-2 py-2 whitespace-nowrap text-sm text-gray-500 max-w-32 truncate">{formatConditioning(child.conditioning)}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-sm text-gray-500">
                        {role !== 'viewer' && (
                          child.excel_file_path ? (
                            <span className="text-green-600">Uploaded</span>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setUploadTarget(child);
                              }}
                              className="text-indigo-600 hover:text-indigo-900"
                            >
                              Upload
                            </button>
                          )
                        )}
                        {role === 'viewer' && (
                          child.excel_file_path ? (
                            <span className="text-green-600">Uploaded</span>
                          ) : '-'
                        )}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => navigate(`/test-sessions/${child.id}`)}
                          className="text-indigo-600 hover:text-indigo-900 mr-3"
                        >
                          View
                        </button>
                        {role !== 'viewer' && (
                          <>
                            <button
                              onClick={() => setEditTarget(child)}
                              className="text-indigo-600 hover:text-indigo-900 mr-3"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => setDeleteTarget(child)}
                              className="text-red-600 hover:text-red-900"
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
            {testSessions?.length === 0 && (
              <tr>
                <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">
                  No test sessions found. Click "Upload Excel" to create one.
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
          title="Create Test Session from Excel"
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
                  {vests?.map((vest) => (
                    <option key={vest.id} value={vest.id}>
                      {vest.vest_code} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
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
            setSelectedLocationId('');
            setProtocol('');
            setSelectedVestId('');
            setTestDate(new Date().toISOString().split('T')[0]);
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
          message={
            <div className="space-y-4">
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
                <>
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
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Operator</label>
                    <input
                      type="text"
                      value={editTarget.operator || ''}
                      onChange={(e) => setEditTarget({ ...editTarget, operator: e.target.value || null })}
                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                    />
                  </div>
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
                </>
              )}
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
              {editTarget.parent_test_group_id && (
                <>
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
                </>
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
                  operator: editTarget.operator,
                  protocol: editTarget.protocol,
                  conditioning: editTarget.conditioning,
                  ambient_temperature_c: editTarget.ambient_temperature_c,
                  humidity_percent: editTarget.humidity_percent,
                  notes: editTarget.notes,
                }
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
          }}
        />
      )}

    </div>
  );
}
