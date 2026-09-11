import { useState, Fragment } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditLogsApi, AuditLogEntry } from '../api/auditLogs';
import { useAuth } from '../hooks/useAuth';

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-green-100 text-green-800',
  update: 'bg-blue-100 text-blue-800',
  delete: 'bg-red-100 text-red-800',
  upload: 'bg-purple-100 text-purple-800',
  upload_pliego: 'bg-purple-100 text-purple-800',
  delete_pliego: 'bg-red-100 text-red-800',
  upload_document: 'bg-purple-100 text-purple-800',
  delete_document: 'bg-red-100 text-red-800',
  update_layers: 'bg-blue-100 text-blue-800',
  bulk_reupload_all_test_sessions: 'bg-orange-100 text-orange-800',
  delete_test_session: 'bg-red-100 text-red-800',
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function JsonDiff({ before, after }: { before: Record<string, any> | null; after: Record<string, any> | null }) {
  if (!before && !after) return <span className="text-gray-400 text-sm">No data</span>;

  const allKeys = new Set([...Object.keys(before || {}), ...Object.keys(after || {})]);

  return (
    <div className="space-y-1 text-xs font-mono">
      {Array.from(allKeys).sort().map(key => {
        const beforeVal = before?.[key];
        const afterVal = after?.[key];

        if (beforeVal === afterVal) return null;

        const isDeleted = beforeVal !== undefined && afterVal === undefined;
        const isAdded = beforeVal === undefined && afterVal !== undefined;
        const isChanged = beforeVal !== undefined && afterVal !== undefined && beforeVal !== afterVal;

        return (
          <div key={key} className="flex gap-2">
            <span className="text-gray-500 min-w-[140px]">{key}:</span>
            {isDeleted && (
              <span className="text-red-600 line-through">{JSON.stringify(beforeVal)}</span>
            )}
            {isAdded && (
              <span className="text-green-600">{JSON.stringify(afterVal)}</span>
            )}
            {isChanged && (
              <>
                <span className="text-red-600 line-through">{JSON.stringify(beforeVal)}</span>
                <span className="text-gray-400">→</span>
                <span className="text-green-600">{JSON.stringify(afterVal)}</span>
              </>
            )}
          </div>
        );
      })}
      {Array.from(allKeys).every(key => before?.[key] === after?.[key]) && (
        <span className="text-gray-400 italic">No data changes</span>
      )}
    </div>
  );
}

export function AuditLogs() {
  const { isAdmin } = useAuth();
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('');
  const [actionFilter, setActionFilter] = useState<string>('');
  const [days, setDays] = useState(30);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['audit-logs', entityTypeFilter, actionFilter, days],
    queryFn: () => auditLogsApi.list({
      entity_type: entityTypeFilter || undefined,
      action: actionFilter || undefined,
      days,
      limit: 500,
    }),
    enabled: isAdmin,
  });

  const { data: entityTypes = [] } = useQuery({
    queryKey: ['audit-log-entity-types'],
    queryFn: auditLogsApi.entityTypes,
    enabled: isAdmin,
  });

  const actionTypes = Array.from(new Set(logs.map(l => l.action))).sort();

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Admin access required to view audit logs.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Audit Trail</h1>

      <div className="flex flex-wrap gap-4 mb-4">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Entity Type</label>
          <select
            value={entityTypeFilter}
            onChange={e => setEntityTypeFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All</option>
            {entityTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Action</label>
          <select
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All</option>
            {actionTypes.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-500 mb-1">Time Range</label>
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={60}>Last 60 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        <div className="flex items-end">
          <span className="text-sm text-gray-500">{logs.length} entries</span>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No audit log entries found.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entity</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {logs.map((log) => (
                <Fragment key={log.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                    className="cursor-pointer hover:bg-gray-50"
                  >
                    <td className="px-4 py-2.5 text-sm text-gray-700 whitespace-nowrap">
                      {formatTimestamp(log.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 whitespace-nowrap">
                      {log.username || (log.user_id ? log.user_id.substring(0, 8) : '-')}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-800'}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-700">{log.entity_type || '-'}</td>
                    <td className="px-4 py-2.5 text-sm text-gray-500">
                      {log.source || '-'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-400">
                      {expandedId === log.id ? '▲' : '▼'}
                    </td>
                  </tr>
                  {expandedId === log.id && (
                    <tr>
                      <td colSpan={6} className="px-4 py-3 bg-gray-50">
                        <JsonDiff before={log.before_json} after={log.after_json} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
