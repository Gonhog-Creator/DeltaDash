import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useVests } from '../hooks/useVests';
import { Vest, vestsApi } from '../api/vests';
import { shotDataApi, ShotData } from '../api/shot_data';
import { testSessionsApi } from '../api/test_session';
import { useMaterials } from '../hooks/useMaterials';
import { Material } from '../api/materials';
import { apiClient } from '../api/client';
import Plot from 'react-plotly.js';

interface AnalyticsPoint {
  velocity: number | null;
  bullet_energy: number | null;
  bfd_mm: number | null;
  caliber: string | null;
  protection_level: string | null;
  test_session_id: string | null;
  test_session_name: string | null;
  vest_number: string | null;
  side: string | null;
  shot_number: string | null;
  angle_degrees: number | null;
  trauma_qualitative: string | null;
  is_official: boolean | null;
}

interface AnalyticsData {
  points: AnalyticsPoint[];
}

interface VestWithStats extends Vest {
  maxBfd1to3: number | null;
  avgBfd1to3: number | null;
  thickness: number | null;
  testSessionIds: string[];
  testSessionNames: string[];
}

export function Comparison() {
  const { data: vests, isLoading: vestsLoading } = useVests();
  const { data: materials } = useMaterials();
  const { data: analyticsData, isLoading: analyticsLoading } = useQuery<AnalyticsData>({
    queryKey: ['analytics', 'velocity-vs-bfd'],
    queryFn: () => apiClient.get<AnalyticsData>('/api/v1/analytics/velocity-vs-bfd'),
  });
  const [searchParams, setSearchParams] = useSearchParams();
  
  const [selectedVest1, setSelectedVest1] = useState<Vest | null>(null);
  const [selectedVest2, setSelectedVest2] = useState<Vest | null>(null);
  const [vest1Stats, setVest1Stats] = useState<VestWithStats | null>(null);
  const [vest2Stats, setVest2Stats] = useState<VestWithStats | null>(null);
  const [vest1Search, setVest1Search] = useState('');
  const [vest2Search, setVest2Search] = useState('');
  const [loadingStats, setLoadingStats] = useState(false);
  const [vest1DropdownOpen, setVest1DropdownOpen] = useState(false);
  const [vest2DropdownOpen, setVest2DropdownOpen] = useState(false);
  const isRestoringRef = useRef(true);

  // Save selected vests to localStorage and URL
  useEffect(() => {
    if (isRestoringRef.current) return;
    
    const newSearchParams = new URLSearchParams();
    
    if (selectedVest1) {
      localStorage.setItem('comparison-vest1', selectedVest1.id);
      newSearchParams.set('vest1', selectedVest1.id);
    } else {
      localStorage.removeItem('comparison-vest1');
    }
    
    if (selectedVest2) {
      localStorage.setItem('comparison-vest2', selectedVest2.id);
      newSearchParams.set('vest2', selectedVest2.id);
    } else {
      localStorage.removeItem('comparison-vest2');
    }
    
    setSearchParams(newSearchParams);
  }, [selectedVest1, selectedVest2]);

  // Restore selected vests from URL parameters first, then localStorage when vests are loaded
  useEffect(() => {
    if (vests && vests.length > 0) {
      isRestoringRef.current = true;
      
      const vest1Id = searchParams.get('vest1') || localStorage.getItem('comparison-vest1');
      const vest2Id = searchParams.get('vest2') || localStorage.getItem('comparison-vest2');
      
      if (vest1Id) {
        const vest1 = vests.find(v => v.id === vest1Id);
        if (vest1) {
          setSelectedVest1(vest1);
          setVest1Search(vest1.vest_code);
        }
      }
      
      if (vest2Id) {
        const vest2 = vests.find(v => v.id === vest2Id);
        if (vest2) {
          setSelectedVest2(vest2);
          setVest2Search(vest2.vest_code);
        }
      }
      
      isRestoringRef.current = false;
    }
  }, [vests, searchParams]);

  // Filter analytics data for selected vests
  const vest1AnalyticsData = vest1Stats ? analyticsData?.points.filter(p => {
    const matchesSessionId = vest1Stats.testSessionIds.includes(p.test_session_id || '');
    const matchesSessionName = vest1Stats.testSessionNames.includes(p.test_session_name || '');
    const matchesParentSessionName = vest1Stats.testSessionNames.includes(p.parent_test_session_name || '');
    const matchesVestNumber = p.vest_number === vest1Stats.vest_code;
    return matchesSessionId || matchesSessionName || matchesParentSessionName || matchesVestNumber;
  }) || [] : [];

  const vest2AnalyticsData = vest2Stats ? analyticsData?.points.filter(p => {
    const matchesSessionId = vest2Stats.testSessionIds.includes(p.test_session_id || '');
    const matchesSessionName = vest2Stats.testSessionNames.includes(p.test_session_name || '');
    const matchesParentSessionName = vest2Stats.testSessionNames.includes(p.parent_test_session_name || '');
    const matchesVestNumber = p.vest_number === vest2Stats.vest_code;
    return matchesSessionId || matchesSessionName || matchesParentSessionName || matchesVestNumber;
  }) || [] : [];

  const filteredVests1 = vests
    ?.filter(v => v.vest_code.toLowerCase().includes(vest1Search.toLowerCase()))
    .sort((a, b) => a.vest_code.localeCompare(b.vest_code)) || [];
  
  const filteredVests2 = vests
    ?.filter(v => v.vest_code.toLowerCase().includes(vest2Search.toLowerCase()))
    .sort((a, b) => a.vest_code.localeCompare(b.vest_code)) || [];

  const calculateVestStats = useCallback(async (vest: Vest): Promise<VestWithStats> => {
    try {
      console.log('Vest:', vest.vest_code, 'total_thickness_mm:', vest.total_thickness_mm);
      
      // Get test sessions for this vest
      const testSessionsResponse = await vestsApi.getTestSessions(vest.id);
      const testSessionIds = testSessionsResponse.test_sessions.map(ts => ts.id);
      const testSessionNames = testSessionsResponse.test_sessions.map(ts => ts.name);

      // Filter analytics data for this vest
      const vestAnalyticsPoints = analyticsData?.points.filter(p => {
        // Match by test_session_id, test_session_name, or parent_test_session_name
        const matchesSessionId = testSessionIds.includes(p.test_session_id || '');
        const matchesSessionName = testSessionNames.includes(p.test_session_name || '');
        const matchesParentSessionName = testSessionNames.includes(p.parent_test_session_name || '');
        const matchesVestNumber = p.vest_number === vest.vest_code;
        return matchesSessionId || matchesSessionName || matchesParentSessionName || matchesVestNumber;
      }) || [];

      // Calculate max and avg for shots 1-3 (both front and back combined)
      const shots1to3 = vestAnalyticsPoints.filter(s => 
        typeof s.shot_number === 'string' && 
        parseInt(s.shot_number) >= 1 && 
        parseInt(s.shot_number) <= 3 &&
        s.bfd_mm !== null
      );

      const maxBfd1to3 = shots1to3.length > 0 
        ? Math.max(...shots1to3.map(s => s.bfd_mm || 0))
        : null;
      
      const avgBfd1to3 = shots1to3.length > 0 
        ? shots1to3.reduce((sum, s) => sum + (s.bfd_mm || 0), 0) / shots1to3.length 
        : null;

      // Use the vest's total_thickness_mm, or estimate from layers
      let thickness = vest.total_thickness_mm;
      if (!thickness && vest.layers && vest.layers.length > 0 && materials) {
        const estimatedThickness = vest.layers.reduce((sum, layer) => {
          const material = materials.find(m => m.id === layer.material_id);
          if (material && material.thickness_mm && layer.layer_count) {
            return sum + (material.thickness_mm * layer.layer_count);
          }
          return sum;
        }, 0);
        if (estimatedThickness > 0) {
          thickness = estimatedThickness;
        }
      }

      return {
        ...vest,
        maxBfd1to3,
        avgBfd1to3,
        thickness,
        testSessionIds,
        testSessionNames,
      };
    } catch (err) {
      console.error('Failed to calculate vest stats:', err);
      return {
        ...vest,
        maxBfd1to3: null,
        avgBfd1to3: null,
        thickness: null,
        testSessionIds: [],
        testSessionNames: [],
      };
    }
  }, [materials, analyticsData]);

  useEffect(() => {
    const loadVest1Stats = async () => {
      if (selectedVest1) {
        setLoadingStats(true);
        try {
          const stats = await calculateVestStats(selectedVest1);
          setVest1Stats(stats);
        } catch (err) {
          console.error('Failed to load vest 1 stats:', err);
          setVest1Stats(null);
        } finally {
          setLoadingStats(false);
        }
      } else {
        setVest1Stats(null);
      }
    };

    loadVest1Stats();
  }, [selectedVest1, calculateVestStats]);

  useEffect(() => {
    const loadVest2Stats = async () => {
      if (selectedVest2) {
        setLoadingStats(true);
        try {
          const stats = await calculateVestStats(selectedVest2);
          setVest2Stats(stats);
        } catch (err) {
          console.error('Failed to load vest 2 stats:', err);
          setVest2Stats(null);
        } finally {
          setLoadingStats(false);
        }
      } else {
        setVest2Stats(null);
      }
    };

    loadVest2Stats();
  }, [selectedVest2, calculateVestStats]);

  const getBetterValue = (metric: string, val1: number | null, val2: number | null): 'vest1' | 'vest2' | 'tie' | null => {
    if (val1 === null || val2 === null) return null;
    
    // For BFD metrics, lower is better
    if (metric.includes('Bfd')) {
      if (val1 < val2) return 'vest1';
      if (val2 < val1) return 'vest2';
      return 'tie';
    }
    
    // For weight, lower is better
    if (metric === 'weight') {
      if (val1 < val2) return 'vest1';
      if (val2 < val1) return 'vest2';
      return 'tie';
    }
    
    // For thickness, lower is better
    if (metric === 'thickness') {
      if (val1 < val2) return 'vest1';
      if (val2 < val1) return 'vest2';
      return 'tie';
    }
    
    return 'tie';
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Vest Comparison</h1>
        <p className="text-gray-600 mt-1">Compare two vests side by side</p>
      </div>

      {vestsLoading && <div>Loading vests...</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select First Vest</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Search vests..."
              value={vest1Search}
              onChange={(e) => {
                setVest1Search(e.target.value);
                setVest1DropdownOpen(true);
              }}
              onFocus={() => setVest1DropdownOpen(true)}
              onBlur={() => setTimeout(() => setVest1DropdownOpen(false), 200)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
            />
            {vest1DropdownOpen && filteredVests1.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                {filteredVests1.map(vest => (
                  <div
                    key={vest.id}
                    onClick={() => {
                      setSelectedVest1(vest);
                      setVest1Search(vest.vest_code);
                      setVest1DropdownOpen(false);
                    }}
                    className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                  >
                    {vest.vest_code} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                  </div>
                ))}
              </div>
            )}
          </div>
          {selectedVest1 && (
            <div className="mt-4 p-4 bg-gray-50 rounded-md">
              <p className="font-medium text-gray-900">{selectedVest1.vest_code}</p>
              <p className="text-sm text-gray-600">Type: {selectedVest1.vest_type || 'N/A'}</p>
              <p className="text-sm text-gray-600">Threat Level: {selectedVest1.threat_level || 'N/A'}</p>
              <p className="text-sm text-gray-600">Layers: {selectedVest1.total_layers || 'N/A'}</p>
              <p className="text-sm text-gray-600">Composition: {(selectedVest1 as any).composition || 'N/A'}</p>
              <p className="text-sm text-gray-600">Test Sessions: {vest1Stats?.testSessionIds?.length || 'N/A'}</p>
            </div>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Select Second Vest</label>
          <div className="relative">
            <input
              type="text"
              placeholder="Search vests..."
              value={vest2Search}
              onChange={(e) => {
                setVest2Search(e.target.value);
                setVest2DropdownOpen(true);
              }}
              onFocus={() => setVest2DropdownOpen(true)}
              onBlur={() => setTimeout(() => setVest2DropdownOpen(false), 200)}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
            />
            {vest2DropdownOpen && filteredVests2.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                {filteredVests2.map(vest => (
                  <div
                    key={vest.id}
                    onClick={() => {
                      setSelectedVest2(vest);
                      setVest2Search(vest.vest_code);
                      setVest2DropdownOpen(false);
                    }}
                    className="px-4 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                  >
                    {vest.vest_code} - {vest.vest_type || 'N/A'} - {vest.threat_level || 'N/A'}
                  </div>
                ))}
              </div>
            )}
          </div>
          {selectedVest2 && (
            <div className="mt-4 p-4 bg-gray-50 rounded-md">
              <p className="font-medium text-gray-900">{selectedVest2.vest_code}</p>
              <p className="text-sm text-gray-600">Type: {selectedVest2.vest_type || 'N/A'}</p>
              <p className="text-sm text-gray-600">Threat Level: {selectedVest2.threat_level || 'N/A'}</p>
              <p className="text-sm text-gray-600">Layers: {selectedVest2.total_layers || 'N/A'}</p>
              <p className="text-sm text-gray-600">Composition: {(selectedVest2 as any).composition || 'N/A'}</p>
              <p className="text-sm text-gray-600">Test Sessions: {vest2Stats?.testSessionIds?.length || 'N/A'}</p>
            </div>
          )}
        </div>
      </div>

      {loadingStats && <div className="text-gray-600">Loading vest statistics...</div>}

      {vest1Stats && vest2Stats && (
        <>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Comparison</h2>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metric</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{vest1Stats.vest_code}</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{vest2Stats.vest_code}</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Avg BFD (Shots 1-3)</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('avgBfd1to3', vest1Stats.avgBfd1to3, vest2Stats.avgBfd1to3) === 'vest1' ? 'bg-green-50' : ''}`}>{vest1Stats.avgBfd1to3?.toFixed(2) || 'N/A'} mm</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('avgBfd1to3', vest1Stats.avgBfd1to3, vest2Stats.avgBfd1to3) === 'vest2' ? 'bg-green-50' : ''}`}>{vest2Stats.avgBfd1to3?.toFixed(2) || 'N/A'} mm</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Max BFD (Shots 1-3)</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('maxBfd1to3', vest1Stats.maxBfd1to3, vest2Stats.maxBfd1to3) === 'vest1' ? 'bg-green-50' : ''}`}>{vest1Stats.maxBfd1to3?.toFixed(2) || 'N/A'} mm</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('maxBfd1to3', vest1Stats.maxBfd1to3, vest2Stats.maxBfd1to3) === 'vest2' ? 'bg-green-50' : ''}`}>{vest2Stats.maxBfd1to3?.toFixed(2) || 'N/A'} mm</td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Thickness</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('thickness', vest1Stats.thickness, vest2Stats.thickness) === 'vest1' ? 'bg-green-50' : ''}`}>{vest1Stats.thickness ? Number(vest1Stats.thickness).toFixed(2) : 'N/A'} mm</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 ${getBetterValue('thickness', vest1Stats.thickness, vest2Stats.thickness) === 'vest2' ? 'bg-green-50' : ''}`}>{vest2Stats.thickness ? Number(vest2Stats.thickness).toFixed(2) : 'N/A'} mm</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Velocity vs BFD Comparison</h2>
            <div className="h-[600px]">
              {!analyticsLoading && vest1Stats && vest2Stats && (
                <Plot
                  data={[
                    {
                      x: vest1AnalyticsData.map(s => s.velocity),
                      y: vest1AnalyticsData.map(s => s.bfd_mm),
                      mode: 'markers',
                      type: 'scatter',
                      name: selectedVest1?.vest_code || 'Vest 1',
                      marker: { color: '#dc2626', size: 8 },
                    },
                    {
                      x: vest2AnalyticsData.map(s => s.velocity),
                      y: vest2AnalyticsData.map(s => s.bfd_mm),
                      mode: 'markers',
                      type: 'scatter',
                      name: selectedVest2?.vest_code || 'Vest 2',
                      marker: { color: '#2563eb', size: 8 },
                    },
                    ...(vest1Stats.avgBfd1to3 ? [{
                      x: [Math.min(...vest1AnalyticsData.map(s => s.velocity || 0), ...vest2AnalyticsData.map(s => s.velocity || 0)), Math.max(...vest1AnalyticsData.map(s => s.velocity || 0), ...vest2AnalyticsData.map(s => s.velocity || 0))],
                      y: [vest1Stats.avgBfd1to3, vest1Stats.avgBfd1to3],
                      mode: 'lines',
                      type: 'scatter',
                      name: `Avg BFD (${selectedVest1?.vest_code || 'Vest 1'})`,
                      line: { color: '#dc2626', dash: 'dash', width: 2 },
                    }] : []),
                    ...(vest2Stats.avgBfd1to3 ? [{
                      x: [Math.min(...vest1AnalyticsData.map(s => s.velocity || 0), ...vest2AnalyticsData.map(s => s.velocity || 0)), Math.max(...vest1AnalyticsData.map(s => s.velocity || 0), ...vest2AnalyticsData.map(s => s.velocity || 0))],
                      y: [vest2Stats.avgBfd1to3, vest2Stats.avgBfd1to3],
                      mode: 'lines',
                      type: 'scatter',
                      name: `Avg BFD (${selectedVest2?.vest_code || 'Vest 2'})`,
                      line: { color: '#2563eb', dash: 'dash', width: 2 },
                    }] : []),
                  ]}
                  layout={{
                    autosize: true,
                    margin: { t: 40, r: 40, b: 60, l: 80 },
                    xaxis: { 
                      title: 'Velocity (m/s)', 
                      gridcolor: '#e5e7eb',
                      autorange: true,
                    },
                    yaxis: { 
                      title: 'BFD (mm)', 
                      gridcolor: '#e5e7eb',
                      autorange: true,
                    },
                    hovermode: 'closest',
                    plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                    paper_bgcolor: 'white',
                    font: { family: 'Inter, sans-serif' },
                  }}
                  config={{
                    responsive: true,
                    displayModeBar: true,
                    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                    displaylogo: false,
                  }}
                  style={{ width: '100%', height: '100%' }}
                />
              )}
              {analyticsLoading && <div className="flex items-center justify-center h-full text-gray-500">Loading chart data...</div>}
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Raw Shot Data</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Shot</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" colSpan={2}>{vest1Stats?.vest_code || 'Vest 1'}</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-200"></th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" colSpan={2}>{vest2Stats?.vest_code || 'Vest 2'}</th>
                  </tr>
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100"></th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">Front</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">Back</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-200"></th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">Front</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">Back</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {Array.from({ length: 6 }, (_, i) => {
                    const shotNum = i + 1;
                    const vest1Front = vest1AnalyticsData.find(s => 
                      s.side?.toLowerCase() === 'front' && 
                      parseInt(s.shot_number || '0') === shotNum
                    );
                    const vest1Back = vest1AnalyticsData.find(s => 
                      s.side?.toLowerCase() === 'back' && 
                      parseInt(s.shot_number || '0') === shotNum
                    );
                    const vest2Front = vest2AnalyticsData.find(s => 
                      s.side?.toLowerCase() === 'front' && 
                      parseInt(s.shot_number || '0') === shotNum
                    );
                    const vest2Back = vest2AnalyticsData.find(s => 
                      s.side?.toLowerCase() === 'back' && 
                      parseInt(s.shot_number || '0') === shotNum
                    );

                    return (
                      <tr key={shotNum}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{shotNum}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {vest1Front ? (
                            <div className="text-xs">
                              <div>V: {vest1Front.velocity?.toFixed(0) || 'N/A'}</div>
                              <div>BFD: {vest1Front.bfd_mm?.toFixed(1) || 'N/A'}</div>
                            </div>
                          ) : <span className="text-gray-300">-</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {vest1Back ? (
                            <div className="text-xs">
                              <div>V: {vest1Back.velocity?.toFixed(0) || 'N/A'}</div>
                              <div>BFD: {vest1Back.bfd_mm?.toFixed(1) || 'N/A'}</div>
                            </div>
                          ) : <span className="text-gray-300">-</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 bg-gray-50"></td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {vest2Front ? (
                            <div className="text-xs">
                              <div>V: {vest2Front.velocity?.toFixed(0) || 'N/A'}</div>
                              <div>BFD: {vest2Front.bfd_mm?.toFixed(1) || 'N/A'}</div>
                            </div>
                          ) : <span className="text-gray-300">-</span>}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {vest2Back ? (
                            <div className="text-xs">
                              <div>V: {vest2Back.velocity?.toFixed(0) || 'N/A'}</div>
                              <div>BFD: {vest2Back.bfd_mm?.toFixed(1) || 'N/A'}</div>
                            </div>
                          ) : <span className="text-gray-300">-</span>}
                        </td>
                      </tr>
                    );
                  })}
                  {vest1AnalyticsData.length === 0 && vest2AnalyticsData.length === 0 && !analyticsLoading && (
                    <tr>
                      <td colSpan={6} className="px-6 py-4 text-center text-sm text-gray-500">
                        No shot data available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
