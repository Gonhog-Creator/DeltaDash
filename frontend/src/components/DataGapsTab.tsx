import { useEffect, useMemo, useState } from 'react';
import { apiClient } from '../api/client';

interface MissingField {
  field: string;
  label: string;
  critical: boolean;
}

interface GapRow {
  id: string;
  name: string;
  missing: MissingField[];
  [key: string]: any;
}

interface DataGaps {
  materials: GapRow[];
  vests: GapRow[];
  ammunition: GapRow[];
  test_sessions: GapRow[];
  shot_data: {
    total_shots: number;
    missing_velocity: number;
    missing_bfd: number;
    missing_outcome: number;
    missing_ammo: number;
  };
}

const CRIT_STYLE = 'bg-red-100 text-red-800';
const INFO_STYLE = 'bg-amber-50 text-amber-800';

function MissingBadges({ missing }: { missing: MissingField[] }) {
  if (missing.length === 0) {
    return <span className="text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded">complete</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {missing.map((m) => (
        <span
          key={m.field}
          className={`text-xs px-2 py-0.5 rounded ${m.critical ? CRIT_STYLE : INFO_STYLE}`}
          title={m.field}
        >
          {m.label}
        </span>
      ))}
    </div>
  );
}

function GapTable({
  title,
  rows,
  extraCols,
}: {
  title: string;
  rows: GapRow[];
  extraCols?: { key: string; label: string; render?: (r: GapRow) => React.ReactNode }[];
}) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? rows : rows.slice(0, 15);
  const incomplete = rows.filter((r) => r.missing.length > 0).length;
  return (
    <div className="mb-8">
      <h3 className="text-lg font-semibold mb-2">
        {title}
        <span className="ml-2 text-sm font-normal text-gray-500">
          {incomplete} of {rows.length} incomplete
        </span>
      </h3>
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              {extraCols?.map((c) => (
                <th key={c.key} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                  {c.label}
                </th>
              ))}
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Missing</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100">
            {shown.map((r) => (
              <tr key={r.id} className={r.missing.length === 0 ? 'opacity-60' : ''}>
                <td className="px-4 py-2 text-sm font-medium text-gray-900 whitespace-nowrap">{r.name}</td>
                {extraCols?.map((c) => (
                  <td key={c.key} className="px-4 py-2 text-sm text-gray-600 whitespace-nowrap">
                    {c.render ? c.render(r) : r[c.key] ?? '—'}
                  </td>
                ))}
                <td className="px-4 py-2 text-sm"><MissingBadges missing={r.missing} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 15 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-1 text-sm text-indigo-600 hover:text-indigo-800"
        >
          {expanded ? 'Show less' : `Show all ${rows.length} rows`}
        </button>
      )}
    </div>
  );
}

export function DataGapsTab({ onError }: { onError: (e: string | null) => void }) {
  const [data, setData] = useState<DataGaps | null>(null);
  const [loading, setLoading] = useState(true);
  const [onlyUsed, setOnlyUsed] = useState(true);

  useEffect(() => {
    apiClient
      .get<DataGaps>('/api/v1/analytics/data-gaps')
      .then(setData)
      .catch((err) => onError(err.detail || 'Failed to load data gaps'))
      .finally(() => setLoading(false));
  }, [onError]);

  const materials = useMemo(
    () => (data ? data.materials.filter((m) => !onlyUsed || m.used_in_vests) : []),
    [data, onlyUsed]
  );

  if (loading) return <div className="text-gray-500 py-8">Scanning database for missing data…</div>;
  if (!data) return null;

  const s = data.shot_data;
  return (
    <div>
      <div className="mb-6 p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-900">
        Missing fields listed per entity.{' '}
        <span className={`${CRIT_STYLE} px-1.5 py-0.5 rounded text-xs font-medium`}>red</span> = required by
        the ballistic model / Monte Carlo.{' '}
        <span className={`${INFO_STYLE} px-1.5 py-0.5 rounded text-xs font-medium`}>amber</span> = useful for
        traceability, not currently blocking.
      </div>

      <div className="mb-8 p-4 bg-white border border-gray-200 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Shot data summary</h3>
        <p className="text-sm text-gray-600">
          {s.total_shots} shots — missing velocity: <b>{s.missing_velocity}</b>, missing BFD (trauma):{' '}
          <b>{s.missing_bfd}</b>, missing outcome: <b>{s.missing_outcome}</b>, unmatched ammunition:{' '}
          <b>{s.missing_ammo}</b>
        </p>
      </div>

      <label className="flex items-center gap-2 mb-3 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={onlyUsed}
          onChange={(e) => setOnlyUsed(e.target.checked)}
          className="rounded"
        />
        Materials: show only those used in vest configurations
      </label>
      <GapTable
        title="Materials"
        rows={materials}
        extraCols={[
          { key: 'used_in_vests', label: 'In use', render: (r) => (r.used_in_vests ? 'yes' : 'no') },
        ]}
      />

      <GapTable
        title="Vests"
        rows={data.vests}
        extraCols={[
          { key: 'threat_level', label: 'Threat' },
          { key: 'layers_configured', label: 'Layers' },
          { key: 'shots', label: 'Shots' },
        ]}
      />

      <GapTable
        title="Ammunition"
        rows={data.ammunition}
        extraCols={[{ key: 'caliber', label: 'Caliber' }]}
      />

      <GapTable
        title="Test Sessions"
        rows={data.test_sessions}
        extraCols={[{ key: 'test_date', label: 'Date' }]}
      />
    </div>
  );
}
