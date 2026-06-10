import Plot from 'react-plotly.js';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

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
  is_official: boolean | null;
  material_name: string | null;
  material_class: string | null;
}

interface AnalyticsData {
  points: AnalyticsPoint[];
}

interface FilterSectionProps {
  uniqueCalibers: string[];
  uniqueProtectionLevels: string[];
  selectedCalibers: string[];
  selectedProtectionLevels: string[];
  setSelectedCalibers: (calibers: string[]) => void;
  setSelectedProtectionLevels: (levels: string[]) => void;
}

export function FilterSection({
  uniqueCalibers,
  uniqueProtectionLevels,
  selectedCalibers,
  selectedProtectionLevels,
  setSelectedCalibers,
  setSelectedProtectionLevels,
}: FilterSectionProps) {
  return (
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
  );
}

interface DebugInfoProps {
  analyticsData: AnalyticsData | undefined;
  filteredPoints: AnalyticsPoint[];
  debugStats?: {
    xLabel: string;
    yLabel: string;
  };
}

export function DebugInfo({ analyticsData, filteredPoints, debugStats }: DebugInfoProps) {
  return (
    <div className="bg-gray-50 rounded-lg shadow p-4 border border-gray-200 mt-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-semibold text-gray-700">Debug Info</h3>
        <button
          onClick={() => {
            const data = JSON.stringify(analyticsData?.points || [], null, 2);
            navigator.clipboard.writeText(data);
          }}
          className="text-xs text-indigo-600 hover:text-indigo-800"
        >
          Copy Raw Data
        </button>
      </div>
      <div className="text-xs text-gray-600 space-y-1">
        <p>Total points in dataset: {analyticsData?.points.length || 0}</p>
        <p>Filtered points displayed: {filteredPoints.length}</p>
        {debugStats && (
          <>
            <p>Points with {debugStats.xLabel}: {analyticsData?.points.filter(p => {
              if (debugStats.xLabel === 'velocity') return p.velocity !== null;
              if (debugStats.xLabel === 'bullet energy') return p.bullet_energy !== null;
              if (debugStats.xLabel === 'BFD') return p.bfd_mm !== null;
              return true;
            }).length || 0}</p>
            <p>Points with {debugStats.yLabel}: {analyticsData?.points.filter(p => {
              if (debugStats.yLabel === 'velocity') return p.velocity !== null;
              if (debugStats.yLabel === 'bullet energy') return p.bullet_energy !== null;
              if (debugStats.yLabel === 'BFD') return p.bfd_mm !== null;
              return true;
            }).length || 0}</p>
          </>
        )}
      </div>
    </div>
  );
}

interface VelocityVsBfdChartProps {
  filteredPoints: AnalyticsPoint[];
  isAdmin: boolean;
  analyticsData: AnalyticsData | undefined;
  uniqueCalibers: string[];
  uniqueProtectionLevels: string[];
  selectedCalibers: string[];
  selectedProtectionLevels: string[];
  setSelectedCalibers: (calibers: string[]) => void;
  setSelectedProtectionLevels: (levels: string[]) => void;
}

export function VelocityVsBfdChart({
  filteredPoints,
  isAdmin,
  analyticsData,
  uniqueCalibers,
  uniqueProtectionLevels,
  selectedCalibers,
  selectedProtectionLevels,
  setSelectedCalibers,
  setSelectedProtectionLevels,
}: VelocityVsBfdChartProps) {
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <FilterSection
        uniqueCalibers={uniqueCalibers}
        uniqueProtectionLevels={uniqueProtectionLevels}
        selectedCalibers={selectedCalibers}
        selectedProtectionLevels={selectedProtectionLevels}
        setSelectedCalibers={setSelectedCalibers}
        setSelectedProtectionLevels={setSelectedProtectionLevels}
      />

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Velocity vs Back Face Deformation
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Y-axis: Back Face Deformation (mm)<br />
          X-axis: Velocity (m/s)
        </p>

        {analyticsData && analyticsData.points.length > 0 ? (
          <div className="h-[600px]">
            <Plot
              data={[
                {
                  x: filteredPoints.map(p => p.velocity),
                  y: filteredPoints.map(p => p.bfd_mm),
                  mode: 'markers',
                  type: 'scatter',
                  marker: {
                    size: 8,
                    color: filteredPoints.map(p => p.caliber),
                    colorscale: 'Viridis',
                    showscale: true,
                    colorbar: {
                      title: 'Caliber',
                      x: 1.02,
                    },
                  },
                  text: filteredPoints.map(p =>
                    `Test Session: ${p.test_session_name || p.test_session_id || 'N/A'}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Velocity: ${p.velocity?.toFixed(2) || 'N/A'} m/s<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm`
                  ),
                  hoverinfo: 'text+x+y',
                  name: 'Shots',
                  customdata: filteredPoints.map(p => p.test_session_id),
                },
              ]}
              layout={{
                autosize: true,
                margin: { t: 40, r: 40, b: 60, l: 80 },
                xaxis: {
                  title: 'Velocity (m/s)',
                  gridcolor: '#e5e7eb',
                  zerolinecolor: '#9ca3af',
                },
                yaxis: {
                  title: 'Back Face Deformation (mm)',
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
            <div className="text-gray-500">No data available</div>
          </div>
        )}

        {isAdmin && (
          <DebugInfo
            analyticsData={analyticsData}
            filteredPoints={filteredPoints}
            debugStats={{ xLabel: 'velocity', yLabel: 'BFD' }}
          />
        )}
      </div>
    </div>
  );
}

interface EnergyVsVelocityChartProps {
  filteredPoints: AnalyticsPoint[];
  isAdmin: boolean;
  analyticsData: AnalyticsData | undefined;
  uniqueCalibers: string[];
  uniqueProtectionLevels: string[];
  selectedCalibers: string[];
  selectedProtectionLevels: string[];
  setSelectedCalibers: (calibers: string[]) => void;
  setSelectedProtectionLevels: (levels: string[]) => void;
}

export function EnergyVsVelocityChart({
  filteredPoints,
  isAdmin,
  analyticsData,
  uniqueCalibers,
  uniqueProtectionLevels,
  selectedCalibers,
  selectedProtectionLevels,
  setSelectedCalibers,
  setSelectedProtectionLevels,
}: EnergyVsVelocityChartProps) {
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <FilterSection
        uniqueCalibers={uniqueCalibers}
        uniqueProtectionLevels={uniqueProtectionLevels}
        selectedCalibers={selectedCalibers}
        selectedProtectionLevels={selectedProtectionLevels}
        setSelectedCalibers={setSelectedCalibers}
        setSelectedProtectionLevels={setSelectedProtectionLevels}
      />

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Bullet Energy vs Velocity
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Y-axis: Bullet Energy (J)<br />
          X-axis: Velocity (m/s)
        </p>

        {analyticsData && analyticsData.points.length > 0 ? (
          <div className="h-[600px]">
            <Plot
              data={(() => {
                const uniqueCalibers = Array.from(new Set(filteredPoints.map(pt => pt.caliber).filter(Boolean)));
                const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
                return uniqueCalibers.map((caliber, idx) => {
                  const caliberPoints = filteredPoints.filter(p => p.caliber === caliber);
                  return {
                    x: caliberPoints.map(p => p.velocity),
                    y: caliberPoints.map(p => p.bullet_energy),
                    mode: 'markers',
                    type: 'scatter',
                    marker: {
                      size: 8,
                      color: colors[idx % colors.length],
                    },
                    text: caliberPoints.map(p =>
                      `Test Session: ${p.test_session_name || p.test_session_id || 'N/A'}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Velocity: ${p.velocity?.toFixed(2) || 'N/A'} m/s<br>Bullet Energy: ${p.bullet_energy?.toFixed(2) || 'N/A'} J`
                    ),
                    hoverinfo: 'text+x+y',
                    name: caliber,
                    showlegend: true,
                    customdata: caliberPoints.map(p => p.test_session_id),
                  };
                });
              })()}
              layout={{
                autosize: true,
                margin: { t: 40, r: 40, b: 60, l: 80 },
                xaxis: {
                  title: 'Velocity (m/s)',
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
            <div className="text-gray-500">No data available</div>
          </div>
        )}

        {isAdmin && (
          <DebugInfo
            analyticsData={analyticsData}
            filteredPoints={filteredPoints}
            debugStats={{ xLabel: 'velocity', yLabel: 'bullet energy' }}
          />
        )}
      </div>
    </div>
  );
}

interface EnergyVsBfdChartProps {
  filteredPoints: AnalyticsPoint[];
  isAdmin: boolean;
  analyticsData: AnalyticsData | undefined;
  uniqueCalibers: string[];
  uniqueProtectionLevels: string[];
  selectedCalibers: string[];
  selectedProtectionLevels: string[];
  setSelectedCalibers: (calibers: string[]) => void;
  setSelectedProtectionLevels: (levels: string[]) => void;
}

export function EnergyVsBfdChart({
  filteredPoints,
  isAdmin,
  analyticsData,
  uniqueCalibers,
  uniqueProtectionLevels,
  selectedCalibers,
  selectedProtectionLevels,
  setSelectedCalibers,
  setSelectedProtectionLevels,
}: EnergyVsBfdChartProps) {
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <FilterSection
        uniqueCalibers={uniqueCalibers}
        uniqueProtectionLevels={uniqueProtectionLevels}
        selectedCalibers={selectedCalibers}
        selectedProtectionLevels={selectedProtectionLevels}
        setSelectedCalibers={setSelectedCalibers}
        setSelectedProtectionLevels={setSelectedProtectionLevels}
      />

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
                  x: filteredPoints.map(p => p.bfd_mm),
                  y: filteredPoints.map(p => p.bullet_energy),
                  mode: 'markers',
                  type: 'scatter',
                  marker: {
                    size: 8,
                    color: filteredPoints.map(p => p.bullet_energy),
                    colorscale: 'Viridis',
                    showscale: true,
                    colorbar: {
                      title: 'Bullet Energy (J)',
                      x: 1.02,
                    },
                  },
                  text: filteredPoints.map(p =>
                    `Test Session: ${p.test_session_name || p.test_session_id || 'N/A'}<br>Shot: ${p.shot_number || 'N/A'}<br>Vest: ${p.vest_number || 'N/A'}<br>Side: ${p.side ? p.side.charAt(0).toUpperCase() + p.side.slice(1) : 'N/A'}${p.angle_degrees ? ` (${p.angle_degrees}°)` : ''}<br>Caliber: ${p.caliber || 'N/A'}<br>Protection Level: ${p.protection_level || 'N/A'}<br>Bullet Energy: ${p.bullet_energy?.toFixed(2) || 'N/A'} J<br>BFD: ${p.bfd_mm?.toFixed(2) || 'N/A'} mm`
                  ),
                  hoverinfo: 'text+x+y',
                  name: 'Shots',
                  customdata: filteredPoints.map(p => p.test_session_id),
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
            <div className="text-gray-500">No data available</div>
          </div>
        )}

        {isAdmin && (
          <DebugInfo
            analyticsData={analyticsData}
            filteredPoints={filteredPoints}
            debugStats={{ xLabel: 'bullet energy', yLabel: 'BFD' }}
          />
        )}
      </div>
    </div>
  );
}

interface MaterialVsBfdChartProps {
  materialAnalyticsData: {
    material_classes: Array<{
      material_class: string;
      avg_bfd: number;
      count: number;
    }>;
    materials: Array<{
      material_class: string;
      material_name: string;
      avg_bfd: number;
      count: number;
    }>;
  } | undefined;
  isLoading: boolean;
  isAdmin: boolean;
}

export function MaterialVsBfdChart({
  materialAnalyticsData,
  isLoading,
  isAdmin,
}: MaterialVsBfdChartProps) {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const normalizeCategoryName = (name: string): string => {
    if (!name) return '';
    return name
      .replace(/_/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">Loading material analytics...</div>
      </div>
    );
  }

  if (!materialAnalyticsData || materialAnalyticsData.material_classes.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-500">No material data available</div>
      </div>
    );
  }

  let chartData: { x: string[]; y: number[]; counts: number[]; names: string[] };

  if (selectedCategory) {
    const categoryMaterials = materialAnalyticsData.materials.filter(
      m => m.material_class === selectedCategory
    );
    if (categoryMaterials.length > 0) {
      chartData = {
        x: categoryMaterials.map(m => m.material_name),
        y: categoryMaterials.map(m => m.avg_bfd),
        counts: categoryMaterials.map(m => m.count),
        names: categoryMaterials.map(m => m.material_name)
      };
    } else {
      chartData = { x: [], y: [], counts: [], names: [] };
    }
  } else {
    chartData = {
      x: materialAnalyticsData.material_classes.map(m => normalizeCategoryName(m.material_class)),
      y: materialAnalyticsData.material_classes.map(m => m.avg_bfd),
      counts: materialAnalyticsData.material_classes.map(m => m.count),
      names: materialAnalyticsData.material_classes.map(m => normalizeCategoryName(m.material_class))
    };
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Filters</h2>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Material Category</label>
          <div className="flex flex-wrap gap-4 border rounded-md p-2">
            <label className="flex items-center space-x-2">
              <input
                type="radio"
                name="category"
                checked={selectedCategory === null}
                onChange={() => setSelectedCategory(null)}
                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700">All Categories</span>
            </label>
            {materialAnalyticsData.material_classes.map(mc => (
              <label key={mc.material_class} className="flex items-center space-x-2">
                <input
                  type="radio"
                  name="category"
                  checked={selectedCategory === mc.material_class}
                  onChange={() => setSelectedCategory(mc.material_class)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-gray-700">{normalizeCategoryName(mc.material_class)}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {selectedCategory ? `Materials in ${normalizeCategoryName(selectedCategory)} Category` : 'Material Categories vs Average BFD'}
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Y-axis: Average Back Face Deformation (mm)<br />
          X-axis: {selectedCategory ? 'Material Name' : 'Material Category'}
        </p>

        {chartData.x.length > 0 ? (
          <div className="h-[600px]">
            <Plot
              data={[
                {
                  x: chartData.x,
                  y: chartData.y,
                  type: 'bar',
                  marker: {
                    color: chartData.x.map((_, idx) => idx % 2 === 0 ? '#3b82f6' : '#6366f1'),
                    line: {
                      color: '#1e40af',
                      width: 1,
                    },
                  },
                  text: chartData.y.map((avg, idx) => avg.toFixed(2)),
                  textposition: 'outside',
                  textfont: {
                    size: 16,
                    color: '#1f2937',
                    family: 'Inter, sans-serif',
                  },
                  hoverinfo: 'x+y',
                  hovertemplate: '<b>%{x}</b><br>Avg BFD: %{y:.2f} mm<extra></extra>',
                  name: 'Average BFD',
                },
                {
                  x: chartData.x,
                  y: chartData.y,
                  type: 'bar',
                  marker: {
                    color: 'rgba(37, 99, 235, 0)',
                  },
                  text: chartData.counts.map(count => `n=${count}`),
                  textposition: 'inside bottom',
                  textfont: {
                    size: 14,
                    color: '#ffffff',
                    family: 'Inter, sans-serif',
                  },
                  hoverinfo: 'skip',
                  showlegend: false,
                },
              ]}
              layout={{
                autosize: true,
                margin: { t: 80, r: 50, b: 120, l: 90 },
                xaxis: {
                  title: {
                    text: selectedCategory ? 'Material Name' : 'Material Category',
                    font: {
                      size: 14,
                      color: '#374151',
                      family: 'Inter, sans-serif',
                    },
                  },
                  gridcolor: '#f3f4f6',
                  zerolinecolor: '#d1d5db',
                  tickangle: -45,
                  tickfont: {
                    size: 12,
                    color: '#6b7280',
                    family: 'Inter, sans-serif',
                  },
                },
                yaxis: {
                  title: {
                    text: 'Average BFD (mm)',
                    font: {
                      size: 14,
                      color: '#374151',
                      family: 'Inter, sans-serif',
                    },
                  },
                  gridcolor: '#f3f4f6',
                  zerolinecolor: '#d1d5db',
                  tickfont: {
                    size: 12,
                    color: '#6b7280',
                    family: 'Inter, sans-serif',
                  },
                },
                hovermode: 'closest',
                hoverlabel: {
                  bgcolor: 'rgba(255, 255, 255, 0.95)',
                  bordercolor: '#e5e7eb',
                  font: {
                    size: 13,
                    color: '#1f2937',
                    family: 'Inter, sans-serif',
                  },
                },
                plot_bgcolor: '#ffffff',
                paper_bgcolor: '#ffffff',
                font: {
                  family: 'Inter, sans-serif',
                },
                barmode: 'overlay',
                showlegend: false,
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
            <div className="text-gray-500 text-center">No data available for selected category</div>
          </div>
        )}
      </div>
    </div>
  );
}
