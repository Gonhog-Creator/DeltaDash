import { useState, Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTestSessions, useDeleteTestSession, useUploadExcel, useCreateFromExcel } from '../hooks/useTestSessions';
import { useLocations, useDeleteLocation, useUpdateLocation } from '../hooks/useLocations';
import { useProtocols, useDeleteProtocol, useUpdateProtocol } from '../hooks/useProtocols';
import { useAuth } from '../hooks/useAuth';
import { TestSession } from '../api/test_session';
import { ConfirmModal } from '../components/ConfirmModal';
import { LocationManagementModal } from '../components/LocationManagementModal';
import { ProtocolManagementModal } from '../components/ProtocolManagementModal';

export function TestSessions() {
  const navigate = useNavigate();
  const { data: testSessions, isLoading, error } = useTestSessions();
  const { data: locations } = useLocations();
  const { data: protocols } = useProtocols();
  const { isAdmin } = useAuth();
  const deleteLocationMutation = useDeleteLocation();
  const updateLocationMutation = useUpdateLocation();
  const deleteProtocolMutation = useDeleteProtocol();
  const updateProtocolMutation = useUpdateProtocol();
  const deleteMutation = useDeleteTestSession();
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
  const [showCreateFromExcel, setShowCreateFromExcel] = useState(false);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [testName, setTestName] = useState('');
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [protocol, setProtocol] = useState('');
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
    } catch (err) {
      console.error('Failed to upload Excel:', err);
    }
  };

  const handleCreateFromExcel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!excelFile || !testName) return;
    try {
      await createFromExcelMutation.mutateAsync({
        file: excelFile,
        testName,
        locationId: selectedLocationId || undefined,
        protocol: protocol || undefined,
        testDate: testDate || undefined,
      });
      setShowCreateFromExcel(false);
      setExcelFile(null);
      setTestName('');
      setSelectedLocationId('');
      setProtocol('');
      setTestDate(new Date().toISOString().split('T')[0]);
    } catch (err) {
      console.error('Failed to create test session from Excel:', err);
    }
  };

  const handleBulkReupload = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/test-sessions/admin/bulk-reupload-all', {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to bulk re-upload');
      }

      setShowAdminModal(false);
      window.location.reload();
    } catch (err) {
      console.error('Failed to bulk re-upload:', err);
      alert('Failed to bulk re-upload. Check console for details.');
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
          <button
            onClick={() => setShowCreateFromExcel(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            Upload Excel
          </button>
        </div>
      </div>

      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Lab</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Operator</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Protocol</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Characteristic</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Excel</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {parentSessions.map((parent) => {
              const children = groupedTests[parent.id] || [];
              const hasChildren = children.length > 0;
              const isExpanded = expandedGroups.has(parent.id);

              return (
                <Fragment key={parent.id}>
                  <tr 
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => hasChildren && toggleGroup(parent.id)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {hasChildren && (
                        <span className="mr-2 text-gray-500">
                          {isExpanded ? '▼' : '▶'}
                        </span>
                      )}
                      {parent.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{parent.test_date || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{parent.lab_name || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{parent.operator || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{parent.protocol || '-'}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatConditioning(parent.conditioning)}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {parent.excel_file_path ? (
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
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(parent);
                        }}
                        className="text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  {isExpanded && hasChildren && children.map((child) => (
                    <tr key={child.id} className="bg-gray-50 hover:bg-gray-100">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 pl-12">
                        {child.name.replace(parent.name + ' - ', '')}
                        {child.size && `, ${child.size}`}
                        {child.conditioning && `, ${formatConditioning(child.conditioning)}`}
                        {child.ballistic_limit && ' (Ballistic Limit)'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{child.test_date || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{child.lab_name || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{child.operator || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{child.protocol || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatConditioning(child.conditioning)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {child.excel_file_path ? (
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
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => navigate(`/test-sessions/${child.id}`)}
                          className="text-indigo-600 hover:text-indigo-900 mr-3"
                        >
                          View
                        </button>
                        <button
                          onClick={() => setDeleteTarget(child)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </Fragment>
              );
            })}
            {testSessions?.length === 0 && (
              <tr>
                <td colSpan={7} className="px-6 py-4 text-center text-sm text-gray-500">
                  No test sessions found. Click "Upload Excel" to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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
                <label className="block text-sm font-medium text-gray-700 mb-1">Test Date</label>
                <input
                  type="date"
                  value={testDate}
                  onChange={(e) => setTestDate(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Excel File</label>
                <input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
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

    </div>
  );
}
