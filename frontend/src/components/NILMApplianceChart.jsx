import React, { useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { fmtKwh, fmtPct, fmtConfidence, fmtCurrency, fmtNum } from '../utils/format';

const COLORS = ['#0d47a1', '#1976d2', '#42a5f5', '#00bcd4', '#4db6ac', '#81c784', '#ffb74d', '#ff8a65', '#9575cd'];

const renderActiveShape = (props) => {
  const RADIAN = Math.PI / 180;
  const { cx, cy, midAngle, innerRadius, outerRadius, startAngle, endAngle,
    fill, payload, percent, value, name } = props;
  
  // Custom label rendering with leader lines to prevent overlap
  const sin = Math.sin(-RADIAN * midAngle);
  const cos = Math.cos(-RADIAN * midAngle);
  
  // Leader line coordinates
  const sx = cx + (outerRadius + 5) * cos;
  const sy = cy + (outerRadius + 5) * sin;
  const mx = cx + (outerRadius + 30) * cos;
  const my = cy + (outerRadius + 30) * sin;
  const ex = mx + (cos >= 0 ? 1 : -1) * 30;
  const ey = my;
  const textAnchor = cos >= 0 ? 'start' : 'end';

  if (percent < 0.02) return null; // Avoid clutter for extremely small slices

  return (
    <g>
      {/* Sector */}
      <path d={`M${cx},${cy} L${cx + outerRadius * Math.cos(-RADIAN * startAngle)},${cy + outerRadius * Math.sin(-RADIAN * startAngle)} A${outerRadius},${outerRadius} 0 ${endAngle - startAngle > 180 ? 1 : 0},0 ${cx + outerRadius * Math.cos(-RADIAN * endAngle)},${cy + outerRadius * Math.sin(-RADIAN * endAngle)} Z`} fill={fill} />
      
      {/* Leader line */}
      <path d={`M${sx},${sy}L${mx},${my}L${ex},${ey}`} stroke={fill} strokeWidth={2} fill="none" />
      <circle cx={ex} cy={ey} r={3} fill={fill} stroke="none" />
      
      {/* Permanent Text Label */}
      <text x={ex + (cos >= 0 ? 1 : -1) * 8} y={ey} dy={-4} textAnchor={textAnchor} fill="#333" fontSize={13} fontWeight="700">
        {name}
      </text>
      <text x={ex + (cos >= 0 ? 1 : -1) * 8} y={ey} dy={14} textAnchor={textAnchor} fill="#666" fontSize={12} fontWeight="500">
        {fmtPct(percent * 100)}% ({fmtKwh(value)} kWh)
      </text>
    </g>
  );
};

const NILMApplianceChart = ({ applianceDetails = [] }) => {
  const [activeIndex, setActiveIndex] = useState(null);

  const validData = applianceDetails.filter(app => (app.kwh || 0) > 0);

  if (!validData.length) {
    return <div className="text-center text-muted py-5 my-5 bg-light rounded border">No active appliances detected by NILM.</div>;
  }

  const activeAppliance = activeIndex !== null ? validData[activeIndex] : null;

  return (
    <div className="d-flex flex-column h-100">
      <div style={{ width: '100%', height: 480, position: 'relative' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart margin={{ top: 20, right: 120, bottom: 40, left: 120 }}>
            <Pie
              data={validData}
              cx="50%"
              cy="50%"
              innerRadius={0} // True Pie Chart
              outerRadius={140} // Increased size for full-width layout
              paddingAngle={1}
              dataKey="kwh"
              nameKey="appliance"
              labelLine={false}
              label={renderActiveShape}
              onClick={(_, index) => setActiveIndex(activeIndex === index ? null : index)}
            >
              {validData.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={COLORS[index % COLORS.length]} 
                  style={{ 
                    cursor: 'pointer', 
                    transition: 'all 0.3s ease', 
                    opacity: activeIndex === null || activeIndex === index ? 1 : 0.4,
                    stroke: '#fff',
                    strokeWidth: 2
                  }}
                />
              ))}
            </Pie>
            <Legend 
              verticalAlign="bottom" 
              height={36} 
              iconType="circle" 
              wrapperStyle={{ fontSize: '13px', fontWeight: '500', marginTop: '20px' }} 
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  return (
                    <div className="bg-white p-3 border rounded-3 shadow" style={{ minWidth: '220px' }}>
                      <h6 className="mb-3 fw-bold border-bottom pb-2" style={{ color: payload[0].payload.fill }}>{data.appliance}</h6>
                      <div className="d-flex justify-content-between mb-2">
                        <span className="text-muted small">Energy</span>
                        <span className="fw-bold small">{fmtKwh(data.kwh)} kWh</span>
                      </div>
                      <div className="d-flex justify-content-between mb-2">
                        <span className="text-muted small">Contribution</span>
                        <span className="fw-bold small">{fmtPct(data.pct)}%</span>
                      </div>
                      <div className="d-flex justify-content-between">
                        <span className="text-muted small">Confidence</span>
                        <span className={`badge ${data.confidence >= 0.8 ? 'bg-success' : 'bg-warning text-dark'}`}>
                          {fmtConfidence(data.confidence)}
                        </span>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      
      {activeAppliance && (
        <div className="mt-3 p-3 bg-light rounded-3 border animation-fade-in shadow-sm">
          <h6 className="fw-bold mb-3 d-flex align-items-center text-primary">
            <i className="bi bi-info-circle-fill me-2"></i>
            {activeAppliance.appliance} Intelligence
          </h6>
          <div className="row g-3">
            <div className="col-6 col-md-4">
              <small className="text-muted d-block mb-1">Est. Energy</small>
              <div className="fw-bold">{fmtKwh(activeAppliance.kwh)} kWh</div>
            </div>
            <div className="col-6 col-md-4">
              <small className="text-muted d-block mb-1">Est. Cost</small>
              <div className="fw-bold text-success">{fmtCurrency(activeAppliance.est_monthly_cost_inr, 0)}</div>
            </div>
            <div className="col-6 col-md-4">
              <small className="text-muted d-block mb-1">Model Used</small>
              <div className="fw-bold">{activeAppliance.model_used || 'Ground Truth'}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NILMApplianceChart;
