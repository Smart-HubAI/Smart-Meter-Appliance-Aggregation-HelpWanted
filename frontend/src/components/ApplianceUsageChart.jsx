import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

const ApplianceUsageChart = ({ breakdown = {} }) => {
  const data = Object.entries(breakdown)
    .filter(([key]) => !key.startsWith('_'))
    .map(([name, value]) => ({
      name,
      value: Number(value) || 0,
    }));

  if (!data.length) {
    return (
      <div className="text-center text-muted py-5">
        No AI appliance usage data available.
      </div>
    );
  }

  const largeItems = data.filter((item) => item.value >= 5);
  const othersValue = data
    .filter((item) => item.value < 5)
    .reduce((sum, item) => sum + item.value, 0);

  const displayData = [...largeItems];
  if (othersValue > 0) {
    displayData.push({
      name: 'Others',
      value: Number(othersValue.toFixed(1)),
    });
  }

  displayData.sort((a, b) => b.value - a.value);

  return (
    <div style={{ width: '100%', height: 330 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={displayData}
          layout="vertical"
          margin={{ top: 10, right: 40, left: 0, bottom: 10 }}
          barSize={22}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e9ecef" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: '#495057' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            axisLine={false}
            tickLine={false}
            width={170}
            tick={{ fontSize: 12, fill: '#212529', fontWeight: 600 }}
          />
          <Tooltip
            cursor={{ fill: '#f8f9fa' }}
            formatter={(value) => [`${value}%`, 'Usage']}
            itemStyle={{ fontSize: 12 }}
          />
          <Bar
            dataKey="value"
            fill="#0d6efd"
            radius={[0, 10, 10, 0]}
            label={{ position: 'right', fill: '#495057', fontSize: 12, fontWeight: 600 }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ApplianceUsageChart;