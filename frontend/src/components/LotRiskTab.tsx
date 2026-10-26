import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Plot from 'react-plotly.js';
import { riskApi, RiskProtocol, RiskRun, RunResultResponse, Scenario } from '../api/risk';
import { vestsApi, VestListItem } from '../api/vests';

const pct = (x?: number | null) =>
  x === null || x === undefined ? '—' : `${(x * 100).toFixed(2)}%`;

const fmt = (n?: number) =>
  n === undefined || n === null ? '?' : Math.abs(n) < 1 ? n.toPrecision(3) : n.toFixed(1);

// linear interpolation of a survival curve at threshold t
const interpSurvival = (t: number, xs: number[], ps: number[]): number | null => {
  if (!xs.length || !ps.length) return null;
  if (t <= xs[0]) return ps[0];
  if (t >= xs[xs.length - 1]) return ps[ps.length - 1];
  for (let i = 1; i < xs.length; i++) {
    if (t <= xs[i]) {
      const f = (t - xs[i - 1]) / (xs[i] - xs[i - 1]);
      return ps[i - 1] + f * (ps[i] - ps[i - 1]);
    }
  }
  return ps[ps.length - 1];
};

// P(at least one event in a lot of n units, each with probability p)
const atLeastOne = (p: number | null, n: number) =>
  p === null ? null : 1 - Math.pow(1 - p, n);

const formatSpread = (v: { family?: string; parameters?: Record<string, unknown>; unit?: string }) => {
  const p = v.parameters || {};
  const unit = v.unit ? ` ${v.unit}` : '';
  switch (v.family) {
    case 'constant':
      return `${fmt(p.value as number)}${unit}`;
    case 'uniform':
      return `${fmt(p.a as number)} – ${fmt(p.b as number)}${unit}`;
    case 'triangular':
      return `${fmt(p.c as number)} [${fmt(p.a as number)}–${fmt(p.b as number)}]${unit}`;
    case 'truncated_normal':
    case 'normal':
      return `${fmt((p.mu ?? p.mean) as number)} ± ${fmt(p.sigma as number)}${unit}`;
    case 'empirical_bootstrap':
      return `${(p.values as number[])?.length ?? 0} samples`;
    default:
      return '—';
  }
};

const humanize = (s?: string) => {
  if (!s) return '';
  const words = s.replace(/_/g, ' ').split(' ').filter(Boolean);
  return words
    .map((w) => (/^[a-z0-9]+$/.test(w) ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
};

const provenanceBadge = (p?: string) => {
  const colors: Record<string, string> = {
    measured: 'bg-green-100 text-green-800',
    report_derived: 'bg-blue-100 text-blue-800',
    spec_window: 'bg-indigo-100 text-indigo-800',
    protocol_spec: 'bg-indigo-100 text-indigo-800',
    assumed: 'bg-amber-100 text-amber-800',
    catalog_nominal: 'bg-gray-100 text-gray-700',
  };
  const label = p || 'unknown';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[label] || 'bg-gray-100 text-gray-700'}`}>
      {label}
    </span>
  );
};

export default function LotRiskTab() {
  const [subTab, setSubTab] = useState<'probability' | 'methodology'>('probability');

  // form state
  const [vestId, setVestId] = useState('');
  const [scenarioName, setScenarioName] = useState('');
  const [bfdLimit, setBfdLimit] = useState(44);
  const [draws, setDraws] = useState(1000);
  const [seed, setSeed] = useState('');
  const [modelVersion, setModelVersion] = useState<string>('');
  const [populationMode, setPopulationMode] = useState<'accepted_units' | 'pre_qc'>('accepted_units');
  const [protocolId, setProtocolId] = useState('');
  const [level, setLevel] = useState('');
  const [ammoId, setAmmoId] = useState('');

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [run, setRun] = useState<RiskRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // worst-case explorer state
  const [wcThreshold, setWcThreshold] = useState(44);
  const [wcLotSize, setWcLotSize] = useState(1000);
  const [wcScope, setWcScope] = useState<string>('vest'); // 'vest' or a shot number as string

  const { data: vests } = useQuery<VestListItem[]>({
    queryKey: ['vests', 'all'],
    queryFn: () => vestsApi.list({ limit: 500 }),
  });

  const { data: models } = useQuery({
    queryKey: ['risk', 'models'],
    queryFn: () => riskApi.models(),
  });

  const { data: protocols } = useQuery<RiskProtocol[]>({
    queryKey: ['risk', 'protocols'],
    queryFn: () => riskApi.protocols(),
  });

  const selectedProtocol = protocols?.find((p) => p.id === protocolId);
  const levels = selectedProtocol?.levels ?? [];
  const selectedLevel = levels.find((l) => l.level_name === level);
  const ammoOptions = selectedLevel?.ammunition_config ?? [];
  const selectedAmmo = ammoOptions.find((a) => a.ammunition_id === ammoId);

  const sortedVests = useMemo(
    () => [...(vests ?? [])].sort((a, b) => a.vest_code.localeCompare(b.vest_code)),
    [vests],
  );

  const { data: distPreview } = useQuery({
    queryKey: ['risk', 'dist', vestId],
    queryFn: () => riskApi.distributionPreview(vestId),
    enabled: !!vestId,
  });

  // poll run status while queued/running
  const { data: runResult } = useQuery<RunResultResponse>({
    queryKey: ['risk', 'run', run?.id],
    queryFn: () => riskApi.getRunResult(run!.id),
    enabled: !!run,
    refetchInterval: run?.status === 'queued' || run?.status === 'running' ? 2000 : false,
  });

  useEffect(() => {
    if (runResult?.run) setRun(runResult.run);
  }, [runResult?.run?.status]);

  const result = runResult?.result;
  const readiness = runResult?.readiness;

  const histData = useMemo(() => {
    if (!result) return [];
    const { bin_edges, counts } = result.histogram;
    const centers = bin_edges.slice(0, -1).map((e, i) => (e + bin_edges[i + 1]) / 2);
    return [
      { x: centers, y: counts, type: 'bar' as const, marker: { color: '#6366f1' }, name: 'BFD' },
    ];
  }, [result]);

  // ---- worst-case answers -------------------------------------------------
  // p for the selected scope at the selected threshold
  const selectedShotCurve = useMemo(() => {
    if (wcScope === 'vest') return null;
    return result?.per_shot_survival?.find(
      (s) => String(s.shot_number) === wcScope,
    ) ?? null;
  }, [result, wcScope]);

  const wcP = useMemo(() => {
    if (wcScope === 'vest') {
      const u = result?.unit_max_survival;
      return u ? interpSurvival(wcThreshold, u.bfd_mm, u.p_exceed) : null;
    }
    const s = selectedShotCurve;
    return s ? interpSurvival(wcThreshold, s.bfd_mm, s.p_exceed) : null;
  }, [result, wcScope, wcThreshold, selectedShotCurve]);

  const wcExpected = wcP === null ? null : wcP * wcLotSize;
  const wcAtLeastOne = atLeastOne(wcP, wcLotSize);

  const perfVestP = result?.perforation?.vest_rate?.estimate ?? null;
  const perfExpected = perfVestP === null ? null : perfVestP * wcLotSize;
  const perfAtLeastOne = atLeastOne(perfVestP, wcLotSize);

  // survival curve for the plot (vest-level or selected shot)
  const wcCurve = wcScope === 'vest' ? result?.unit_max_survival : selectedShotCurve;

  const createAndRun = async () => {
    if (!vestId) {
      setError('Select a design vest first.');
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const vestCode = sortedVests.find((v) => v.id === vestId)?.vest_code || 'vest';
      const sc = await riskApi.createScenario({
        name: scenarioName || `Eval ${vestCode} ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`,
        design_id: vestId,
        model_version: modelVersion || undefined,
        protocol_id: protocolId || undefined,
        level: level || undefined,
        ammunition_id: ammoId || undefined,
        population_mode: populationMode,
        outcome_rule_json: { bfd_threshold_mm: bfdLimit },
      });
      setScenario(sc);
      const r = await riskApi.createRun({
        scenario_id: sc.id,
        requested_draws: draws,
        seed: seed ? parseInt(seed, 10) : undefined,
      });
      setRun(r);
    } catch (e: any) {
      setError(e?.message || 'Failed to create scenario/run');
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!run) return;
    const updated = await riskApi.cancelRun(run.id);
    setRun(updated);
  };

  const running = run && (run.status === 'queued' || run.status === 'running');
  const progress = run ? run.completed_independent_draws / run.requested_draws : 0;

  return (
    <div className="space-y-6">
      {/* sub-tabs */}
      <div className="flex space-x-4 border-b border-gray-200">
        {(['probability', 'methodology'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setSubTab(t)}
            className={`py-2 px-1 text-sm font-medium border-b-2 -mb-px ${
              subTab === t
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t === 'probability' ? 'Probability' : 'Methodology & Trace'}
          </button>
        ))}
      </div>

      {subTab === 'probability' && (
        <div className="grid grid-cols-3 gap-6">
          {/* left: setup */}
          <div className="bg-white rounded-lg shadow p-5 space-y-4">
            <h3 className="text-sm font-semibold text-gray-900">Simulation Setup</h3>
            <p className="text-[11px] text-gray-500">
              Monte Carlo over {draws.toLocaleString()} virtual vests: material
              tolerances and protocol velocity windows are sampled per unit, every
              shot is predicted by the model, then corrected for the model's
              measured bias and spread.
            </p>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Design vest</label>
              <select
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={vestId}
                onChange={(e) => {
                  const id = e.target.value;
                  setVestId(id);
                  // autofill protocol/level from the vest's assigned threat_level
                  // (stored as "<protocol name> - <level>", e.g. "ANMaC 2023 - RB3")
                  const tl = sortedVests.find((x) => x.id === id)?.threat_level;
                  if (!tl || !protocols) return;
                  const combos = protocols.flatMap((p) =>
                    (p.levels ?? []).map((l) => ({ p, l })),
                  );
                  const m =
                    combos.find(({ p, l }) => tl === `${p.name} - ${l.level_name}`) ??
                    combos.find(({ p, l }) => tl === `${p.name}-${l.level_name}`) ??
                    combos.find(({ l }) => tl === l.level_name);
                  if (m) {
                    setProtocolId(m.p.id);
                    setLevel(m.l.level_name);
                    setAmmoId('');
                  }
                }}
              >
                <option value="">Select vest…</option>
                {sortedVests.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.vest_code}
                  </option>
                ))}
              </select>
            </div>

            {/* threat targeting: protocol -> level -> ammo */}
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Protocol</label>
                <select
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={protocolId}
                  onChange={(e) => { setProtocolId(e.target.value); setLevel(''); setAmmoId(''); }}
                >
                  <option value="">None</option>
                  {protocols?.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Level</label>
                <select
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={level}
                  onChange={(e) => { setLevel(e.target.value); setAmmoId(''); }}
                  disabled={!protocolId}
                >
                  <option value="">—</option>
                  {levels.map((l) => (
                    <option key={l.level_name} value={l.level_name}>{l.level_name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Ammunition</label>
                <select
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={ammoId}
                  onChange={(e) => setAmmoId(e.target.value)}
                  disabled={!level}
                >
                  <option value="">All ({ammoOptions.length})</option>
                  {ammoOptions.map((a) => (
                    <option key={a.ammunition_id} value={a.ammunition_id}>
                      {a.ammunition_name || a.caliber || a.ammunition_id.slice(0, 8)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {(selectedAmmo || (level && ammoOptions.length > 0)) && (
              <p className="text-[11px] text-gray-500">
                {selectedAmmo
                  ? `${selectedAmmo.ammunition_name || 'ammo'} · ${selectedAmmo.reference_velocity_m_s ?? '?'} ± ${selectedAmmo.velocity_window_m_s ?? '?'} m/s · ${selectedAmmo.shots_per_panel ?? '?'} shots`
                  : ammoOptions.map((a) => `${a.ammunition_name || 'ammo'} ${a.reference_velocity_m_s ?? '?'}±${a.velocity_window_m_s ?? '?'} m/s ×${a.shots_per_panel ?? '?'}`).join(' · ')}
              </p>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Scenario name</label>
              <input
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                placeholder="e.g. MDS III NIJ IIIA eval"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">BFD limit (mm)</label>
                <input
                  type="number"
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={bfdLimit}
                  onChange={(e) => setBfdLimit(parseFloat(e.target.value))}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Draws (vests)</label>
                <input
                  type="number"
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={draws}
                  min={10}
                  max={200000}
                  onChange={(e) => setDraws(parseInt(e.target.value, 10))}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Model version</label>
                <select
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={modelVersion}
                  onChange={(e) => setModelVersion(e.target.value)}
                >
                  <option value="">active ({models?.versions?.find((m) => m.version === models?.active_version)?.model_name || models?.active_version || '…'})</option>
                  {models?.versions?.map((m) => (
                    <option key={m.version} value={m.version}>
                      {m.model_name ? `${m.model_name} (${m.version})` : m.version}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Seed (optional)</label>
                <input
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value)}
                  placeholder="auto"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Population mode</label>
              <select
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={populationMode}
                onChange={(e) => setPopulationMode(e.target.value as any)}
              >
                <option value="accepted_units">Accepted units</option>
                <option value="pre_qc">Pre-QC (all units)</option>
              </select>
              <p className="text-[11px] text-gray-500 mt-1">
                {populationMode === 'pre_qc'
                  ? 'Draws from full supplier tolerance windows — units outside spec are rejected and counted (worst-case incoming material).'
                  : 'Draws within acceptance windows only — represents vests that pass incoming QC.'}
              </p>
            </div>

            {error && <p className="text-xs text-red-600">{error}</p>}

            <div className="flex space-x-2">
              <button
                onClick={createAndRun}
                disabled={busy || !!running}
                className="flex-1 bg-indigo-600 text-white text-sm font-medium rounded py-2 disabled:opacity-50"
              >
                {busy ? 'Starting…' : running ? 'Running…' : 'Create scenario & run'}
              </button>
              {running && (
                <button
                  onClick={cancel}
                  className="px-3 border border-gray-300 text-sm rounded text-gray-700"
                >
                  Cancel
                </button>
              )}
            </div>

            {run && (
              <div>
                <div className="flex justify-between text-xs text-gray-600 mb-1">
                  <span>
                    {run.status} — {run.completed_independent_draws}/{run.requested_draws} units
                  </span>
                  <span>{Math.round(progress * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded h-2">
                  <div
                    className="bg-indigo-600 h-2 rounded"
                    style={{ width: `${Math.min(100, progress * 100)}%` }}
                  />
                </div>
                {run.status === 'failed' && (
                  <p className="text-xs text-red-600 mt-1">{run.failure_reason}</p>
                )}
              </div>
            )}
          </div>

          {/* right: results */}
          <div className="col-span-2 space-y-4">
            {readiness && (
              <div className="bg-white rounded-lg shadow p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-2">Readiness</h3>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(readiness).filter(([k]) => k !== 'explanations').map(([k, v]) => (
                    <span
                      key={k}
                      className={`px-2.5 py-1 rounded text-xs font-medium ${
                        v === 'blocked'
                          ? 'bg-red-100 text-red-800'
                          : v === 'exploratory'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-green-100 text-green-800'
                      }`}
                    >
                      {k.replace(/_/g, ' ')}: {v as string}
                    </span>
                  ))}
                </div>
                {readiness.explanations && (
                  <ul className="mt-2 text-xs text-gray-500 list-disc pl-4 space-y-0.5">
                    {Object.entries(readiness.explanations).map(([k, v]) => (
                      <li key={k}><b>{k.replace(/_/g, ' ')}</b>: {v}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {result ? (
              <>
                {/* ---- worst-case answers ---- */}
                <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500">
                  <h3 className="text-sm font-semibold text-gray-900 mb-1">
                    Worst-Case Answers
                  </h3>
                  <p className="text-[11px] text-gray-500 mb-3">
                    "We measured BFD of X mm on shot k — how unusual is that?"
                    Slide the threshold, pick a scope, get the lot-level answer.
                  </p>

                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Scope
                      </label>
                      <select
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        value={wcScope}
                        onChange={(e) => setWcScope(e.target.value)}
                      >
                        <option value="vest">Any shot on the vest</option>
                        {result.per_shot_survival?.map((s) => (
                          <option key={s.shot_number} value={String(s.shot_number)}>
                            Shot {s.shot_number} only
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        BFD threshold: <b>{wcThreshold.toFixed(0)} mm</b>
                      </label>
                      <input
                        type="range"
                        min={0}
                        max={Math.ceil(Math.max(...(result.survival?.bfd_mm ?? [result.bfd_limit_mm * 2])))}
                        step={0.5}
                        value={wcThreshold}
                        onChange={(e) => setWcThreshold(parseFloat(e.target.value))}
                        className="w-full"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Lot size (vests)
                      </label>
                      <input
                        type="number"
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        value={wcLotSize}
                        min={1}
                        onChange={(e) => setWcLotSize(Math.max(1, parseInt(e.target.value, 10) || 1))}
                      />
                    </div>
                  </div>

                  {/* BFD answer */}
                  <div className="bg-indigo-50 rounded p-3 mb-3">
                    {wcP !== null ? (
                      <>
                        <p className="text-sm text-gray-900">
                          ≈<b>{wcExpected!.toFixed(1)}</b> vests in {wcLotSize.toLocaleString()}{' '}
                          ({pct(wcP)} of vests) are expected to record a BFD ≥{' '}
                          <b>{wcThreshold} mm</b>{' '}
                          {wcScope === 'vest'
                            ? 'on at least one shot'
                            : `on shot ${wcScope}`}
                          .
                        </p>
                        <p className="text-xs text-gray-600 mt-1">
                          There is a <b>{pct(wcAtLeastOne)}</b> chance that at
                          least one vest in a lot of {wcLotSize.toLocaleString()}{' '}
                          records BFD ≥ {wcThreshold} mm
                          {wcScope === 'vest' ? ' on any shot' : ` on shot ${wcScope}`}.
                          {wcExpected !== null && wcExpected < 1 && wcLotSize >= 100 && (
                            <span className="ml-1 text-green-700 font-medium">
                              — less than 1 expected in the lot; that reading would be unusual.
                            </span>
                          )}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-gray-500">
                        {result.partial
                          ? 'Survival curves are available once the run completes.'
                          : 'No survival data for this scope — the model may have classified every shot as a perforation.'}
                      </p>
                    )}
                  </div>

                  {/* perforation answer */}
                  <div className="bg-amber-50 border border-amber-200 rounded p-3">
                    <p className="text-xs font-semibold text-amber-800 mb-1">
                      Penetration {result.perforation?.uncalibrated !== false && (
                        <span className="font-normal">— exploratory (classifier has too few real perforation examples to calibrate)</span>
                      )}
                    </p>
                    {!result.perforation ? (
                      <p className="text-sm text-gray-500">
                        No perforation model on this version — the classifier was
                        skipped because there are too few real measured failure
                        outcomes. Only BFD statistics are shown for this run.
                      </p>
                    ) : perfVestP !== null ? (
                      <p className="text-sm text-gray-900">
                        ≈<b>{perfExpected!.toFixed(1)}</b> vests in {wcLotSize.toLocaleString()}{' '}
                        are expected to experience a penetration on at least one
                        shot — a <b>{pct(perfAtLeastOne)}</b> chance of at least
                        one penetration in the lot.
                        <span className="text-xs text-gray-500 ml-1">
                          ({result.n_perforated_shots} penetrations seen in{' '}
                          {result.n_predicted_shots.toLocaleString()} simulated shots;
                          95% CI {pct(result.perforation?.vest_rate?.ci95_low)} –{' '}
                          {pct(result.perforation?.vest_rate?.ci95_high)} per vest)
                        </span>
                      </p>
                    ) : (
                      <p className="text-sm text-gray-500">
                        No penetrations in this run — a penetration event would be
                        rarer than ~1 in {result.n_units.toLocaleString()} vests
                        under these conditions.
                      </p>
                    )}
                  </div>
                </div>

                {/* survival plot */}
                {wcCurve && (
                  <div className="bg-white rounded-lg shadow p-4">
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">
                      Exceedance probability vs BFD threshold —{' '}
                      {wcScope === 'vest' ? 'worst shot per vest' : `shot ${wcScope}`}
                      {result.partial && (
                        <span className="ml-2 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-medium align-middle">live</span>
                      )}
                    </h3>
                    <Plot
                      data={[
                        {
                          x: wcCurve.bfd_mm,
                          y: wcCurve.p_exceed.map((p) => p * 100),
                          type: 'scatter' as const,
                          mode: 'lines' as const,
                          line: { color: '#6366f1', width: 2 },
                          name: 'P(BFD ≥ x)',
                        },
                        ...(wcScope !== 'vest' && result.unit_max_survival
                          ? [{
                              x: result.unit_max_survival.bfd_mm,
                              y: result.unit_max_survival.p_exceed.map((p: number) => p * 100),
                              type: 'scatter' as const,
                              mode: 'lines' as const,
                              line: { color: '#94a3b8', width: 1.5, dash: 'dot' as const },
                              name: 'Any shot on vest',
                            }]
                          : []),
                      ]}
                      layout={{
                        height: 280,
                        margin: { t: 10, b: 45, l: 55, r: 10 },
                        xaxis: { title: 'BFD threshold (mm)' },
                        yaxis: { title: '% of vests exceeding', ticksuffix: '%' },
                        showlegend: wcScope !== 'vest',
                        shapes: [
                          {
                            type: 'line', x0: wcThreshold, x1: wcThreshold,
                            y0: 0, y1: 1, yref: 'paper',
                            line: { color: '#dc2626', dash: 'dash', width: 2 },
                          },
                          {
                            type: 'line', x0: result.bfd_limit_mm, x1: result.bfd_limit_mm,
                            y0: 0, y1: 1, yref: 'paper',
                            line: { color: '#f59e0b', dash: 'dot', width: 1.5 },
                          },
                        ],
                        annotations: [{
                          x: result.bfd_limit_mm, y: 1, yref: 'paper',
                          text: `limit ${result.bfd_limit_mm}mm`,
                          showarrow: false, font: { size: 10, color: '#f59e0b' },
                          xanchor: 'left',
                        }],
                      }}
                      config={{ displayModeBar: false, responsive: true }}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}

                {/* histogram */}
                <div className="bg-white rounded-lg shadow p-4">
                  <div className="flex justify-between items-baseline mb-2">
                    <h3 className="text-sm font-semibold text-gray-900">
                      Predicted BFD distribution — {result.n_units} vests × {result.n_shots_per_unit} shot(s)
                      {result.partial && (
                        <span className="ml-2 px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 text-[10px] font-medium align-middle">
                          live
                        </span>
                      )}
                    </h3>
                    {scenario && (
                      <span className="text-xs text-gray-400">
                        {scenario.name} · {scenario.model_version}
                      </span>
                    )}
                  </div>
                  <Plot
                    data={histData}
                    layout={{
                      height: 240,
                      margin: { t: 10, b: 40, l: 45, r: 10 },
                      xaxis: { title: 'Predicted BFD (mm)' },
                      yaxis: { title: 'Shots' },
                      shapes: [{
                        type: 'line', x0: result.bfd_limit_mm, x1: result.bfd_limit_mm,
                        y0: 0, y1: 1, yref: 'paper',
                        line: { color: '#dc2626', dash: 'dash', width: 2 },
                      }],
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: '100%' }}
                  />
                </div>

                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-indigo-50 border border-indigo-200 rounded-lg shadow p-4">
                    <p className="text-xs text-indigo-600 font-medium">Combined failure rate</p>
                    <p className="text-xl font-bold text-gray-900">
                      {pct(result.combined_failure_rate?.estimate)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {result.combined_events_per_1000_shots?.toFixed(1) ?? '—'} events / 1000 shots
                    </p>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4">
                    <p className="text-xs text-gray-500">Vest-level exceedance</p>
                    <p className="text-xl font-bold text-gray-900">
                      {pct(result.protocol_exceedance?.estimate)}
                    </p>
                    <p className="text-xs text-gray-500">
                      of vests exceed {result.bfd_limit_mm}mm on ≥1 shot · CI [{pct(result.protocol_exceedance?.ci95_low)} – {pct(result.protocol_exceedance?.ci95_high)}]
                    </p>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4">
                    <p className="text-xs text-gray-500">Expected events / 1000 shots</p>
                    <p className="text-xl font-bold text-gray-900">
                      {result.expected_events_per_1000_shots?.toFixed(1) ?? '—'}
                    </p>
                    {(result.n_perforated_shots ?? 0) > 0 && (
                      <p className="text-xs text-gray-500">
                        {result.n_perforated_shots} perforated shots excluded
                      </p>
                    )}
                  </div>
                  <div className="bg-white rounded-lg shadow p-4">
                    <p className="text-xs text-gray-500">
                      Vest penetration rate {result.perforation?.uncalibrated && <span className="text-amber-600">(uncalibrated)</span>}
                    </p>
                    <p className="text-xl font-bold text-gray-900">
                      {result.perforation?.vest_rate ? pct(result.perforation.vest_rate.estimate) : '—'}
                    </p>
                    {result.perforation?.vests_with_perforation_per_1000 !== undefined && (
                      <p className="text-xs text-gray-500">
                        ≈{result.perforation.vests_with_perforation_per_1000?.toFixed(1) ?? '—'} vests / 1000
                      </p>
                    )}
                  </div>
                </div>

                {result.per_shot_exceedance?.length > 1 && (
                  <div className="bg-white rounded-lg shadow p-4">
                    <h4 className="text-xs font-semibold text-gray-700 mb-2">
                      Per-shot exceedance at {result.bfd_limit_mm}mm
                    </h4>
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-left text-gray-500">
                          <th className="py-1">Shot</th><th>Estimate</th><th>95% CI</th>
                          {result.perforation && <th>Perf. score</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {result.per_shot_exceedance.map((s, i) => (
                          <tr key={s.shot_number} className="border-t">
                            <td className="py-1">#{s.shot_number}</td>
                            <td>{pct(s.estimate)}</td>
                            <td>[{pct(s.ci95_low)} – {pct(s.ci95_high)}]</td>
                            {result.perforation && (
                              <td>{pct(result.perforation.per_shot_mean[i])}</td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {(result.warnings?.length ?? 0) > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                    <h4 className="text-xs font-semibold text-amber-800 mb-1">Warnings</h4>
                    <ul className="text-xs text-amber-800 list-disc pl-4 space-y-0.5">
                      {(result.warnings ?? []).map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400 text-sm">
                {run ? 'Waiting for result…' : 'Configure a design vest and run a simulation.'}
              </div>
            )}
          </div>
        </div>
      )}

      {subTab === 'methodology' && (
        <div className="space-y-4">
          {distPreview && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">
                Resolved distributions — design preview
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-1.5">Material</th><th>Property</th><th>Family</th>
                    <th>Value / spread</th><th>Provenance</th><th>Basis</th>
                  </tr>
                </thead>
                <tbody>
                  {distPreview.variables.map((v) => (
                    <tr key={v.variable} className="border-b">
                      <td className="py-1.5 font-medium">{v.material}</td>
                      <td>{humanize(v.property_key)}{v.direction ? ` (${humanize(v.direction)})` : ''}</td>
                      <td>{humanize(v.family) || (v.skipped ? '—' : '')}</td>
                      <td className="font-mono">{formatSpread(v)}</td>
                      <td>{provenanceBadge(v.provenance)}</td>
                      <td className="text-gray-500">{v.basis || v.reason || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {distPreview.warnings.length > 0 && (
                <ul className="mt-3 text-xs text-amber-700 list-disc pl-4">
                  {distPreview.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              )}

              <div className="mt-4 border-t pt-3 grid grid-cols-2 gap-4 text-[11px] text-gray-500">
                <div>
                  <p className="font-semibold text-gray-600 mb-1">Distribution families</p>
                  <ul className="space-y-0.5">
                    <li><b>Triangular</b> — min / most-likely / max; used when only a spec window or an assumed ±5% tolerance exists.</li>
                    <li><b>Truncated Normal</b> — Gaussian around a mean, cut at physical bounds (e.g. no negative values).</li>
                    <li><b>Uniform</b> — every value between the bounds equally likely (velocity windows).</li>
                    <li><b>Empirical Bootstrap</b> — resamples real recorded measurements directly.</li>
                    <li><b>Constant</b> — single catalog nominal, no spread on record.</li>
                  </ul>
                </div>
                <div>
                  <p className="font-semibold text-gray-600 mb-1">Provenance</p>
                  <ul className="space-y-0.5">
                    <li><b>measured</b> — drawn from actual test measurements.</li>
                    <li><b>report_derived</b> — statistics extracted from test reports / spec sheets.</li>
                    <li><b>spec_window</b> — supplier tolerance or spec limits.</li>
                    <li><b>assumed</b> — no tolerance on record; ±5% triangular fallback (verify).</li>
                    <li><b>catalog_nominal</b> — catalog value only, no spread.</li>
                    <li><b>protocol_spec</b> — velocity window from the selected protocol.</li>
                  </ul>
                </div>
              </div>
            </div>
          )}

          {result?.calculation_trace && (
            <div className="bg-white rounded-lg shadow p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">
                Calculation trace — run {run?.id?.slice(0, 8)}
              </h3>
              <dl className="grid grid-cols-4 gap-2 text-xs">
                <dt className="text-gray-500">Model version</dt>
                <dd className="font-mono">{result.calculation_trace.model_version}</dd>
                <dt className="text-gray-500">Contract</dt>
                <dd className="font-mono">{result.calculation_trace.feature_contract_version}</dd>
                <dt className="text-gray-500">Seed</dt>
                <dd className="font-mono">{result.calculation_trace.seed}</dd>
                <dt className="text-gray-500">Population</dt>
                <dd>{result.calculation_trace.population_mode}</dd>
                <dt className="text-gray-500 col-span-1">Composition</dt>
                <dd className="col-span-3 font-mono">{result.calculation_trace.composition}</dd>
              </dl>
              {result.calculation_trace.notes && (
                <ul className="mt-3 text-xs text-gray-500 list-disc pl-4 space-y-0.5">
                  {result.calculation_trace.notes.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
              )}
            </div>
          )}

          {!distPreview && !result && (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400 text-sm">
              Select a vest on the Probability tab to preview resolved distributions.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
