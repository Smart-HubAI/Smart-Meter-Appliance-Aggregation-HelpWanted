import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, AreaChart, Area, LabelList, ReferenceDot
} from "recharts";
import { fmtNum } from "../utils/format";

function tooltipKwh(v) { return `${fmtNum(v)} kWh`; }
function tooltipNum(v) { return fmtNum(v); }

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white p-3 border rounded shadow-sm" style={{ minWidth: '220px' }}>
        <h6 className="fw-bold mb-2 pb-1 border-bottom">{data.label}</h6>
        <div className="d-flex justify-content-between mb-1">
          <span className="text-muted small">Consumption:</span> 
          <span className="fw-semibold">{fmtNum(data.value)} kWh</span>
        </div>
        {data.diff_pct !== undefined && (
          <div className="d-flex justify-content-between mb-1">
            <span className="text-muted small">Trend:</span> 
            <span className={`fw-semibold ${data.diff_pct > 0 ? 'text-danger' : data.diff_pct < 0 ? 'text-success' : 'text-muted'}`}>
              {data.diff_pct > 0 ? '↑' : data.diff_pct < 0 ? '↓' : ''} {Math.abs(data.diff_pct)}%
            </span>
          </div>
        )}
        {data.top_appliance && (
          <div className="d-flex justify-content-between mb-1">
            <span className="text-muted small">Top Appliance:</span> 
            <span className="fw-semibold text-truncate ms-2" style={{maxWidth: '120px'}}>{data.top_appliance}</span>
          </div>
        )}
        {data.estimated_cost !== undefined && (
          <div className="d-flex justify-content-between">
            <span className="text-muted small">Est. Cost:</span> 
            <span className="fw-semibold">₹{data.estimated_cost}</span>
          </div>
        )}
      </div>
    );
  }
  return null;
};

export function TrendLineChart({ labels = [], values = [], details = [], color = "#0d47a1" }) {
  const data = labels.map((label, i) => ({ 
    label, 
    value: values[i] ?? 0,
    ...(details?.[i] || {})
  }));
  
  if (!data.length) return null;

  let maxVal = -Infinity, minVal = Infinity;
  let maxLabel = "", minLabel = "";
  
  data.forEach(d => {
    if (d.value > maxVal) { maxVal = d.value; maxLabel = d.label; }
    if (d.value < minVal) { minVal = d.value; minLabel = d.label; }
  });

  const latest = data[data.length - 1];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 30, right: 30, left: 10, bottom: 20 }}>
        <defs>
          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.6}/>
            <stop offset="95%" stopColor={color} stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} horizontal={true} stroke="#f0f0f0" />
        <XAxis dataKey="label" tick={{ fontSize: 13, fill: '#666', fontWeight: 500 }} interval="preserveStartEnd" dy={15} tickLine={false} axisLine={{ stroke: '#e0e0e0', strokeWidth: 2 }} tickMargin={10} />
        <YAxis tick={{ fontSize: 13, fill: '#666', fontWeight: 500 }} dx={-10} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={fmtNum} />
        <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#adb5bd', strokeWidth: 1, strokeDasharray: '4 4' }} />
        <Area type="monotone" dataKey="value" stroke={color} strokeWidth={4} fillOpacity={1} fill="url(#colorValue)" activeDot={{ r: 7, fill: color, stroke: '#fff', strokeWidth: 2 }} />
        
        {maxLabel && <ReferenceDot x={maxLabel} y={maxVal} r={6} fill="#dc3545" stroke="#fff" strokeWidth={2.5} />}
        {minLabel && <ReferenceDot x={minLabel} y={minVal} r={6} fill="#198754" stroke="#fff" strokeWidth={2.5} />}
        {latest && <ReferenceDot x={latest.label} y={latest.value} r={6} fill="#0dcaf0" stroke="#fff" strokeWidth={2.5} />}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function RankingsBarChart({ labels = [], values = [] }) {
  const data = labels.slice(0, 15).map((label, i) => ({ label, value: values[i] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} layout="vertical" margin={{ top: 20, right: 60, left: 120, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e0e0e0" />
        <XAxis type="number" tick={{ fontSize: 14, fill: '#555' }} dy={10} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="label" tick={{ fontSize: 14, fill: '#333', fontWeight: 500 }} width={110} dx={-10} tickLine={false} axisLine={{ stroke: '#ccc' }} />
        <Tooltip formatter={tooltipNum} wrapperStyle={{ fontSize: 14 }} cursor={{ fill: '#f5f5f5' }} />
        <Bar dataKey="value" fill="#0d47a1" radius={[0, 4, 4, 0]} barSize={32}>
          <LabelList dataKey="value" position="right" fontSize={13} fontWeight="bold" fill="#555" formatter={(v) => fmtNum(v)} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Monthly energy trend (area chart)
export function MonthlyTrendChart({ labels = [], values = [] }) {
  const data = labels.map((label, i) => ({ label, value: values[i] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={450}>
      <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <defs>
          <linearGradient id="colorKwh" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#1565c0" stopOpacity={0.8} />
            <stop offset="95%" stopColor="#1565c0" stopOpacity={0.1} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
        <XAxis dataKey="label" tick={{ fontSize: 16, fill: '#333', fontWeight: 500 }} interval="preserveStartEnd" dy={15} tickLine={false} axisLine={{ stroke: '#ccc' }} />
        <YAxis tick={{ fontSize: 14, fill: '#555' }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} dx={-10} tickLine={false} axisLine={false} />
        <Tooltip formatter={tooltipKwh} wrapperStyle={{ fontSize: 16 }} cursor={{ stroke: '#e0e0e0', strokeWidth: 2 }} />
        <Area type="monotone" dataKey="value" stroke="#1565c0" fillOpacity={1} fill="url(#colorKwh)" strokeWidth={4} activeDot={{ r: 6 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// Daily load curve (line chart with dots)
export function DailyLoadChart({ labels = [], values = [] }) {
  const data = labels.map((label, i) => ({ label, value: values[i] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
        <XAxis dataKey="label" tick={{ fontSize: 14, fill: '#555' }} interval="preserveStartEnd" dy={10} tickLine={false} axisLine={{ stroke: '#ccc' }} />
        <YAxis tick={{ fontSize: 14, fill: '#555' }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} dx={-10} tickLine={false} axisLine={false} />
        <Tooltip formatter={tooltipKwh} wrapperStyle={{ fontSize: 14 }} cursor={{ stroke: '#e0e0e0', strokeWidth: 2 }} />
        <Line type="monotone" dataKey="value" stroke="#2e7d32" strokeWidth={3} dot={{ r: 4, fill: '#2e7d32', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

const PIE_COLORS = ["#1565c0", "#2e7d32", "#ef6c00", "#c62828", "#6a1b9a", "#00838f", "#f9a825", "#455a64"];

const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, name }) => {
  if (percent < 0.05) return null;
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * (Math.PI / 180));
  const y = cy + radius * Math.sin(-midAngle * (Math.PI / 180));

  return (
    <text x={x} y={y} fill="white" fontSize={14} fontWeight="bold" textAnchor="middle" dominantBaseline="central">
      {`${(percent * 100).toFixed(1)}%`}
    </text>
  );
};

// Pie chart for category/appliance distribution
export function DistributionPieChart({ data = [], dataKey = "name", valueKey = "value" }) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <PieChart margin={{ top: 20, right: 20, bottom: 40, left: 20 }}>
        <Pie 
          data={data} 
          dataKey={valueKey} 
          nameKey={dataKey} 
          cx="50%" 
          cy="45%" 
          outerRadius={150} 
          label={renderCustomizedLabel}
          labelLine={false}
          stroke="#fff"
          strokeWidth={2}
        >
          {data.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
        </Pie>
        <Tooltip formatter={tooltipNum} wrapperStyle={{ fontSize: 14 }} />
        <Legend iconSize={12} wrapperStyle={{ fontSize: 14, paddingTop: '20px', lineHeight: '24px' }} verticalAlign="bottom" align="center" />
      </PieChart>
    </ResponsiveContainer>
  );
}

// Horizontal bar chart for zone/top consumers
export function HorizontalBarChart({ data = [], dataKey = "name", valueKey = "value", color = "#1565c0" }) {
  if (!data || !data.length) return <div className="text-muted p-3">No data available</div>;
  
  const sliced = [...data].sort((a, b) => b[valueKey] - a[valueKey]).slice(0, 10);
  const total = sliced.reduce((sum, item) => sum + (Number(item[valueKey]) || 0), 0);
  const max = Math.max(...sliced.map(item => Number(item[valueKey]) || 0));

  return (
    <div className="d-flex flex-column justify-content-center w-100" style={{ minHeight: '400px', paddingRight: '10px' }}>
      {sliced.map((item, index) => {
        const val = Number(item[valueKey]) || 0;
        const pctOfMax = max > 0 ? (val / max) * 100 : 0;
        const pctOfTotal = total > 0 ? (val / total) * 100 : 0;
        return (
          <div key={index} className="mb-4">
            <div className="d-flex justify-content-between align-items-end mb-2">
              <span className="fw-bold text-dark fs-6">{item[dataKey]}</span>
              <span className="fw-bold text-dark">{val.toFixed(1)} kWh <span className="text-muted fw-normal ms-1">({pctOfTotal.toFixed(1)}%)</span></span>
            </div>
            <div className="progress" style={{ height: '18px', borderRadius: '10px', backgroundColor: '#e9ecef' }}>
              <div 
                className="progress-bar" 
                role="progressbar" 
                style={{ width: `${pctOfMax}%`, backgroundColor: color, borderRadius: '10px' }}
                aria-valuenow={pctOfMax} 
                aria-valuemin="0" 
                aria-valuemax="100"
                title={`${item[dataKey]}: ${val.toFixed(1)} kWh`}
              ></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Simple trend chart for anomaly/tamper trends
export function SimpleTrendChart({ labels = [], values = [], color = "#c62828" }) {
  const data = labels.map((label, i) => ({ label, value: values[i] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart data={data} margin={{ top: 20, right: 20, left: 20, bottom: 20 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
        <XAxis dataKey="label" tick={{ fontSize: 14, fill: '#555' }} interval="preserveStartEnd" dy={10} tickLine={false} axisLine={{ stroke: '#ccc' }} />
        <YAxis tick={{ fontSize: 14, fill: '#555' }} dx={-10} tickLine={false} axisLine={false} />
        <Tooltip formatter={tooltipNum} wrapperStyle={{ fontSize: 14 }} cursor={{ fill: '#f5f5f5' }} />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} barSize={40}>
          <LabelList dataKey="value" position="top" fontSize={13} fontWeight="bold" fill="#555" dy={-5} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
