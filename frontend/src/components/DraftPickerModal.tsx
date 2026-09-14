import { useState, useEffect } from 'react';
import { X, Trash2, FileText, Plus } from 'lucide-react';
import { listDraftsForUser, deleteDraftByKey, DraftSummary } from '../db/draftDb';

interface DraftPickerModalProps {
  userId: string;
  onContinue: (draftKey: string) => void;
  onStartNew: () => void;
  onClose: () => void;
}

export function DraftPickerModal({ userId, onContinue, onStartNew, onClose }: DraftPickerModalProps) {
  const [drafts, setDrafts] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDrafts = async (autoStart = false) => {
    setLoading(true);
    const result = await listDraftsForUser(userId);
    setDrafts(result);
    setLoading(false);
    // Auto-start a new entry if no drafts exist (only on initial load)
    if (autoStart && result.length === 0) {
      onStartNew();
    }
  };

  useEffect(() => {
    loadDrafts(true);
  }, [userId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async (key: string) => {
    await deleteDraftByKey(key);
    await loadDrafts();
  };

  const formatDate = (timestamp: number) => {
    const d = new Date(timestamp);
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Live Data Entry Drafts</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading drafts...</div>
          ) : drafts.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-500 mb-4">No saved drafts found.</p>
              <button
                onClick={onStartNew}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 inline-flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Start New Entry
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {drafts.map((draft) => (
                <div
                  key={draft.key}
                  className="flex items-center justify-between border border-gray-200 rounded-lg p-4 hover:border-gray-300"
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <FileText className="w-5 h-5 text-gray-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {draft.sessionName}
                      </p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {draft.testDate || 'No date'} · {draft.protocol || 'No protocol'} · {draft.shotCount} shots · {draft.tabCount} tab(s)
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Last saved: {formatDate(draft.updatedAt)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                    <button
                      onClick={() => onContinue(draft.key)}
                      className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
                    >
                      Continue
                    </button>
                    <button
                      onClick={() => handleDelete(draft.key)}
                      className="p-1.5 text-red-600 hover:text-red-800 hover:bg-red-50 rounded-md"
                      title="Delete draft"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {drafts.length > 0 && (
          <div className="p-6 border-t border-gray-200">
            <button
              onClick={onStartNew}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 inline-flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Start New Entry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
