import { useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pliegoApi, PliegoDocument, PliegoRequirements, PliegoVestMatch } from '../api/pliego';
import { exportPliegoReportPdf } from '../utils/pliegoPdfExport';

export function PliegoMatcher() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ['pliego-documents'],
    queryFn: pliegoApi.list,
  });

  const { data: selectedDoc, isLoading: docLoading } = useQuery({
    queryKey: ['pliego-document', selectedDocId],
    queryFn: () => pliegoApi.get(selectedDocId!),
    enabled: !!selectedDocId,
  });

  const uploadMutation = useMutation({
    mutationFn: pliegoApi.upload,
    onSuccess: (doc) => {
      queryClient.invalidateQueries({ queryKey: ['pliego-documents'] });
      setSelectedDocId(doc.id);
      setUploadError(null);
    },
    onError: (error: Error) => {
      setUploadError(error.message || 'Upload failed');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: pliegoApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pliego-documents'] });
      setSelectedDocId(null);
    },
  });

  const retryMutation = useMutation({
    mutationFn: pliegoApi.retry,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pliego-documents'] });
      queryClient.invalidateQueries({ queryKey: ['pliego-document', selectedDocId] });
    },
  });

  const handleFileSelect = useCallback((file: File) => {
    setUploadError(null);
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx', 'doc', 'txt'].includes(ext || '')) {
      setUploadError('Unsupported file type. Allowed: PDF, DOCX, TXT');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setUploadError('File too large. Max size: 20MB');
      return;
    }
    uploadMutation.mutate(file);
  }, [uploadMutation]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, [handleFileSelect]);

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileSelect(file);
  };

  const handleDownload = async (id: string, name: string) => {
    try {
      const blob = await pliegoApi.download(id);
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // noop
    }
  };

  const activeDoc = selectedDoc || documents?.find((d) => d.id === selectedDocId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">RFP Analysis</h1>
        <p className="mt-1 text-sm text-gray-600">
          Upload a bid/contract document (RFP/tender) and AI will extract the vest
          requirements, then match them against officially certified vests in your database.
        </p>
      </div>

      {/* Upload Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          onChange={handleFileInput}
          className="hidden"
        />
        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center gap-3">
            <svg className="animate-spin h-8 w-8 text-indigo-600" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-sm text-gray-600">Analyzing document with AI...</p>
            <p className="text-xs text-gray-400">Extracting requirements and matching vests</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <svg className="h-10 w-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm font-medium text-gray-700">
              Drop your RFP document here, or click to browse
            </p>
            <p className="text-xs text-gray-400">PDF, DOCX, or TXT — up to 20MB</p>
          </div>
        )}
      </div>

      {uploadError && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-800">{uploadError}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Document History Sidebar */}
        <div className="lg:col-span-1">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Previous Analyses</h2>
          {docsLoading ? (
            <p className="text-sm text-gray-400">Loading...</p>
          ) : !documents || documents.length === 0 ? (
            <p className="text-sm text-gray-400">No documents uploaded yet.</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setSelectedDocId(doc.id)}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedDocId === doc.id
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-800 truncate">
                      {doc.original_name || doc.filename}
                    </span>
                    <StatusBadge status={doc.status} />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Main Content Area */}
        <div className="lg:col-span-2">
          {docLoading ? (
            <div className="flex items-center justify-center h-64">
              <svg className="animate-spin h-8 w-8 text-indigo-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : !activeDoc ? (
            <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
              Upload a document or select a previous analysis to view results.
            </div>
          ) : activeDoc.status === 'failed' ? (
            <div className="rounded-lg bg-red-50 border border-red-200 p-6">
              <h3 className="text-sm font-semibold text-red-800">Analysis Failed</h3>
              <p className="mt-2 text-sm text-red-700">{activeDoc.error_message}</p>
              <p className="mt-2 text-xs text-red-500">
                Ensure GEMINI_API_KEY is set in the backend environment.
              </p>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => retryMutation.mutate(activeDoc.id)}
                  disabled={retryMutation.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:opacity-50"
                >
                  {retryMutation.isPending ? 'Retrying...' : 'Retry Analysis'}
                </button>
                <button
                  onClick={() => deleteMutation.mutate(activeDoc.id)}
                  className="px-4 py-2 text-sm font-medium text-red-600 border border-red-300 rounded hover:bg-red-50"
                >
                  Delete
                </button>
              </div>
            </div>
          ) : activeDoc.status === 'pending' ? (
            <div className="flex items-center justify-center h-64">
              <p className="text-sm text-gray-500">Analysis in progress...</p>
            </div>
          ) : (
            <AnalysisResults doc={activeDoc} onDelete={() => deleteMutation.mutate(activeDoc.id)} onDownload={() => handleDownload(activeDoc.id, activeDoc.original_name || activeDoc.filename)} />
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    analyzed: 'bg-green-100 text-green-800',
    pending: 'bg-yellow-100 text-yellow-800',
    failed: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${styles[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

function AnalysisResults({ doc, onDelete, onDownload }: { doc: PliegoDocument; onDelete: () => void; onDownload: () => void }) {
  const reqs = doc.extracted_requirements;
  const results = doc.match_results;
  const [exportingPdf, setExportingPdf] = useState(false);

  const handleExportPdf = async (lang: 'en' | 'es') => {
    setExportingPdf(true);
    try {
      await exportPliegoReportPdf(doc, lang);
    } finally {
      setExportingPdf(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Document Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">{doc.original_name || doc.filename}</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Analyzed on {new Date(doc.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => handleExportPdf('en')}
            disabled={exportingPdf}
            className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            {exportingPdf ? 'Exporting...' : 'Download Report (EN)'}
          </button>
          <button
            onClick={() => handleExportPdf('es')}
            disabled={exportingPdf}
            className="px-3 py-1.5 text-xs font-medium text-white bg-indigo-600 rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            {exportingPdf ? 'Exporting...' : 'Download Report (ES)'}
          </button>
          <button
            onClick={onDownload}
            className="px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
          >
            Download Original File
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-300 rounded hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Extracted Requirements */}
      {reqs && <RequirementsCard reqs={reqs} />}

      {/* Summary */}
      {results && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900">{results.summary.total_certified_vests}</p>
              <p className="text-xs text-gray-500">Certified Vests</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-indigo-600">{results.summary.total_matched}</p>
              <p className="text-xs text-gray-500">Matched</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">{results.summary.top_score.toFixed(0)}%</p>
              <p className="text-xs text-gray-500">Top Match Score</p>
            </div>
          </div>
        </div>
      )}

      {/* Global Gaps */}
      {results?.gaps && results.gaps.length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-4">
          <h3 className="text-sm font-semibold text-amber-800 flex items-center gap-2">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Coverage Gaps
          </h3>
          <ul className="mt-2 space-y-1">
            {results.gaps.map((gap, i) => (
              <li key={i} className="text-sm text-amber-700">• {gap}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Vest Recommendations */}
      {results?.recommendations && results.recommendations.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">
            Recommended Vests ({results.recommendations.length})
          </h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {results.recommendations.map((vest, i) => (
              <VestMatchCard key={vest.vest_id} vest={vest} rank={i + 1} />
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-8 text-center">
          <p className="text-sm text-gray-500">
            No certified vests matched the extracted requirements.
          </p>
        </div>
      )}
    </div>
  );
}

function RequirementsCard({ reqs }: { reqs: PliegoRequirements }) {
  const entries: Array<{ label: string; value: string }> = [];

  if (reqs.raw_summary) entries.push({ label: 'Summary', value: reqs.raw_summary });
  if (reqs.threat_level) entries.push({ label: 'Threat Level', value: reqs.threat_level });
  if (reqs.vest_type) entries.push({ label: 'Vest Type', value: reqs.vest_type });
  if (reqs.protection_class) entries.push({ label: 'Protection Class', value: reqs.protection_class });
  if (reqs.max_weight_g) entries.push({ label: 'Max Weight', value: `${reqs.max_weight_g}g` });
  if (reqs.required_sizes?.length) entries.push({ label: 'Required Sizes', value: reqs.required_sizes.join(', ') });
  if (reqs.ammunition_calibers?.length) entries.push({ label: 'Ammunition', value: reqs.ammunition_calibers.join(', ') });
  if (reqs.trauma_homologation?.backface_max_mm) entries.push({ label: 'Max Backface', value: `${reqs.trauma_homologation.backface_max_mm}mm` });
  if (reqs.trauma_homologation?.ammunition) entries.push({ label: 'Trauma Ammo', value: reqs.trauma_homologation.ammunition });
  if (reqs.flexibility_required !== null && reqs.flexibility_required !== undefined) entries.push({ label: 'Flexibility', value: reqs.flexibility_required ? 'Required' : 'Not required' });
  if (reqs.panel_sewn_required !== null && reqs.panel_sewn_required !== undefined) entries.push({ label: 'Panel Sewn', value: reqs.panel_sewn_required ? 'Required' : 'Not required' });
  if (reqs.is_female_required !== null && reqs.is_female_required !== undefined) entries.push({ label: 'Female Fit', value: reqs.is_female_required ? 'Required' : 'Not required' });
  if (reqs.max_thickness_mm) entries.push({ label: 'Max Thickness', value: `${reqs.max_thickness_mm}mm` });
  if (reqs.stitch_pattern) entries.push({ label: 'Stitch Pattern', value: reqs.stitch_pattern });
  if (reqs.additional_notes) entries.push({ label: 'Notes', value: reqs.additional_notes });

  if (entries.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Extracted Requirements</h3>
        <p className="text-sm text-gray-400">No specific requirements were extracted from the document.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Extracted Requirements</h3>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        {entries.map((entry, i) => (
          <div key={i} className="flex flex-col">
            <span className="text-xs font-medium text-gray-500">{entry.label}</span>
            <span className="text-sm text-gray-800">{entry.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VestMatchCard({ vest, rank }: { vest: PliegoVestMatch; rank: number }) {
  const [expanded, setExpanded] = useState(false);
  const scoreColor = vest.match_score >= 80 ? 'green' : vest.match_score >= 50 ? 'yellow' : 'red';
  const scoreBg: Record<string, string> = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-gray-50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">
              {rank}
            </span>
            <div>
              <Link
                to={`/vests/${vest.vest_id}`}
                onClick={(e) => e.stopPropagation()}
                className="text-sm font-semibold text-indigo-600 hover:underline"
              >
                {vest.vest_code}
              </Link>
              <p className="text-xs text-gray-500">
                {vest.vest_type || '—'} · {vest.threat_level || '—'} · {vest.total_layers || '?'} layers
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-24">
              <div className="flex justify-between text-xs text-gray-500 mb-0.5">
                <span>Match</span>
                <span className="font-semibold">{vest.match_score.toFixed(0)}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${scoreBg[scoreColor]} rounded-full transition-all`}
                  style={{ width: `${vest.match_score}%` }}
                />
              </div>
            </div>
            <svg
              className={`h-4 w-4 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 p-4 space-y-4">
          {/* Match Details */}
          <div>
            <h4 className="text-xs font-semibold text-gray-600 mb-2">Match Details</h4>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              {Object.entries(vest.match_details).map(([key, value]) => (
                <div key={key} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500 capitalize">{key.replace(/_/g, ' ')}:</span>
                  <MatchIndicator value={value} />
                </div>
              ))}
            </div>
          </div>

          {/* Vest Properties */}
          <div>
            <h4 className="text-xs font-semibold text-gray-600 mb-2">Vest Properties</h4>
            <div className="grid grid-cols-3 gap-x-4 gap-y-1.5 text-xs">
              <Prop label="Weight" value={vest.weight_g ? `${vest.weight_g}g` : '—'} />
              <Prop label="Thickness" value={vest.total_thickness_mm ? `${vest.total_thickness_mm}mm` : '—'} />
              <Prop label="Composition" value={vest.composition || '—'} />
              <Prop label="Flexibility" value={vest.flexibility_rating ? 'Yes' : 'No'} />
              <Prop label="Panel Sewn" value={vest.is_panel_sewn ? 'Yes' : vest.is_panel_sewn === false ? 'No' : '—'} />
              <Prop label="Catalog Model" value={vest.is_catalog_model ? 'Yes' : 'No'} />
              <Prop label="Female Fit" value={vest.is_female ? 'Yes' : vest.is_female === false ? 'No' : '—'} />
              <Prop label="Sizes" value={vest.sizes ? Object.keys(vest.sizes).join(', ') : '—'} />
              <Prop label="Protection Class" value={vest.protection_class || '—'} />
            </div>
          </div>

          {/* Certifications */}
          {vest.certifications.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 mb-2">Official Certifications</h4>
              <div className="space-y-1">
                {vest.certifications.map((cert, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-green-50 rounded px-2 py-1">
                    <svg className="h-3.5 w-3.5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-gray-700 font-medium">{cert.name}</span>
                    {cert.lab_name && <span className="text-gray-500">· {cert.lab_name}</span>}
                    {cert.certification_number && <span className="text-gray-500">· #{cert.certification_number}</span>}
                    {cert.test_date && <span className="text-gray-400">· {new Date(cert.test_date).toLocaleDateString()}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per-vest Gaps */}
          {vest.match_gaps.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-600 mb-2">Gaps for this vest</h4>
              <ul className="space-y-1">
                {vest.match_gaps.map((gap, i) => (
                  <li key={i} className="text-xs text-amber-700">• {gap}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MatchIndicator({ value }: { value: string | boolean }) {
  if (typeof value === 'boolean') {
    return value ? (
      <span className="text-green-600 font-medium">✓ Yes</span>
    ) : (
      <span className="text-gray-400">— No</span>
    );
  }
  const str = String(value);
  if (str === 'match' || str === 'compliant') return <span className="text-green-600 font-medium">✓ {str}</span>;
  if (str === 'mismatch' || str === 'exceeds' || str === 'no match') return <span className="text-red-600 font-medium">✕ {str}</span>;
  if (str === 'marginal') return <span className="text-yellow-600 font-medium">⚠ {str}</span>;
  if (str === 'unknown' || str === 'not_specified') return <span className="text-gray-400">{str}</span>;
  return <span className="text-gray-700">{str}</span>;
}

function Prop({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-700">{value}</span>
    </div>
  );
}
