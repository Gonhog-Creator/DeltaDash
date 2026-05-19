import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTestSession, useUpdateTestSession, useDeleteTestSession } from '../hooks/useTestSessions';
import { useShotDataByTestSession, useUpdateShotData } from '../hooks/useShotData';
import { TestSessionUpdate } from '../api/test_session';
import { ShotDataUpdate } from '../api/shot_data';
import { ConfirmModal } from '../components/ConfirmModal';

export function TestSessionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: testSession, isLoading, error } = useTestSession(id || '');
  const { data: shotData } = useShotDataByTestSession(id || '');
  const updateMutation = useUpdateTestSession();
  const deleteMutation = useDeleteTestSession();
  const updateShotMutation = useUpdateShotData();

  console.log('Test session ID:', id);
  console.log('Test session data:', testSession);
  console.log('Shot data:', shotData);
  
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<TestSessionUpdate>({});
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [editingShot, setEditingShot] = useState<any>(null);
  const [shotFormData, setShotFormData] = useState<ShotDataUpdate>({});

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading test session</div>;
  if (!testSession) return <div>Test session not found</div>;

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updateMutation.mutateAsync({ id: testSession.id, testSession: formData });
      setIsEditing(false);
      setFormData({});
    } catch (err) {
      console.error('Failed to update:', err);
    }
  };

  const handleDeleteConfirm = async () => {
    try {
      await deleteMutation.mutateAsync(testSession.id);
      navigate('/test-sessions');
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const handleShotEdit = (shot: any) => {
    setEditingShot(shot);
    setShotFormData({
      shot_number: shot.shot_number?.toString(),
      velocity_m_s: shot.velocity_m_s || shot.measured_velocity_m_s || undefined,
      trauma_mm: shot.trauma_mm || shot.bfd_mm || undefined,
      trauma_qualitative: shot.trauma_qualitative || undefined,
      angle_degrees: shot.angle_degrees || undefined,
      side: shot.side || undefined,
      vest_number: shot.vest_number || undefined,
      protection_level: shot.protection_level || undefined,
      caliber: shot.caliber || undefined,
      temperature_c: shot.temperature_c || undefined,
      humidity_percent: shot.humidity_percent || undefined,
    });
  };

  const handleShotUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingShot) return;
    try {
      await updateShotMutation.mutateAsync({ id: editingShot.id, shotData: shotFormData });
      setEditingShot(null);
      setShotFormData({});
    } catch (err) {
      console.error('Failed to update shot:', err);
    }
  };

  const startEdit = () => {
    setFormData({
      name: testSession.name,
      test_date: testSession.test_date || '',
      lab_name: testSession.lab_name || '',
      operator: testSession.operator || '',
      protocol: testSession.protocol || '',
      clay_temperature_c: testSession.clay_temperature_c,
      ambient_temperature_c: testSession.ambient_temperature_c,
      humidity_percent: testSession.humidity_percent,
      conditioning: testSession.conditioning || '',
      notes: testSession.notes || '',
    });
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setFormData({});
  };

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

  return (
    <div>
      <div className="mb-6">
        <button
          onClick={() => navigate('/test-sessions')}
          className="text-indigo-600 hover:text-indigo-900 mb-4 inline-block"
        >
          ← Back to Test Sessions
        </button>
        <h1 className="text-2xl font-bold text-gray-900">Test Session Details</h1>
      </div>

      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Session Information</h2>
          {!isEditing && (
            <div className="space-x-2">
              <button
                onClick={startEdit}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                Edit
              </button>
              <button
                onClick={() => setShowDeleteModal(true)}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          )}
        </div>

        {isEditing ? (
          <form onSubmit={handleUpdate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Session Name</label>
                <input
                  type="text"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Test Date</label>
                <input
                  type="date"
                  value={formData.test_date || ''}
                  onChange={(e) => setFormData({ ...formData, test_date: e.target.value || null })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Lab Name</label>
                <input
                  type="text"
                  value={formData.lab_name || ''}
                  onChange={(e) => setFormData({ ...formData, lab_name: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Operator</label>
                <input
                  type="text"
                  value={formData.operator || ''}
                  onChange={(e) => setFormData({ ...formData, operator: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Protocol</label>
                <input
                  type="text"
                  value={formData.protocol || ''}
                  onChange={(e) => setFormData({ ...formData, protocol: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Conditioning</label>
                <select
                  value={formData.conditioning || ''}
                  onChange={(e) => setFormData({ ...formData, conditioning: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="">Select conditioning...</option>
                  <option value="ambient">Ambient</option>
                  <option value="wet">Wet</option>
                  <option value="tumbled">Tumbled</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ambient Temperature (°C)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.ambient_temperature_c ?? ''}
                  onChange={(e) => setFormData({ ...formData, ambient_temperature_c: e.target.value ? parseFloat(e.target.value) : null })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Humidity (%)</label>
                <input
                  type="number"
                  step="0.1"
                  value={formData.humidity_percent ?? ''}
                  onChange={(e) => setFormData({ ...formData, humidity_percent: e.target.value ? parseFloat(e.target.value) : null })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
              <textarea
                rows={3}
                value={formData.notes || ''}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
              />
            </div>
            <div className="flex space-x-2">
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                Save
              </button>
              <button
                type="button"
                onClick={cancelEdit}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-sm font-medium text-gray-500">Name:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.name}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Date:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.test_date || '-'}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Lab:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.lab_name || '-'}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Operator:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.operator || '-'}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Protocol:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.protocol || '-'}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Characteristic:</span>
                <span className="ml-2 text-sm text-gray-900">{formatConditioning(testSession.conditioning)}</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Temperature:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.ambient_temperature_c ?? '-'}°C</span>
              </div>
              <div>
                <span className="text-sm font-medium text-gray-500">Humidity:</span>
                <span className="ml-2 text-sm text-gray-900">{testSession.humidity_percent ?? '-'}%</span>
              </div>
            </div>
            {testSession.notes && (
              <div>
                <span className="text-sm font-medium text-gray-500">Notes:</span>
                <p className="mt-1 text-sm text-gray-900">{testSession.notes}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {shotData && shotData.length > 0 && (() => {
        const sortedShots = shotData.sort((a, b) => parseFloat(a.shot_number) - parseFloat(b.shot_number));
        const frontShots = sortedShots.filter(shot => shot.side && (shot.side.toLowerCase() === 'frente' || shot.side.toLowerCase() === 'front'));
        const backShots = sortedShots.filter(shot => shot.side && (shot.side.toLowerCase() === 'espalda' || shot.side.toLowerCase() === 'back'));
        
        const renderShotTable = (shots: typeof shotData, title: string) => {
          const firstThreeShots = shots.slice(0, 3);
          const avgVelocity = firstThreeShots.reduce((sum, shot) => {
            const vel = shot.velocity_m_s || shot.measured_velocity_m_s;
            return sum + (parseFloat(vel) || 0);
          }, 0) / firstThreeShots.length;
          const avgTrauma = firstThreeShots.reduce((sum, shot) => {
            const trauma = shot.trauma_mm || shot.bfd_mm;
            return sum + (parseFloat(trauma) || 0);
          }, 0) / firstThreeShots.length;
          
          const hasQualitativeTrauma = shots.some(shot => shot.trauma_qualitative);
          const hasAngle = shots.some(shot => shot.angle_degrees);
          
          return (
            <div className="bg-white shadow rounded-lg p-6 mb-4">
              <h3 className="text-md font-semibold text-gray-900 mb-4">{title}</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Shot #</th>
                      {hasAngle && (
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Angle (°)</th>
                      )}
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Velocity (m/s)</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">{hasQualitativeTrauma ? 'Result' : 'Trauma (mm)'}</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {shots.map((shot) => (
                      <tr key={shot.id}>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{shot.shot_number}</td>
                        {hasAngle && (
                          <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                            {shot.angle_degrees ? `${shot.angle_degrees}°` : '-'}
                          </td>
                        )}
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          {shot.velocity_m_s || shot.measured_velocity_m_s || '-'}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          {shot.trauma_qualitative ? (
                            shot.trauma_qualitative === 'PERFORO' ? 'Punctured' : shot.trauma_qualitative
                          ) : (
                            shot.trauma_mm || shot.bfd_mm || '-'
                          )}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          <button
                            onClick={() => handleShotEdit(shot)}
                            className="text-indigo-600 hover:text-indigo-900"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    ))}
                    <tr className="bg-gray-100 font-semibold">
                      <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">Average</td>
                      {hasAngle && (
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900"></td>
                      )}
                      <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                        {avgVelocity.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                        {avgTrauma.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900"></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          );
        };
        
        return (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Shot Data</h2>
            {frontShots.length > 0 && renderShotTable(frontShots, 'Front')}
            {backShots.length > 0 && renderShotTable(backShots, 'Back')}
          </div>
        );
      })()}

      {showDeleteModal && (
        <ConfirmModal
          title="Delete Test Session"
          message={`Are you sure you want to delete "${testSession.name}"? This action cannot be undone.`}
          confirmLabel="Delete"
          variant="danger"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setShowDeleteModal(false)}
        />
      )}

      {editingShot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => {
            setEditingShot(null);
            setShotFormData({});
          }} />
          <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Edit Shot Data</h3>
            <form onSubmit={handleShotUpdate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Shot Number</label>
                  <input
                    type="text"
                    value={shotFormData.shot_number || ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, shot_number: e.target.value })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Velocity (m/s)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={shotFormData.velocity_m_s ?? ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, velocity_m_s: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Trauma (mm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={shotFormData.trauma_mm ?? ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, trauma_mm: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Angle (°)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={shotFormData.angle_degrees ?? ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, angle_degrees: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Side</label>
                  <select
                    value={shotFormData.side || ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, side: e.target.value || undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select side...</option>
                    <option value="front">Front</option>
                    <option value="back">Back</option>
                    <option value="frente">Frente</option>
                    <option value="espalda">Espalda</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Result</label>
                  <select
                    value={shotFormData.trauma_qualitative || ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, trauma_qualitative: e.target.value || undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select result...</option>
                    <option value="OK">OK</option>
                    <option value="Punctured">Punctured</option>
                    <option value="PERFORO">PERFORO</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Protection Level</label>
                  <input
                    type="text"
                    value={shotFormData.protection_level || ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, protection_level: e.target.value || undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Caliber</label>
                  <input
                    type="text"
                    value={shotFormData.caliber || ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, caliber: e.target.value || undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Temperature (°C)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={shotFormData.temperature_c ?? ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, temperature_c: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Humidity (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={shotFormData.humidity_percent ?? ''}
                    onChange={(e) => setShotFormData({ ...shotFormData, humidity_percent: e.target.value ? parseFloat(e.target.value) : undefined })}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => {
                    setEditingShot(null);
                    setShotFormData({});
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                >
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
