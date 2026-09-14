import Dexie, { Table } from 'dexie';

export interface DraftShotRow {
  id?: number;
  draftKey: string;
  rowIndex: number;
  vestTabId: string;
  shot_number: string;
  side: string | null;
  vest_number: string | null;
  angle_degrees: number | null;
  velocity_m_s: number | null;
  trauma_mm: number | null;
  trauma_qualitative: string | null;
  updatedAt: number;
}

export interface DraftMeta {
  key: string; // same draftKey
  sessionName: string;
  testDate: string | null;
  labName: string | null;
  protocol: string | null;
  clayTempC: number | null;
  ambientTempC: number | null;
  humidityPercent: number | null;
  vestId: string | null;
  geometryId: string | null;
  isOfficial: boolean;
  certificationNumber: string | null;
  notes: string | null;
  protectionLevel: string | null;
  vestTabs: VestTabDraft[];
  updatedAt: number;
}

export interface VestTabDraft {
  id: string;
  vestNumber: string | null;
  size: string | null;
  conditioning: string | null;
  ballisticLimit: boolean;
  ammunitionId: string | null;
}

export interface DraftState {
  meta: DraftMeta | null;
  rows: DraftShotRow[];
}

class DraftDB extends Dexie {
  shots!: Table<DraftShotRow, number>;
  meta!: Table<DraftMeta, string>;

  constructor() {
    super('DeltaDashDrafts');
    this.version(1).stores({
      shots: '++id, draftKey, rowIndex, updatedAt',
      meta: 'key, updatedAt',
    });
    this.version(2).stores({
      shots: '++id, draftKey, vestTabId, rowIndex, updatedAt',
      meta: 'key, updatedAt',
    });
  }
}

const db = new DraftDB();

export interface DraftSummary {
  key: string;
  sessionName: string;
  testDate: string | null;
  protocol: string | null;
  shotCount: number;
  tabCount: number;
  updatedAt: number;
}

export async function listDraftsForUser(userId: string): Promise<DraftSummary[]> {
  const prefix = `user_${userId}_`;
  const allMeta = await db.meta.toArray();
  const userMeta = allMeta.filter((m) => m.key.startsWith(prefix));
  const summaries: DraftSummary[] = [];
  for (const m of userMeta) {
    const shotCount = await db.shots.where('draftKey').equals(m.key).count();
    summaries.push({
      key: m.key,
      sessionName: m.sessionName || '(unnamed)',
      testDate: m.testDate,
      protocol: m.protocol,
      shotCount,
      tabCount: m.vestTabs?.length || 0,
      updatedAt: m.updatedAt,
    });
  }
  summaries.sort((a, b) => b.updatedAt - a.updatedAt);
  return summaries;
}

export async function deleteDraftByKey(key: string): Promise<void> {
  await db.shots.where('draftKey').equals(key).delete();
  await db.meta.delete(key);
}

export { db };
