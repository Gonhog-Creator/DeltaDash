import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import Plot from 'react-plotly.js';
import { apiClient } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface AnalyticsPoint {
  velocity: number | null;
  bullet_energy: number | null;
  bfd_mm: number | null;
  caliber: string | null;
  protection_level: string | null;
  test_session_id: string | null;
  test_session_name: string | null;
  parent_test_session_name: string | null;
  vest_number: string | null;
  side: string | null;
  shot_number: string | null;
  angle_degrees: number | null;
  trauma_qualitative: string | null;
}

interface AnalyticsData {
  points: AnalyticsPoint[];
}

type AxisOption = 'velocity' | 'bullet_energy' | 'bfd_mm' | 'ballistic_limit';
type ColorGroupingOption = 'test_session' | 'side' | 'shot_number' | 'result' | 'protection_level';

const AXIS_OPTIONS: { value: AxisOption; label: string }[] = [
  { value: 'velocity', label: 'Velocity (m/s)' },
  { value: 'bullet_energy', label: 'Bullet Energy (J)' },
  { value: 'bfd_mm', label: 'BFD (mm)' },
  { value: 'ballistic_limit', label: 'Ballistic Limit Test' },
];

const COLOR_GROUPING_OPTIONS: { value: ColorGroupingOption; label: string; type: 'range' | 'category' }[] = [
  { value: 'test_session', label: 'Test Session (Group)', type: 'category' },
  { value: 'side', label: 'Side (Front/Back)', type: 'category' },
  { value: 'shot_number', label: 'Shot Number (Group)', type: 'category' },
  { value: 'result', label: 'Test Result (OK/Punctured)', type: 'category' },
  { value: 'protection_level', label: 'Protection Level', type: 'category' },
];

export function Analytics() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { data: analyticsData, isLoading, error } = useQuery<AnalyticsData>({
    queryKey: ['analytics', 'velocity-vs-bfd'],
    queryFn: () => apiClient.get<AnalyticsData>('/api/v1/analytics/velocity-vs-bfd'),
  });

  const [activeTab, setActiveTab] = useState<'builder' | 'velocity-bfd' | 'energy-bfd'>('builder');
  const [xAxis, setXAxis] = useState<AxisOption>('bfd_mm');
  const [yAxis, setYAxis] = useState<AxisOption>('velocity');
  const [colorGrouping, setColorGrouping] = useState<ColorGroupingOption>('side');

  // Lock y-axis to velocity when ballistic_limit is selected
  const handleXAxisChange = (value: AxisOption) => {
    setXAxis(value);
    if (value === 'ballistic_limit') {
      setYAxis('velocity');
      setColorGrouping('result');
    }
  };
  
  // Filters
  const [selectedCalibers, setSelectedCalibers] = useState<string[]>([]);
  const [selectedProtectionLevels, setSelectedProtectionLevels] = useState<string[]>([]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">Loading analytics data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-red-500">Error loading analytics data</div>
      </div>
    );
  }

  const getAxisValue = (point: AnalyticsPoint, axis: AxisOption): number | null => {
    switch (axis) {
      case 'velocity':
        return point.velocity;
      case 'bullet_energy':
        return point.bullet_energy;
      case 'bfd_mm':
        return point.bfd_mm;
      case 'ballistic_limit':
        return point.shot_number ? parseFloat(point.shot_number) : null;
      default:
        return null;
    }
  };

  const getColorValue = (point: AnalyticsPoint, grouping: ColorGroupingOption): string | number | null => {
    switch (grouping) {
      case 'test_session':
        // Strip vest number from test session name to group by main session only
        const sessionName = point.test_session_name || point.test_session_id || 'Unknown';
        // Remove " - Vest X" pattern to avoid splitting by vest
        return sessionName.replace(/\s*-\s*Vest\s*\d+/i, '').trim();
      case 'side':
        // Include angle in side grouping if present
        if (point.side && point.angle_degrees && point.angle_degrees > 0) {
          // Normalize side name
          const sideName = point.side.charAt(0).toUpperCase() + point.side.slice(1);
          return `${sideName} (${point.angle_degrees}°)`;
        }
        // Normalize side name
        return point.side ? point.side.charAt(0).toUpperCase() + point.side.slice(1) : 'Unknown';
      case 'shot_number':
        return point.shot_number || 'Unknown';
      case 'result':
        // Use trauma_qualitative field to determine test result
        // Normalize values: "OK" stays as "OK", "punctured"/"perforada" become "Punctured"
        if (!point.trauma_qualitative) {
          return 'Unknown';
        }
        const value = point.trauma_qualitative.toLowerCase();
        if (value === 'ok') {
          return 'OK';
        }
        if (value === 'punctured' || value === 'perforada') {
          return 'Punctured';
        }
        // If it's some other value, treat as Unknown
        return 'Unknown';
      case 'protection_level':
        return point.protection_level || 'Unknown';
      default:
        return null;
    }
  };

  const getAxisLabel = (axis: AxisOption): string => {
    if (axis === 'ballistic_limit') {
      return 'Shot Number';
    }
    const option = AXIS_OPTIONS.find(opt => opt.value === axis);
    return option ? option.label : axis;
  };

  const getColorGroupingLabel = (grouping: ColorGroupingOption): string => {
    const option = COLOR_GROUPING_OPTIONS.find(opt => opt.value === grouping);
    return option ? option.label : grouping;
  };

  const getColorGroupingType = (grouping: ColorGroupingOption): 'range' | 'category' => {
    const option = COLOR_GROUPING_OPTIONS.find(opt => opt.value === grouping);
    return option ? option.type : 'range';
  };

  // Get unique filter options from data
  const uniqueCalibers = Array.from(new Set(analyticsData?.points.map(p => p.caliber).filter(Boolean) || []));
  const uniqueProtectionLevels = Array.from(new Set(analyticsData?.points.map(p => p.protection_level).filter(Boolean) || []));

  // Apply filters
  const filteredPoints = analyticsData?.points.filter(p => {
    // Filter by caliber
    if (selectedCalibers.length > 0 && (!p.caliber || !selectedCalibers.includes(p.caliber))) {
      return false;
    }

    // Filter by protection level
    if (selectedProtectionLevels.length > 0 && (!p.protection_level || !selectedProtectionLevels.includes(p.protection_level))) {
      return false;
    }

    // Filter out ballistic limit tests (bfd_mm === null) for regular charts
    if (xAxis !== 'ballistic_limit' && p.bfd_mm === null) {
      return false;
    }

    // For ballistic limit chart, only include ballistic limit tests (bfd_mm === null)
    if (xAxis === 'ballistic_limit' && p.bfd_mm !== null) {
      return false;
    }

    // Filter out points with null values for selected axes
    if (getAxisValue(p, xAxis) === null) {
      return false;
    }
    if (getAxisValue(p, yAxis) === null) {
      return false;
    }

    return true;
  }) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-gray-600 mt-1">Visualize ballistic test data</p>
      </div>

      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('builder')}
            className={`${
              activeTab === 'builder'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Chart Builder
          </button>
          <button
            onClick={() => setActiveTab('velocity-bfd')}
            className={`${
              activeTab === 'velocity-bfd'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Velocity vs BFD
          </button>
          <button
            onClick={() => setActiveTab('energy-bfd')}
            className={`${
              activeTab === 'energy-bfd'
                ? 'border-indigo-500 text-indigo-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            Bullet Energy vs BFD
          </button>
        </nav>
      </div>

      {activeTab === 'builder' ? (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Chart Configuration</h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">X-Axis</label>
                <select
                  value={xAxis}
                  onChange={(e) => handleXAxisChange(e.target.value as AxisOption)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  {AXIS_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Y-Axis</label>
                <select
                  value={yAxis}
                  onChange={(e) => setYAxis(e.target.value as AxisOption)}
                  disabled={xAxis === 'ballistic_limit'}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-gray-100 disabled:text-gray-500"
                >
                  {AXIS_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Color Grouping</label>
                <select
                  value={colorGrouping}
                  onChange={(e) => setColorGrouping(e.target.value as ColorGroupingOption)}
                  disabled={xAxis === 'ballistic_limit'}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border disabled:bg-gray-100 disabled:text-gray-500"
                >
                  {COLOR_GROUPING_OPTIONS.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Filters</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ammunition Type (Caliber)</label>
                <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-2">
                  {uniqueCalibers.map(caliber => (
                    <label key={caliber} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={selectedCalibers.includes(caliber)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedCalibers([...selectedCalibers, caliber]);
                          } else {
                            setSelectedCalibers(selectedCalibers.filter(c => c !== caliber));
                          }
                        }}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-gray-700">{caliber}</span>
                    </label>
                  ))}
                </div>
                {selectedCalibers.length > 0 && (
                  <button
                    onClick={() => setSelectedCalibers([])}
                    className="mt-2 text-sm text-indigo-600 hover:text-indigo-800"
                  >
                    Clear caliber filter
                  </button>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Protection Level</label>
                <div className="space-y-2 max-h-40 overflow-y-auto border rounded-md p-2">
                  {uniqueProtectionLevels.map(level => (
                    <label key={level} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={selectedProtectionLevels.includes(level)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedProtectionLevels([...selectedProtectionLevels, level]);
                          } else {
                            setSelectedProtectionLevels(selectedProtectionLevels.filter(l => l !== level));
                          }
                        }}
                        className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <span className="text-sm text-gray-700">{level}</span>
                    </label>
                  ))}
                </div>
                {selectedProtectionLevels.length > 0 && (
                  <button
                    onClick={() => setSelectedProtectionLevels([])}
                    className="mt-2 text-sm text-indigo-600 hover:text-indigo-800"
                  >
                    Clear protection level filter
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              {getAxisLabel(yAxis)} vs {getAxisLabel(xAxis)}
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Color Grouping: {getColorGroupingLabel(colorGrouping)}
            </p>
            
            {filteredPoints.length > 0 ? (
              <div className="h-[600px]">
                <Plot
                  data={
                    getColorGroupingType(colorGrouping) === 'category' 
                      ? (() => {
                          // Group by category and create separate traces
                          const groups = new Map<string, AnalyticsPoint[]>();
                          filteredPoints.forEach(p => {
                            const key = String(getColorValue(p, colorGrouping) || 'Unknown');
                            if (!groups.has(key)) {
                              groups.set(key, []);
                            }
                            groups.get(key)!.push(p);
                          });

                          const colors = ['#dc2626', '#2563eb', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#ca8a04', '#db2777'];
                          
                          return Array.from(groups.entries()).map(([groupName, points], index) => ({
                            x: points.map(p => getAxisValue(p, xAxis)),
                            y: points.map(p => getAxisValue(p, yAxis)),
                            mode: 'markers',
                            type: 'scatter',
                            marker: {
                              size: 8,
                              color: colorGrouping === 'result' 
                                ? (groupName === 'OK' ? '#16a34a' : '#dc2626')
                                : colors[index % colors.length],
                            },
                            text: points.map(p => {
                              const sessionName = p.test_session_name || p.test_session_id || 'N/A';
                              let parentFolder = p.parent_test_session_name;
                              if (!parentFolder && sessionName.includes(' - ')) {
                                const parts = sessionName.split(' - ');
                                // If there are at least 3 parts and the first two parts are the same (e.g., "4 - 4 - S - Ambient"),
                                // use just one of them as the parent indicator
                                if (parts.length >= 3 && parts[0] === parts[1]) {
                                  parentFolder = parts[0];
                                } else if (parts.length >= 3) {
                                  parentFolder = parts[0];
                                } else {
                                  parentFolder = parts[0];
                                }
                              }
                              if (!parentFolder) {
                                parentFolder = sessionName;
                              }
                              return `Test: ${parentFolder} - ${sessionName}<br>Caliber: ${p.caliber || 'N/A'}<br>Velocity: ${p.velocity?.toFixed(2) || 'N/A'} m/s<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm<br>Bullet Energy: ${p.bullet_energy?.toFixed(2) || 'N/A'} J`;
                            }),
                            customdata: points.map(p => p.test_session_id),
                            hoverinfo: 'text+x+y',
                            name: groupName,
                            showlegend: true,
                          }));
                        })()
                      : [
                          {
                            x: filteredPoints.map(p => getAxisValue(p, xAxis)),
                            y: filteredPoints.map(p => getAxisValue(p, yAxis)),
                            mode: 'markers',
                            type: 'scatter',
                            marker: {
                              size: 8,
                              color: filteredPoints.map(p => getColorValue(p, colorGrouping)),
                              colorscale: 'Viridis',
                              showscale: true,
                              colorbar: {
                                title: getColorGroupingLabel(colorGrouping),
                                x: 1.02,
                              },
                            },
                            text: filteredPoints.map(p => {
                              const sessionName = p.test_session_name || p.test_session_id || 'N/A';
                              let parentFolder = p.parent_test_session_name;
                              if (!parentFolder && sessionName.includes(' - ')) {
                                const parts = sessionName.split(' - ');
                                parentFolder = parts.length >= 3 ? parts[0] : parts[0];
                              }
                              if (!parentFolder) {
                                parentFolder = sessionName;
                              }
                              return `Test: ${parentFolder} - ${sessionName}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Velocity: ${p.velocity?.toFixed(2) || 'N/A'} m/s<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm<br>Bullet Energy: ${p.bullet_energy?.toFixed(2) || 'N/A'} J`;
                            }),
                            customdata: filteredPoints.map(p => p.test_session_id),
                            hoverinfo: 'text+x+y',
                            name: 'Shots',
                          },
                        ]
                  }
                  layout={{
                    autosize: true,
                    margin: { t: 40, r: getColorGroupingType(colorGrouping) === 'range' ? 120 : 40, b: 60, l: 80 },
                    xaxis: {
                      title: getAxisLabel(xAxis),
                      gridcolor: '#e5e7eb',
                      zerolinecolor: '#9ca3af',
                    },
                    yaxis: {
                      title: getAxisLabel(yAxis),
                      gridcolor: '#e5e7eb',
                      zerolinecolor: '#9ca3af',
                    },
                    hovermode: 'closest',
                    plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                    paper_bgcolor: 'white',
                    font: {
                      family: 'Inter, sans-serif',
                    },
                  }}
                  config={{
                    responsive: true,
                    displayModeBar: true,
                    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                    displaylogo: false,
                  }}
                  onClick={(data: any) => {
                    if (data.points && data.points.length > 0) {
                      const testSessionId = data.points[0].customdata;
                      if (testSessionId) {
                        navigate(`/test-sessions/${testSessionId}`);
                      }
                    }
                  }}
                  style={{ width: '100%', height: '100%' }}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-96">
                <div className="text-gray-500">No data available for selected axes</div>
              </div>
            )}
          </div>

          {isAdmin && (
            <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Debug Info</h3>
              <div className="text-xs text-gray-600 space-y-1">
                <p>Total points in dataset: {analyticsData?.points.length || 0}</p>
                <p>Filtered points displayed: {filteredPoints.length}</p>
                <p>Points filtered by caliber: {analyticsData?.points.filter(p => selectedCalibers.length > 0 && (!p.caliber || !selectedCalibers.includes(p.caliber))).length || 0}</p>
                <p>Points filtered by protection level: {analyticsData?.points.filter(p => selectedProtectionLevels.length > 0 && (!p.protection_level || !selectedProtectionLevels.includes(p.protection_level))).length || 0}</p>
                <p>Points filtered (no BFD): {analyticsData?.points.filter(p => xAxis !== 'ballistic_limit' && p.bfd_mm === null).length || 0}</p>
                <p>Points filtered (null x-axis): {analyticsData?.points.filter(p => getAxisValue(p, xAxis) === null).length || 0}</p>
                <p>Points filtered (null y-axis): {analyticsData?.points.filter(p => getAxisValue(p, yAxis) === null).length || 0}</p>
                <p>Unique calibers: {uniqueCalibers.length}</p>
                <p>Unique protection levels: {uniqueProtectionLevels.length}</p>
                <p>Active caliber filters: {selectedCalibers.length > 0 ? selectedCalibers.join(', ') : 'None'}</p>
                <p>Active protection level filters: {selectedProtectionLevels.length > 0 ? selectedProtectionLevels.join(', ') : 'None'}</p>
              </div>
            </div>
          )}
        </div>
      ) : activeTab === 'energy-bfd' ? (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Bullet Energy vs Back Face Deformation
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Y-axis: Bullet Energy (J)<br />
            X-axis: Back Face Deformation (mm)
          </p>
          
          {analyticsData && analyticsData.points.length > 0 ? (
            <div className="h-[600px]">
              <Plot
                data={[
                  {
                    x: analyticsData.points.map(p => p.bfd_mm),
                    y: analyticsData.points.map(p => p.bullet_energy),
                    mode: 'markers',
                    type: 'scatter',
                    marker: {
                      size: 8,
                      color: analyticsData.points.map(p => p.bullet_energy),
                      colorscale: 'Viridis',
                      showscale: true,
                      colorbar: {
                        title: 'Bullet Energy (J)',
                        x: 1.02,
                      },
                    },
                    text: analyticsData.points.map(p => 
                      `Test Session: ${p.test_session_name || p.test_session_id || 'N/A'}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Bullet Energy: ${p.bullet_energy?.toFixed(2) || 'N/A'} J<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm`
                    ),
                    hoverinfo: 'text+x+y',
                    name: 'Shots',
                  },
                ]}
                layout={{
                  autosize: true,
                  margin: { t: 40, r: 40, b: 60, l: 80 },
                  xaxis: {
                    title: 'Back Face Deformation (mm)',
                    gridcolor: '#e5e7eb',
                    zerolinecolor: '#9ca3af',
                  },
                  yaxis: {
                    title: 'Bullet Energy (J)',
                    gridcolor: '#e5e7eb',
                    zerolinecolor: '#9ca3af',
                  },
                  hovermode: 'closest',
                  plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                  paper_bgcolor: 'white',
                  font: {
                    family: 'Inter, sans-serif',
                  },
                }}
                config={{
                  responsive: true,
                  displayModeBar: true,
                  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                  displaylogo: false,
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-96">
              <div className="text-gray-500">No data available</div>
            </div>
          )}

          {isAdmin && (
            <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200 mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Debug Info</h3>
              <div className="text-xs text-gray-600 space-y-1">
                <p>Total points in dataset: {analyticsData?.points.length || 0}</p>
                <p>Points with bullet energy: {analyticsData?.points.filter(p => p.bullet_energy !== null).length || 0}</p>
                <p>Points with BFD: {analyticsData?.points.filter(p => p.bfd_mm !== null).length || 0}</p>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Velocity vs Back Face Deformation
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Y-axis: Velocity (m/s)<br />
            X-axis: Back Face Deformation (mm)
          </p>
          
          {analyticsData && analyticsData.points.length > 0 ? (
            <div className="h-[600px]">
              <Plot
                data={[
                  {
                    x: analyticsData.points.map(p => p.bfd_mm),
                    y: analyticsData.points.map(p => p.velocity),
                    mode: 'markers',
                    type: 'scatter',
                    marker: {
                      size: 8,
                      color: analyticsData.points.map(p => p.velocity),
                      colorscale: 'Viridis',
                      showscale: true,
                      colorbar: {
                        title: 'Velocity (m/s)',
                        x: 1.02,
                      },
                    },
                    text: analyticsData.points.map(p => 
                      `Test Session: ${p.test_session_name || p.test_session_id || 'N/A'}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Velocity: ${p.velocity?.toFixed(2) || 'N/A'} m/s<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm`
                    ),
                    hoverinfo: 'text+x+y',
                    name: 'Shots',
                  },
                ]}
                layout={{
                  autosize: true,
                  margin: { t: 40, r: 40, b: 60, l: 80 },
                  xaxis: {
                    title: 'Back Face Deformation (mm)',
                    gridcolor: '#e5e7eb',
                    zerolinecolor: '#9ca3af',
                  },
                  yaxis: {
                    title: 'Velocity (m/s)',
                    gridcolor: '#e5e7eb',
                    zerolinecolor: '#9ca3af',
                  },
                  hovermode: 'closest',
                  plot_bgcolor: 'rgba(255, 255, 255, 0.8)',
                  paper_bgcolor: 'white',
                  font: {
                    family: 'Inter, sans-serif',
                  },
                }}
                config={{
                  responsive: true,
                  displayModeBar: true,
                  modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                  displaylogo: false,
                }}
                style={{ width: '100%', height: '100%' }}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-96">
              <div className="text-gray-500">No data available</div>
            </div>
          )}

          {isAdmin && (
            <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200 mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Debug Info</h3>
              <div className="text-xs text-gray-600 space-y-1">
                <p>Total points in dataset: {analyticsData?.points.length || 0}</p>
                <p>Points with velocity: {analyticsData?.points.filter(p => p.velocity !== null).length || 0}</p>
                <p>Points with BFD: {analyticsData?.points.filter(p => p.bfd_mm !== null).length || 0}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
