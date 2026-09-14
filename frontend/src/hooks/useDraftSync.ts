import { useState, useEffect, useCallback, useRef } from 'react';
import { db, DraftShotRow, DraftMeta } from '../db/draftDb';

export type SyncStatus = 'idle' | 'synced' | 'syncing' | 'offline' | 'error';

export function useDraftSync(draftKey: string | null) {
  const [meta, setMeta] = useState<DraftMeta | null>(null);
  const [rows, setRows] = useState<DraftShotRow[]>([]);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('idle');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const loadedKeyRef = useRef<string | null>(null);

  // Track online/offline
  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  // Load draft from IndexedDB on mount or when draftKey changes
  const loadDraft = useCallback(async (key: string) => {
    const savedMeta = await db.meta.get(key);
    const savedRows = await db.shots
      .where('draftKey')
      .equals(key)
      .sortBy('rowIndex');
    if (savedMeta) {
      setMeta(savedMeta);
      setRows(savedRows);
      setLastSaved(new Date(savedMeta.updatedAt));
    } else {
      setMeta(null);
      setRows([]);
      setLastSaved(null);
    }
  }, []);

  useEffect(() => {
    if (!draftKey) return;
    if (loadedKeyRef.current === draftKey) return;
    loadedKeyRef.current = draftKey;
    loadDraft(draftKey);
  }, [draftKey, loadDraft]);

  // Auto-update sync status based on online state
  useEffect(() => {
    if (!isOnline) {
      setSyncStatus('offline');
    } else if (syncStatus === 'offline') {
      setSyncStatus('synced');
    }
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  // Save meta to IndexedDB
  const saveMeta = useCallback(
    async (newMeta: Omit<DraftMeta, 'key' | 'updatedAt'>) => {
      if (!draftKey) return;
      const fullMeta: DraftMeta = {
        ...newMeta,
        key: draftKey,
        updatedAt: Date.now(),
      };
      await db.meta.put(fullMeta);
      setMeta(fullMeta);
      setLastSaved(new Date());
      setSyncStatus(isOnline ? 'synced' : 'offline');
    },
    [draftKey, isOnline]
  );

  // Save all rows (bulk replace)
  const saveRows = useCallback(
    async (newRows: Omit<DraftShotRow, 'id' | 'draftKey' | 'updatedAt' | 'rowIndex'>[]) => {
      if (!draftKey) return;
      // Delete old rows for this draft
      await db.shots.where('draftKey').equals(draftKey).delete();
      // Insert new rows
      const rowsWithMeta: DraftShotRow[] = newRows.map((r, i) => ({
        ...r,
        draftKey,
        rowIndex: i,
        updatedAt: Date.now(),
      }));
      await db.shots.bulkAdd(rowsWithMeta);
      setRows(rowsWithMeta);
      setLastSaved(new Date());
      setSyncStatus(isOnline ? 'synced' : 'offline');
    },
    [draftKey, isOnline]
  );

  // Update a single row
  const updateRow = useCallback(
    async (rowIndex: number, patch: Partial<DraftShotRow>) => {
      if (!draftKey) return;
      const existing = await db.shots
        .where('draftKey')
        .equals(draftKey)
        .and((r) => r.rowIndex === rowIndex)
        .first();
      if (existing) {
        const updated = { ...existing, ...patch, updatedAt: Date.now() };
        await db.shots.update(existing.id!, updated);
        setRows((prev) =>
          prev.map((r) => (r.rowIndex === rowIndex ? updated : r))
        );
      } else {
        const newRow: DraftShotRow = {
          ...patch,
          draftKey,
          rowIndex,
          updatedAt: Date.now(),
        } as DraftShotRow;
        await db.shots.add(newRow);
        setRows((prev) => [...prev, newRow]);
      }
      setLastSaved(new Date());
      setSyncStatus(isOnline ? 'synced' : 'offline');
    },
    [draftKey, isOnline]
  );

  // Clear draft after successful submit
  const clearDraft = useCallback(async () => {
    if (!draftKey) return;
    await db.shots.where('draftKey').equals(draftKey).delete();
    await db.meta.delete(draftKey);
    setMeta(null);
    setRows([]);
    setLastSaved(null);
    setSyncStatus('idle');
  }, [draftKey]);

  // Check for existing draft on mount
  const hasExistingDraft = meta !== null && rows.length > 0;

  return {
    meta,
    rows,
    syncStatus,
    lastSaved,
    isOnline,
    hasExistingDraft,
    saveMeta,
    saveRows,
    updateRow,
    clearDraft,
    loadDraft,
  };
}
