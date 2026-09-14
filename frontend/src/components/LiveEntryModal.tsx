import { useState, useEffect, useRef } from 'react';
import { X, Plus, Check, Wifi, WifiOff, Loader2, AlertCircle } from 'lucide-react';
import { useVests } from '../hooks/useVests';
import { useGeometries } from '../hooks/useGeometries';
import { useLocations } from '../hooks/useLocations';
import { useProtocols } from '../hooks/useProtocols';
import { useAmmunition } from '../hooks/useAmmunition';
import { useAuth } from '../hooks/useAuth';
import { useDraftSync } from '../hooks/useDraftSync';
import { DraftShotRow } from '../db/draftDb';
import { ShotGrid, ShotRowData } from './ShotGrid';
import { manualEntryApi, ManualEntryRequest, ManualEntryVestTab } from '../api/manualEntry';
import { ProtocolLevel } from '../api/protocols';
import { useQueryClient } from '@tanstack/react-query';

interface VestTab {
  id: string;
  vestNumber: string;
  size: string;
  conditioning: string;
  ballisticLimit: boolean;
  ammunitionId: string;
  shots: ShotRowData[];
}

const CONDITIONING_OPTIONS = ['ambient', 'wet', 'tumbled', 'ballistic_limit'];

interface LiveEntryModalProps {
  onClose: () => void;
  onSubmitted?: (sessionId: string) => void;
  draftKey?: string;
}

export function LiveEntryModal({ onClose, onSubmitted, draftKey: propDraftKey }: LiveEntryModalProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { data: vests } = useVests();
  const { data: geometries } = useGeometries();
  const { data: locations } = useLocations();
  const { data: protocols } = useProtocols();
  const { data: ammunition } = useAmmunition({ limit: 500 });

  const draftKey = propDraftKey || (user ? `user_${user.id}_new_${crypto.randomUUID()}` : null);
  const draft = useDraftSync(draftKey);

  // Session-level metadata
  const [sessionName, setSessionName] = useState('');
  const [testDate, setTestDate] = useState(new Date().toISOString().split('T')[0]);
  const [labName, setLabName] = useState('');
  const [protocol, setProtocol] = useState('');
  const [clayTempC, setClayTempC] = useState<number | null>(null);
  const [ambientTempC, setAmbientTempC] = useState<number | null>(null);
  const [humidityPercent, setHumidityPercent] = useState<number | null>(null);
  const [vestId, setVestId] = useState<string>('');
  const [geometryId, setGeometryId] = useState<string>('');
  const [isOfficial, setIsOfficial] = useState(false);
  const [certNumber, setCertNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [protectionLevel, setProtectionLevel] = useState('');

  // Vest tabs (modular: one per vest/size/conditioning)
  const [vestTabs, setVestTabs] = useState<VestTab[]>([
    {
      id: crypto.randomUUID(),
      vestNumber: '1',
      size: '',
      conditioning: 'ambient',
      ballisticLimit: false,
      ammunitionId: '',
      shots: [],
    },
  ]);
  const [activeTabId, setActiveTabId] = useState<string>('');

  // Submit state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showDraftRestored, setShowDraftRestored] = useState(false);

  // Initialize active tab
  useEffect(() => {
    if (vestTabs.length > 0 && !vestTabs.find((t) => t.id === activeTabId)) {
      setActiveTabId(vestTabs[0].id);
    }
  }, [vestTabs, activeTabId]);

  // Restore draft once data is loaded from IndexedDB
  const draftRestoredRef = useRef(false);
  useEffect(() => {
    if (draftRestoredRef.current) return;
    if (!draft.hasExistingDraft || !draft.meta) return;
    draftRestoredRef.current = true;

    const m = draft.meta;
    setSessionName(m.sessionName || '');
    setTestDate(m.testDate || new Date().toISOString().split('T')[0]);
    setLabName(m.labName || '');
    setProtocol(m.protocol || '');
    setClayTempC(m.clayTempC);
    setAmbientTempC(m.ambientTempC);
    setHumidityPercent(m.humidityPercent);
    setVestId(m.vestId || '');
    setGeometryId(m.geometryId || '');
    setIsOfficial(m.isOfficial);
    setCertNumber(m.certificationNumber || '');
    setNotes(m.notes || '');
    setProtectionLevel((m as any).protectionLevel || '');

    if (m.vestTabs?.length > 0) {
      const restoredTabs: VestTab[] = m.vestTabs.map((vt) => ({
        id: vt.id,
        vestNumber: vt.vestNumber || '',
        size: vt.size || '',
        conditioning: vt.conditioning || 'ambient',
        ballisticLimit: vt.ballisticLimit || false,
        ammunitionId: (vt as any).ammunitionId || '',
        shots: [],
      }));

      // Restore shot rows to their correct tabs
      if (draft.rows.length > 0) {
        const rowsByTab: Record<string, ShotRowData[]> = {};
        draft.rows.forEach((r) => {
          const tabId = (r as any).vestTabId || restoredTabs[0].id;
          if (!rowsByTab[tabId]) rowsByTab[tabId] = [];
          rowsByTab[tabId].push({
            id: crypto.randomUUID(),
            shot_number: r.shot_number,
            side: r.side,
            angle_degrees: r.angle_degrees,
            velocity_m_s: r.velocity_m_s,
            trauma_mm: r.trauma_mm,
            trauma_qualitative: r.trauma_qualitative,
          });
        });
        restoredTabs.forEach((tab) => {
          if (rowsByTab[tab.id]) {
            tab.shots = rowsByTab[tab.id];
          }
        });
      }

      setVestTabs(restoredTabs);
      setActiveTabId(restoredTabs[0].id);
    }

    setShowDraftRestored(true);
    setTimeout(() => setShowDraftRestored(false), 5000);
  }, [draft.hasExistingDraft, draft.meta, draft.rows]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-save to IndexedDB (debounced)
  useEffect(() => {
    if (!draftKey) return;
    const timer = setTimeout(() => {
      draft.saveMeta({
        sessionName,
        testDate,
        labName,
        protocol,
        clayTempC,
        ambientTempC,
        humidityPercent,
        vestId,
        geometryId,
        isOfficial,
        certificationNumber: certNumber,
        notes,
        protectionLevel,
        vestTabs: vestTabs.map((t) => ({
          id: t.id,
          vestNumber: t.vestNumber,
          size: t.size,
          conditioning: t.conditioning,
          ballisticLimit: t.ballisticLimit,
          ammunitionId: t.ammunitionId,
        })),
      });
    }, 800);
    return () => clearTimeout(timer);
  }, [sessionName, testDate, labName, protocol, clayTempC, ambientTempC, humidityPercent, vestId, geometryId, isOfficial, certNumber, notes, vestTabs]); // eslint-disable-line react-hooks/exhaustive-deps

  // Save shot rows to IndexedDB when any tab's shots change (debounced)
  useEffect(() => {
    if (!draftKey) return;
    const timer = setTimeout(() => {
      const allRows: Omit<DraftShotRow, 'id' | 'draftKey' | 'updatedAt' | 'rowIndex'>[] = [];
      vestTabs.forEach((tab) => {
        tab.shots.forEach((s) => {
          allRows.push({
            vestTabId: tab.id,
            shot_number: s.shot_number,
            side: s.side,
            vest_number: tab.vestNumber,
            angle_degrees: s.angle_degrees,
            velocity_m_s: s.velocity_m_s,
            trauma_mm: s.trauma_mm,
            trauma_qualitative: s.trauma_qualitative,
          });
        });
      });
      draft.saveRows(allRows);
    }, 800);
    return () => clearTimeout(timer);
  }, [vestTabs]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeTab = vestTabs.find((t) => t.id === activeTabId);

  // Get available sizes from selected geometry
  const selectedGeometry = geometries?.find((g) => g.id === geometryId);
  const availableSizes = selectedGeometry?.available_sizes || [];

  // Get protection level options from selected protocol's levels_config
  const selectedProtocol = protocols?.find((p) => p.name === protocol);
  const protectionLevelOptions: string[] = selectedProtocol?.levels_config?.map((l: ProtocolLevel) => l.level_name) || [];

  // Get ammunition options filtered by selected protection level
  const ammoForLevel = selectedProtocol?.levels_config?.find((l: ProtocolLevel) => l.level_name === protectionLevel);
  const availableAmmoIds = ammoForLevel?.ammunition_config?.map((a) => a.ammunition_id) || [];
  const availableAmmo = ammunition?.filter((a) => availableAmmoIds.includes(a.id)) || [];

  // Get the selected ammunition for the active tab (for caliber in payload)
  const selectedAmmo = ammunition?.find((a) => a.id === activeTab?.ammunitionId) || null;

  const addVestTab = () => {
    const newTab: VestTab = {
      id: crypto.randomUUID(),
      vestNumber: String(vestTabs.length + 1),
      size: '',
      conditioning: 'ambient',
      ballisticLimit: false,
      ammunitionId: '',
      shots: [],
    };
    setVestTabs([...vestTabs, newTab]);
    setActiveTabId(newTab.id);
  };

  const removeVestTab = (tabId: string) => {
    if (vestTabs.length <= 1) return;
    const filtered = vestTabs.filter((t) => t.id !== tabId);
    setVestTabs(filtered);
    if (activeTabId === tabId) {
      setActiveTabId(filtered[0].id);
    }
  };

  const updateTab = (tabId: string, patch: Partial<VestTab>) => {
    setVestTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, ...patch } : t)));
  };

  const updateTabShots = (tabId: string, shots: ShotRowData[]) => {
    setVestTabs((prev) => prev.map((t) => (t.id === tabId ? { ...t, shots } : t)));
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setIsSubmitting(true);

    try {
      // Validate required fields
      if (!sessionName.trim()) throw new Error('Session name is required');
      if (!geometryId) throw new Error('Geometry is required');
      const hasShots = vestTabs.some((t) => t.shots.length > 0);
      if (!hasShots) throw new Error('At least one shot is required');

      // Build request
      const vestTabsPayload: ManualEntryVestTab[] = vestTabs
        .filter((t) => t.shots.length > 0)
        .map((t, idx) => {
          const vestNum = String(idx + 1);
          return {
          vest_number: vestNum,
          size: t.size || null,
          conditioning: t.conditioning || null,
          ballistic_limit: t.ballisticLimit || false,
          shots: t.shots.map((s) => ({
            shot_number: s.shot_number,
            side: s.side,
            vest_number: vestNum,
            angle_degrees: s.angle_degrees,
            caliber: selectedAmmo?.caliber || null,
            velocity_m_s: s.velocity_m_s,
            trauma_mm: s.trauma_mm,
            trauma_qualitative: s.trauma_qualitative,
            protection_level: protectionLevel || null,
            temperature_c: ambientTempC,
            humidity_percent: humidityPercent,
          })),
        };
        });

      const payload: ManualEntryRequest = {
        name: sessionName,
        test_date: testDate || null,
        lab_name: labName || null,
        protocol: protocol || null,
        clay_temperature_c: clayTempC,
        ambient_temperature_c: ambientTempC,
        humidity_percent: humidityPercent,
        vest_id: vestId || null,
        geometry_id: geometryId,
        is_official: isOfficial,
        certification_number: certNumber || null,
        notes: notes || null,
        protection_level: protectionLevel || null,
        vest_tabs: vestTabsPayload,
      };

      const result = await manualEntryApi.submit(payload);

      // Clear draft from IndexedDB
      await draft.clearDraft();

      // Invalidate test sessions query so the list refreshes
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });

      if (onSubmitted) {
        onSubmitted(result.parent_session_id);
      } else {
        onClose();
      }
    } catch (err: any) {
      const detail = err?.detail;
      if (typeof detail === 'object' && detail?.missing_calibers) {
        setSubmitError(`Missing calibers in ammunition DB: ${detail.missing_calibers.join(', ')}`);
      } else if (typeof detail === 'object' && detail?.missing_shots) {
        setSubmitError(detail.message || detail.missing_shots.join('\n'));
      } else {
        setSubmitError(err?.message || 'Failed to submit. Your data is saved locally.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const syncStatusBadge = () => {
    const { syncStatus, isOnline, lastSaved } = draft;
    if (!isOnline) {
      return (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
          <WifiOff size={14} />
          Offline — saved locally
        </div>
      );
    }
    if (syncStatus === 'syncing') {
      return (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
          <Loader2 size={14} className="animate-spin" />
          Saving...
        </div>
      );
    }
    if (syncStatus === 'error') {
      return (
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
          <AlertCircle size={14} />
          Error
        </div>
      );
    }
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
        <Wifi size={14} />
        {lastSaved ? `Saved ${lastSaved.toLocaleTimeString()}` : 'Saved'}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 bg-gray-900/80 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-gray-900">Live Shot-by-Shot Data Entry</h2>
          {syncStatusBadge()}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* Draft restored banner */}
      {showDraftRestored && (
        <div className="px-6 py-2 bg-blue-50 text-blue-700 text-sm flex items-center gap-2">
          <Check size={16} />
          Restored your draft from earlier. You can continue where you left off.
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-hidden flex flex-col bg-gray-50">
        {/* Session Setup Panel */}
        <div className="px-6 py-4 bg-white border-b border-gray-200">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Session Name *</label>
              <input
                type="text"
                value={sessionName}
                onChange={(e) => setSessionName(e.target.value)}
                placeholder="e.g. NIJ Test - Batch 2024-01"
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Test Date</label>
              <input
                type="date"
                value={testDate}
                onChange={(e) => setTestDate(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Lab / Location</label>
              <select
                value={labName}
                onChange={(e) => setLabName(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              >
                <option value="">—</option>
                {locations?.map((loc) => (
                  <option key={loc.id} value={loc.name}>{loc.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Protocol</label>
              <select
                value={protocol}
                onChange={(e) => setProtocol(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              >
                <option value="">—</option>
                {protocols?.map((p) => (
                  <option key={p.id} value={p.name}>{p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Vest</label>
              <select
                value={vestId}
                onChange={(e) => setVestId(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              >
                <option value="">—</option>
                {vests?.map((v) => (
                  <option key={v.id} value={v.id}>{v.vest_code}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Geometry *</label>
              <select
                value={geometryId}
                onChange={(e) => setGeometryId(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              >
                <option value="">Select...</option>
                {geometries?.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Clay Temp (°C)</label>
              <input
                type="number"
                step="0.1"
                value={clayTempC ?? ''}
                onChange={(e) => setClayTempC(e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Ambient Temp (°C)</label>
              <input
                type="number"
                step="0.1"
                value={ambientTempC ?? ''}
                onChange={(e) => setAmbientTempC(e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Humidity (%)</label>
              <input
                type="number"
                step="0.1"
                value={humidityPercent ?? ''}
                onChange={(e) => setHumidityPercent(e.target.value ? parseFloat(e.target.value) : null)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div className="flex items-end gap-2 pb-1">
              <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={isOfficial}
                  onChange={(e) => setIsOfficial(e.target.checked)}
                  className="rounded border-gray-300"
                />
                Official
              </label>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Cert #</label>
              <input
                type="text"
                value={certNumber}
                onChange={(e) => setCertNumber(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Protection Level</label>
              <select
                value={protectionLevel}
                onChange={(e) => setProtectionLevel(e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none"
              >
                <option value="">—</option>
                {protectionLevelOptions.map((lvl) => (
                  <option key={lvl} value={lvl}>{lvl}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Vest Tabs */}
        <div className="flex items-center gap-1 px-6 pt-3 bg-white border-b border-gray-200">
          {vestTabs.map((tab) => (
            <div
              key={tab.id}
              onClick={() => setActiveTabId(tab.id)}
              className={`flex items-center gap-1 px-3 py-2 text-sm font-medium cursor-pointer rounded-t-lg border-b-2 transition-colors ${
                activeTabId === tab.id
                  ? 'border-blue-500 text-blue-600 bg-blue-50'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              Vest {vestTabs.findIndex((t) => t.id === tab.id) + 1}
              {tab.size && ` · ${tab.size}`}
              {vestTabs.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeVestTab(tab.id);
                  }}
                  className="ml-1 text-gray-400 hover:text-red-500"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
          <button
            onClick={addVestTab}
            className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-t-lg transition-colors"
          >
            <Plus size={14} />
            Add Vest
          </button>
        </div>

        {/* Tab-level controls (vest number, size, conditioning) */}
        {activeTab && (
          <div className="px-6 py-2 bg-white border-b border-gray-200 flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Vest #</label>
              <span className="px-2 py-1 text-sm font-medium text-gray-700 bg-gray-100 rounded">
                {vestTabs.findIndex((t) => t.id === activeTab.id) + 1}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Size</label>
              <select
                value={activeTab.size}
                onChange={(e) => updateTab(activeTab.id, { size: e.target.value })}
                className="px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400 outline-none"
              >
                <option value="">—</option>
                {availableSizes.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Conditioning</label>
              <select
                value={activeTab.conditioning}
                onChange={(e) => updateTab(activeTab.id, { conditioning: e.target.value })}
                className="px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400 outline-none"
              >
                {CONDITIONING_OPTIONS.map((c) => (
                  <option key={c} value={c}>
                    {c === 'ballistic_limit' ? 'Ballistic Limit' : c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={activeTab.ballisticLimit}
                onChange={(e) => updateTab(activeTab.id, { ballisticLimit: e.target.checked })}
                className="rounded border-gray-300"
              />
              Ballistic Limit
            </label>
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-500">Ammunition</label>
              <select
                value={activeTab.ammunitionId}
                onChange={(e) => updateTab(activeTab.id, { ammunitionId: e.target.value })}
                className="px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400 outline-none min-w-[180px]"
              >
                <option value="">—</option>
                {availableAmmo.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.caliber} — {a.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Shot Grid */}
        <div className="flex-1 overflow-hidden p-6">
          {activeTab && (
            <ShotGrid
              data={activeTab.shots}
              onChange={(shots) => updateTabShots(activeTab.id, shots)}
              ballisticLimit={activeTab.ballisticLimit}
            />
          )}
        </div>
      </div>

      {/* Footer / Submit bar */}
      <div className="px-6 py-3 bg-white border-t border-gray-200 flex items-center justify-between">
        <div className="text-sm text-gray-500">
          {vestTabs.reduce((sum, t) => sum + t.shots.length, 0)} total shot{vestTabs.reduce((sum, t) => sum + t.shots.length, 0) !== 1 ? 's' : ''} across {vestTabs.length} vest{vestTabs.length !== 1 ? 's' : ''}
        </div>
        <div className="flex items-center gap-3">
          {submitError && (
            <div className="flex items-center gap-1.5 text-sm text-red-600">
              <AlertCircle size={14} />
              {submitError}
            </div>
          )}
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 rounded-lg transition-colors"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Check size={16} />
                Submit & Create Session
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
