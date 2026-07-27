/**
 * Chart.js visualization helpers for Smart Meter Analytics Platform
 */

const ChartDefaults = {
  primary: "#0d47a1",
  accent: "#ff6f00",
  palette: ["#0d47a1", "#1976d2", "#ff6f00", "#2e7d32", "#7b1fa2", "#00838f"],
};

/**
 * Destroy existing chart instance on canvas if present
 */
function destroyChart(chartInstance) {
  if (chartInstance) {
    chartInstance.destroy();
  }
}

/**
 * Line chart for consumption trends
 */
function createLineChart(canvasId, labels, values, label = "kWh") {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: label,
          data: values,
          borderColor: ChartDefaults.primary,
          backgroundColor: "rgba(13, 71, 161, 0.1)",
          fill: true,
          tension: 0.35,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: "kWh" } },
      },
    },
  });
}

/**
 * Bar chart for weekly/monthly comparisons
 */
function createBarChart(canvasId, labels, values, color = ChartDefaults.accent) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;

  return new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Consumption (kWh)",
          data: values,
          backgroundColor: color,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

/**
 * Interactive doughnut chart for NILM Appliance Breakdown
 */
function createInteractiveNILMChart(canvasId, applianceData) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !applianceData || !applianceData.labels) return null;

  // Filter out zero-prediction appliances
  const filteredLabels = [];
  const filteredValues = [];
  const filteredDetails = [];
  
  for (let i = 0; i < applianceData.labels.length; i++) {
    if (applianceData.values[i] > 0) {
      filteredLabels.push(applianceData.labels[i]);
      filteredValues.push(applianceData.values[i]);
      if (applianceData.details) {
        // Find matching detail object
        const detail = applianceData.details.find(d => d.appliance === applianceData.labels[i]);
        filteredDetails.push(detail || {});
      }
    }
  }

  // Set up custom tooltips
  const tooltipOptions = {
    callbacks: {
      label: function(context) {
        const detail = filteredDetails[context.dataIndex];
        const val = context.parsed || 0;
        const conf = detail && detail.confidence ? Math.round(detail.confidence * 100) : 80;
        return ` ${val.toFixed(1)}% | Conf: ${conf}%`;
      }
    }
  };

  const chart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: filteredLabels,
      datasets: [
        {
          data: filteredValues,
          backgroundColor: ChartDefaults.palette,
          borderWidth: 2,
          borderColor: "#ffffff",
          hoverOffset: 4
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        animateScale: true,
        animateRotate: true
      },
      plugins: {
        legend: { position: "right" },
        tooltip: tooltipOptions
      },
      onClick: (event, elements) => {
        if (elements.length > 0) {
          const idx = elements[0].index;
          const detail = filteredDetails[idx];
          if (detail) {
            updateNILMPanel(detail);
          }
        }
      }
    },
  });

  return chart;
}

function updateNILMPanel(detail) {
  document.getElementById('applianceDetailPrompt').style.display = 'none';
  document.getElementById('applianceDetailPanel').style.display = 'block';

  document.getElementById('panelAppName').innerHTML = `<i class="bi bi-plugin"></i> ${detail.appliance}`;
  const conf = Math.round((detail.confidence || 0.8) * 100);
  document.getElementById('panelAppConf').textContent = `${conf}% Confidence`;
  document.getElementById('panelAppKwh').textContent = `${detail.kwh || 0} kWh`;
  document.getElementById('panelAppPct').textContent = `(${detail.pct || 0}%)`;
  document.getElementById('panelAppCost').textContent = `₹${detail.est_monthly_cost_inr || 0}`;
  document.getElementById('panelAppCarbon').textContent = `${detail.carbon_emissions_kg || 0} kgCO2`;
  
  document.getElementById('panelAppReasoning').textContent = detail.reasoning_summary || "Detected via NILM temporal features.";
  document.getElementById('panelAppModel').textContent = `Model: ${detail.model_used || "TemporalEnsemble"}`;
  document.getElementById('panelAppHours').textContent = `Typical Hours: ${detail.operating_hours || "N/A"}`;
  
  const featsContainer = document.getElementById('panelAppFeatures');
  featsContainer.innerHTML = '';
  if (detail.important_features && Object.keys(detail.important_features).length > 0) {
    Object.entries(detail.important_features)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .forEach(([feat, val]) => {
        featsContainer.innerHTML += `<span class="badge bg-light text-dark border border-secondary" style="font-size: 0.7rem;">${feat}: ${(val*100).toFixed(1)}%</span>`;
    });
  } else {
    featsContainer.innerHTML = '<span class="text-muted small">N/A</span>';
  }
}

/**
 * Peak demand hours bar chart (admin)
 */
function createPeakChart(canvasId, labels, values) {
  return createBarChart(canvasId, labels, values, ChartDefaults.primary);
}

/**
 * Initialize all consumer dashboard charts from embedded JSON
 */
function initConsumerCharts(chartData) {
  const charts = [];
  if (!chartData) return charts;

  if (chartData.daily) {
    charts.push(
      createLineChart(
        "chartDaily",
        chartData.daily.labels,
        chartData.daily.values,
        "Daily kWh"
      )
    );
  }
  if (chartData.weekly) {
    charts.push(
      createBarChart(
        "chartWeekly",
        chartData.weekly.labels,
        chartData.weekly.values
      )
    );
  }
  if (chartData.monthly) {
    charts.push(
      createLineChart(
        "chartMonthly",
        chartData.monthly.labels,
        chartData.monthly.values,
        "Monthly kWh"
      )
    );
  }
  if (chartData.appliance) {
    charts.push(
      createInteractiveNILMChart(
        "chartApplianceInteractive",
        chartData.appliance
      )
    );
  }
  return charts;
}

/**
 * Initialize admin dashboard charts
 */
function initAdminCharts(chartData) {
  const charts = [];
  if (!chartData) return charts;

  if (chartData.peak_hours) {
    charts.push(
      createPeakChart(
        "chartPeakHours",
        chartData.peak_hours.labels,
        chartData.peak_hours.values
      )
    );
  }
  if (chartData.rankings) {
    charts.push(
      createBarChart(
        "chartRankings",
        chartData.rankings.labels,
        chartData.rankings.values,
        ChartDefaults.accent
      )
    );
  }
  return charts;
}

/**
 * Render simple CSS heatmap for consumption patterns
 */
function renderHeatmap(containerId, heatmapData) {
  const container = document.getElementById(containerId);
  if (!container || !heatmapData || !heatmapData.values) return;

  const { hours, days, values } = heatmapData;
  const flat = values.flat();
  const maxVal = Math.max(...flat, 0.001);

  let html = '<div class="heatmap-grid">';
  html += '<div></div>';
  hours.forEach((h) => {
    html += `<div class="text-center text-muted">${h}</div>`;
  });

  days.forEach((day, dow) => {
    html += `<div class="fw-bold small">${day}</div>`;
    for (let h = 0; h < 24; h++) {
      const val = values[dow] ? values[dow][h] : 0;
      const intensity = val / maxVal;
      const r = Math.round(13 + intensity * 200);
      const g = Math.round(71 + intensity * 100);
      const b = Math.round(161 - intensity * 50);
      html += `<div class="heatmap-cell" title="${day} ${h}:00 - ${val} kW" 
        style="background: rgb(${r},${g},${b})"></div>`;
    }
  });
  html += "</div>";
  container.innerHTML = html;
}

// Export for module environments (optional)
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    initConsumerCharts,
    initAdminCharts,
    renderHeatmap,
    createLineChart,
    createBarChart,
    createInteractiveNILMChart,
  };
}
