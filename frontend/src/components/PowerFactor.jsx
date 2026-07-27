import React from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const getStatus = (pf) => {
  if (pf >= 0.90) return 'Excellent';
  if (pf >= 0.80) return 'Warning';
  return 'Critical';
};

const getStatusColorHex = (pf) => {
  // GREEN PF >= 0.90 Status Excellent
  // YELLOW 0.80 <= PF < 0.90 Status Warning
  // RED PF < 0.80 Status Critical
  if (pf >= 0.90) return '#4CAF50'; // Green
  if (pf >= 0.80) return '#FFC107'; // Yellow
  return '#F44336'; // Red
};

const thresholdBandsPlugin = {
  id: 'thresholdBands',
  beforeDraw: (chart) => {
    const { ctx, chartArea: { top, bottom, left, right }, scales: { y } } = chart;
    ctx.save();
    
    const drawBand = (yMin, yMax, color) => {
      // Ensure we don't go outside the chart area
      const maxY = Math.min(yMax, y.max);
      const minY = Math.max(yMin, y.min);
      if (minY >= maxY) return;

      const startY = y.getPixelForValue(maxY);
      const endY = y.getPixelForValue(minY);
      
      ctx.fillStyle = color;
      ctx.fillRect(left, startY, right - left, endY - startY);
    };

    // Green: 0.90 - 1.00
    drawBand(0.90, 1.00, 'rgba(76, 175, 80, 0.2)');
    // Yellow: 0.80 - 0.90
    drawBand(0.80, 0.90, 'rgba(255, 193, 7, 0.2)');
    // Red: 0.00 - 0.80
    drawBand(0.00, 0.80, 'rgba(244, 67, 54, 0.2)');

    ctx.restore();
  }
};

export function PowerFactorChart({ readings }) {
  const labels = readings.map(r => r.time_label);
  const dataPoints = readings.map(r => r.power_factor);

  const data = {
    labels,
    datasets: [
      {
        label: 'Power Factor',
        data: dataPoints,
        borderColor: 'rgba(54, 162, 235, 1)', // Blue line
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        tension: 0.4, // smooth curve
        fill: false,
        pointRadius: 0,
        pointHoverRadius: 6,
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          title: function(context) {
            return context[0].label;
          },
          label: function(context) {
            const val = context.parsed.y;
            return `Power Factor: ${val.toFixed(2)}`;
          },
          afterLabel: function(context) {
            const val = context.parsed.y;
            return `Status: ${getStatus(val)}`;
          }
        }
      },
      thresholdBands: {}
    },
    scales: {
      x: {
        grid: {
          display: false
        }
      },
      y: {
        min: 0,
        max: 1.0,
      }
    },
    interaction: {
      mode: 'index',
      intersect: false,
    },
  };

  return (
    <div style={{ height: '400px', width: '100%' }}>
      <Line data={data} options={options} plugins={[thresholdBandsPlugin]} />
    </div>
  );
}

export function PowerFactorGauge({ averagePf }) {
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  
  // Calculate stroke dashoffset ensuring it's bounded
  const pf = Math.max(0, Math.min(1, averagePf || 0));
  const strokeDashoffset = circumference - (pf * circumference);
  
  const color = getStatusColorHex(pf);
  const status = getStatus(pf);

  return (
    <div className="d-flex flex-column align-items-center justify-content-center p-3">
      <div style={{ position: 'relative', width: '120px', height: '120px' }}>
        <svg viewBox="0 0 120 120" width="120" height="120">
          <circle
            cx="60" cy="60" r={radius}
            fill="none" stroke="#f0f0f0" strokeWidth="10"
          />
          <circle
            cx="60" cy="60" r={radius}
            fill="none" stroke={color} strokeWidth="10"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            transform="rotate(-90 60 60)"
            style={{ transition: 'stroke-dashoffset 1s ease-in-out' }}
          />
        </svg>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
          <div className="fs-4 fw-bold">{pf.toFixed(2)}</div>
        </div>
      </div>
      <div className="mt-2 text-center">
        <span className="fw-bold px-3 py-1 rounded-pill" style={{ backgroundColor: color + '33', color: '#333' }}>
          {status}
        </span>
      </div>
    </div>
  );
}
