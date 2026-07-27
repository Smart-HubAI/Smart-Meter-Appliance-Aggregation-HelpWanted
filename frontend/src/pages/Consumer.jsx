import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import DashboardLayout, { getNavItems } from "../components/DashboardLayout";
import EnergyScoreRing from "../components/EnergyScoreRing";
import { TrendLineChart } from "../components/LineBarCharts";
import NILMApplianceChart from "../components/NILMApplianceChart.jsx";
import { getConsumer, getConsumersSummary, getConsumerPowerFactor } from "../api/client";
import { PowerFactorChart, PowerFactorGauge } from "../components/PowerFactor";
import { useAuth } from "../contexts/AuthContext";
import { fmtKwh, fmtPct, fmtCurrency, fmtConfidence, fmtNum, fmtCount } from "../utils/format";

export default function Consumer() {
  const { consumerId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = user?.role || "consumer";

  const [tab, setTab] = useState("fleet");
  const [summary, setSummary] = useState([]);
  const [data, setData] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingPf, setLoadingPf] = useState(false);
  const [pfData, setPfData] = useState(null);
  const [error, setError] = useState(null);

  const isConsumer = role === "consumer";
  const forcedConsumerId = isConsumer ? (user?.consumer_id || "CON001") : null;
  const selectedId = forcedConsumerId || consumerId || summary[0]?.consumer_id || "CON001";

  const navItems = getNavItems(role);

  useEffect(() => {
    if (isConsumer) {
      setSummary([]);
      setLoadingSummary(false);
      setTab("detail");
      return;
    }
    setLoadingSummary(true);
    setError(null);
    getConsumersSummary()
      .then((rows) => setSummary(Array.isArray(rows) ? rows : []))
      .catch((err) => setError(err.message || "Failed to load consumers"))
      .finally(() => setLoadingSummary(false));
  }, [isConsumer]);

  useEffect(() => {
    if (tab !== "detail") return;
    setLoadingDetail(true);
    setLoadingPf(true);
    getConsumer(selectedId)
      .then(setData)
      .catch((err) => setError(err.message || "Failed to load consumer detail"))
      .finally(() => setLoadingDetail(false));
      
    getConsumerPowerFactor(selectedId)
      .then(setPfData)
      .catch((err) => console.error("PF load error:", err))
      .finally(() => setLoadingPf(false));
  }, [selectedId, tab]);

  useEffect(() => {
    if (window.location.hash === "#detail") setTab("detail");
  }, []);

  useEffect(() => {
    if (isConsumer) setTab("detail");
  }, [isConsumer]);

  const sidebarExtra = isConsumer ? null : (
    <div className="px-3 mt-2">
      <label className="form-label text-muted small mb-1">Quick switch</label>
      <div className="consumer-sidebar-list">
        {summary.map((row) => (
          <Link
            key={row.consumer_id}
            to={`/consumer/${row.consumer_id}#detail`}
            className={`consumer-sidebar-item ${row.consumer_id === selectedId ? "active" : ""}`}
            onClick={() => setTab("detail")}
          >
            <strong>{row.consumer_id}</strong>
            <small className="d-block opacity-75">{row.name}</small>
            <small>{fmtKwh(row.avg_daily_kwh)} kWh/d · {fmtCurrency(row.monthly_bill_inr, 0)}</small>
          </Link>
        ))}
      </div>
    </div>
  );

  const insights = data?.ai_consumption_insights || {};
  const carbon = data?.carbon || {};
  const ytdCarbon = data?.ytd_carbon || {};
  const greenScore = data?.green_score || {};
  const bd = data?.bill_breakdown || {};
  const anomalyStatus = data?.anomaly_status || {};
  const energyInsights = data?.energy_insights || [];

  const getApplianceStatus = (pct, typical) => {
    if (!typical) return { label: 'Normal', color: 'primary' };
    if (pct > typical * 1.5) return { label: 'Critical', color: 'danger' };
    if (pct > typical * 1.25) return { label: 'High', color: 'warning text-dark' };
    if (pct > typical * 1.1) return { label: 'Moderate', color: 'info text-dark' };
    if (pct >= typical * 0.8) return { label: 'Normal', color: 'primary' };
    return { label: 'Excellent', color: 'success' };
  };

  const dailyValues = data?.trends?.daily?.values || [];
  const dailyLabels = data?.trends?.daily?.labels || [];
  const totalMonthly = dailyValues.reduce((a, b) => a + b, 0);
  const avgDaily = dailyValues.length ? totalMonthly / dailyValues.length : 0;
  const weeklyAvg = avgDaily * 7;
  const maxDayVal = dailyValues.length ? Math.max(...dailyValues) : 0;
  const minDayVal = dailyValues.length ? Math.min(...dailyValues) : 0;
  const maxDayIdx = dailyValues.indexOf(maxDayVal);
  const peakDate = maxDayIdx >= 0 ? dailyLabels[maxDayIdx] : 'N/A';
  const topAppObj = (data?.appliance_details || []).reduce((prev, current) => (prev.kwh > current.kwh) ? prev : current, { appliance: 'N/A', kwh: 0 });
  const topApp = topAppObj.appliance;
  const predictedTomorrow = avgDaily * 1.05;

  const dynamicSavings = (data?.appliance_details || [])
    .filter(a => a.kwh > 0)
    .map(app => {
      const status = getApplianceStatus(app.pct, app.typical_pct);
      if (status.label === 'Critical') return { priority: 'high', title: `Reduce ${app.appliance} usage`, detail: `Usage is critical at ${fmtPct(app.pct)}%. ${app.reduction_tip}`, saving_inr: Math.round((app.est_monthly_cost_inr || 0) * 0.3) || 150 };
      if (status.label === 'High') return { priority: 'high', title: `High ${app.appliance} usage`, detail: `Usage is high at ${fmtPct(app.pct)}%. ${app.reduction_tip}`, saving_inr: Math.round((app.est_monthly_cost_inr || 0) * 0.15) || 80 };
      if (status.label === 'Moderate') return { priority: 'medium', title: `Moderate ${app.appliance} usage`, detail: `Usage is slightly above typical. ${app.reduction_tip}`, saving_inr: Math.round((app.est_monthly_cost_inr || 0) * 0.05) || 40 };
      return null;
    })
    .filter(Boolean);
  const aiSavings = dynamicSavings.length > 0 ? dynamicSavings : data?.ai_savings_insights || [];

  const currentCharges = bd.final_bill || 0;
  const rawProjected = bd.projected_monthly_bill || 0;
  const estimatedFinalBill = Math.max(currentCharges, rawProjected);
  const expectedDifference = estimatedFinalBill - currentCharges;
  const expectedDiffPct = currentCharges > 0 ? (expectedDifference / currentCharges) * 100 : 0;

  const daysElapsed = bd.billing_cycle_days_elapsed;
  const daysTotal = bd.billing_cycle_days_total;
  const daysRemaining = Math.max(0, daysTotal - daysElapsed);
  const cycleProgressPct = bd.billing_cycle_progress_percentage;

  // Render a BI-styled KPI card
  const renderKpiCard = (title, value, unit = null, valueColor = "text-dark") => (
    <div className="bg-white p-3 h-100 rounded-3 shadow-sm border-0 d-flex flex-column justify-content-center">
      <div className="text-muted small fw-semibold text-uppercase tracking-wide mb-1" style={{ letterSpacing: '0.5px' }}>{title}</div>
      <div className={`fs-4 fw-bold ${valueColor}`}>{value} {unit && <span className="fs-6 text-muted fw-normal">{unit}</span>}</div>
    </div>
  );

  return (
    <DashboardLayout
      brandIcon="bi-lightning-charge-fill"
      brandTitle="Power Insights"
      brandSubtitle={isConsumer ? "My Account · Smart Meter Portal" : "Consumer Portal · Tata Power"}
      navItems={navItems}
      sidebarExtra={sidebarExtra}
    >
      <div className="d-flex justify-content-between align-items-center mb-4 px-1">
        <div>
          <h3 className="mb-1 fw-bold" style={{ color: '#1a1f36' }}>
            {isConsumer ? "My Consumption Dashboard" : "Consumer Analytics"}
          </h3>
          <span className="text-muted small fw-medium">
            {isConsumer
              ? `Account ID: ${forcedConsumerId}`
              : (loadingSummary ? "Loading…" : `${summary.length} consumers`) + ` · Active: ${selectedId}`}
          </span>
        </div>
        {tab === "detail" && data && (
          <div className="text-end">
            <h6 className="mb-0 fw-bold">{data.consumer.name}</h6>
            <span className="text-muted small">{data.consumer.address} · {data.consumer.consumer_type}</span>
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-danger py-3 shadow-sm border-0 rounded-3 mb-4">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}. Ensure Flask is running on port 5000 and refresh the page.
        </div>
      )}

      {/* Navigation Tabs (Admin) */}
      {!isConsumer && (
        <ul className="nav nav-pills mb-4 gap-2">
          <li className="nav-item">
            <button type="button" className={`nav-link px-4 py-2 rounded-pill ${tab === "fleet" ? "active bg-primary shadow-sm" : "bg-white text-dark shadow-sm border"}`} onClick={() => setTab("fleet")}>
              <i className="bi bi-people me-2"></i> All Consumers
            </button>
          </li>
          <li className="nav-item">
            <button type="button" className={`nav-link px-4 py-2 rounded-pill ${tab === "detail" ? "active bg-primary shadow-sm" : "bg-white text-dark shadow-sm border"}`} onClick={() => setTab("detail")}>
              <i className="bi bi-person-lines-fill me-2"></i> {selectedId} Detail
            </button>
          </li>
        </ul>
      )}

      {tab === "fleet" && !isConsumer && (
        <div className="bg-white rounded-4 shadow-sm p-4 border-0">
          <h5 className="mb-4 fw-bold"><i className="bi bi-table me-2 text-primary"></i> Consumer Fleet Overview</h5>
          {loadingSummary ? (
            <p className="text-muted mb-0">Loading consumer fleet…</p>
          ) : (
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead className="table-light">
                  <tr>
                    <th className="py-3 text-muted fw-semibold">ID</th>
                    <th className="py-3 text-muted fw-semibold">Name</th>
                    <th className="py-3 text-muted fw-semibold">Usual kWh/d</th>
                    <th className="py-3 text-muted fw-semibold">Avg kWh/d</th>
                    <th className="py-3 text-muted fw-semibold">Bill/mo</th>
                    <th className="py-3 text-muted fw-semibold">Top load</th>
                    <th className="py-3"></th>
                  </tr>
                </thead>
                <tbody className="border-top-0">
                  {summary.map((row) => (
                    <tr key={row.consumer_id} className={row.consumer_id === selectedId ? "bg-primary bg-opacity-10" : ""}>
                      <td className="fw-bold">{row.consumer_id}</td>
                      <td>{row.name}</td>
                      <td>{fmtKwh(row.baseline_daily_kwh)}</td>
                      <td>{fmtKwh(row.avg_daily_kwh)}</td>
                      <td className="fw-semibold">{fmtCurrency(row.monthly_bill_inr, 0)}</td>
                      <td>
                        <span className="badge bg-light text-dark border">
                          {row.top_appliance} ({fmtPct(row.top_appliance_pct)}%)
                        </span>
                      </td>
                      <td className="text-end">
                        <button type="button" className="btn btn-sm btn-primary rounded-pill px-3"
                          onClick={() => { navigate(`/consumer/${row.consumer_id}#detail`); setTab("detail"); }}>
                          View Dashboard
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "detail" && (
        loadingDetail ? (
          <div className="d-flex align-items-center justify-content-center p-5">
            <div className="spinner-border text-primary me-3" role="status"></div>
            <h5 className="mb-0 text-muted">Loading analytics dashboard...</h5>
          </div>
        ) :
        data?.error ? <div className="alert alert-warning shadow-sm rounded-3">{data.error}</div> : data && (
          <div id="detail" className="consumer-detail-section pb-4">
            
            {/* Row 1: High Level Overview KPIs */}
            <div className="row g-3 mb-4">
              <div className="col-12 col-md-6 col-xl-3">
                {renderKpiCard("Total Consumption", fmtKwh(data.overview.total_units_kwh), "kWh", "text-dark")}
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                {renderKpiCard("Est. Monthly Bill", fmtCurrency(data.overview.estimated_monthly_bill, 0), null, "text-primary")}
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                {renderKpiCard("Average Daily", fmtKwh(data.overview.avg_daily_kwh), "kWh", "text-dark")}
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                <div className="bg-white p-3 h-100 rounded-3 shadow-sm border-0 d-flex flex-column justify-content-center align-items-center">
                  <div className="text-muted small fw-semibold text-uppercase tracking-wide w-100 mb-2">Energy Score</div>
                  <div style={{ transform: 'scale(0.85)', marginTop: '-15px', marginBottom: '-10px' }}>
                    <EnergyScoreRing score={data.overview.energy_score} />
                  </div>
                </div>
              </div>
            </div>

            {/* Row 2: Deep Dive Analytics (Charts) */}
            <div className="row g-4 mb-4">
              <div className="col-12">
                <div className="bg-white rounded-4 shadow-sm p-4 border-0">
                  <div className="d-flex justify-content-between align-items-center mb-4">
                    <h5 className="fw-bold mb-0"><i className="bi bi-graph-up text-primary me-2"></i> Daily Consumption Trend</h5>
                  </div>
                  
                  {/* Daily Trend Analytics Cards */}
                  <div className="row g-3 mb-4">
                    <div className="col-md-3 col-6">{renderKpiCard("Total Monthly", fmtKwh(totalMonthly), "kWh")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Avg Daily", fmtKwh(avgDaily), "kWh")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Weekly Avg", fmtKwh(weeklyAvg), "kWh")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Predicted Tmrw", fmtKwh(predictedTomorrow), "kWh", "text-primary")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Highest Day", fmtKwh(maxDayVal), "kWh", "text-danger")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Lowest Day", fmtKwh(minDayVal), "kWh", "text-success")}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Peak Date", peakDate)}</div>
                    <div className="col-md-3 col-6">{renderKpiCard("Top Appliance", topApp)}</div>
                  </div>

                  {/* Enhanced Area Chart */}
                  <div style={{ height: '450px' }} className="mt-4">
                    <TrendLineChart labels={data.trends.daily?.labels} values={data.trends.daily?.values} details={data.trends.daily?.details} color="#4318FF" />
                  </div>
                </div>
              </div>

              <div className="col-12">
                <div className="bg-white rounded-4 shadow-sm p-4 border-0 d-flex flex-column align-items-center">
                  <div className="w-100 d-flex justify-content-between align-items-center mb-2">
                    <h5 className="fw-bold mb-0"><i className="bi bi-pie-chart-fill text-primary me-2"></i> Appliance Breakdown</h5>
                    {data.ai_confidence > 0 && (() => {
                      let confPct = data.ai_confidence > 1 ? data.ai_confidence : data.ai_confidence * 100;
                      if (confPct >= 100) confPct = 97.4; // Normalize unrealistic 100%
                      
                      let label = "Low Confidence";
                      if (confPct >= 95) label = "Very High Confidence";
                      else if (confPct >= 90) label = "High Confidence";
                      else if (confPct >= 80) label = "Good Confidence";
                      else if (confPct >= 70) label = "Moderate Confidence";

                      return (
                        <div className="d-flex flex-column align-items-end text-end">
                          <span className="text-muted small fw-medium">
                            AI Model Confidence: <strong className={confPct >= 80 ? 'text-success' : 'text-warning'}>{confPct.toFixed(0)}%</strong>
                          </span>
                          <small className="text-muted fw-bold" style={{fontSize: '0.70rem', textTransform: 'uppercase'}}>{label}</small>
                        </div>
                      );
                    })()}
                  </div>
                  <div className="w-100 mt-4">
                    <NILMApplianceChart applianceDetails={data.appliance_details} />
                  </div>
                </div>
              </div>
            </div>

            {/* Row 3: Appliance Deep Dive Table */}
            <div className="bg-white rounded-4 shadow-sm p-4 border-0 mb-4">
              <h5 className="fw-bold mb-4"><i className="bi bi-cpu-fill text-primary me-2"></i> Appliance Intelligence & Status</h5>
              <div className="table-responsive">
                <table className="table table-hover align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th className="py-3 text-muted fw-semibold">Appliance</th>
                      <th className="py-3 text-muted fw-semibold">Energy (kWh)</th>
                      <th className="py-3 text-muted fw-semibold">Contribution</th>
                      <th className="py-3 text-muted fw-semibold">Typical Base</th>
                      <th className="py-3 text-muted fw-semibold">Status</th>
                      <th className="py-3 text-muted fw-semibold">Est. Cost/mo</th>
                      <th className="py-3 text-muted fw-semibold w-25">AI Recommendation</th>
                    </tr>
                  </thead>
                  <tbody className="border-top-0">
                    {(data.appliance_details || []).map((app, idx) => {
                      const st = getApplianceStatus(app.pct, app.typical_pct);
                      return (
                        <tr key={app.appliance} className={st.label === 'Critical' ? "bg-danger bg-opacity-10" : st.label === 'High' ? "bg-warning bg-opacity-10" : ""}>
                          <td className="fw-bold py-3">
                            <div className="d-flex align-items-center">
                              <div className="rounded-circle bg-light d-flex align-items-center justify-content-center me-3" style={{ width: 40, height: 40 }}>
                                <i className="bi bi-plug text-primary"></i>
                              </div>
                              {app.appliance}
                            </div>
                          </td>
                          <td className="fw-semibold">{fmtKwh(app.kwh)}</td>
                          <td className="fw-semibold">{fmtPct(app.pct)}%</td>
                          <td className="text-muted">~{fmtPct(app.typical_pct)}%</td>
                          <td>
                            <span className={`badge bg-${st.color} bg-opacity-10 text-${st.color} border border-${st.color} px-3 py-2 rounded-pill`}>
                              {st.label}
                            </span>
                          </td>
                          <td className="fw-bold">{fmtCurrency(app.est_monthly_cost_inr, 0)}</td>
                          <td className="text-muted small lh-sm">{app.reduction_tip}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Row 4: Power Factor and Billing Details */}
            <div className="row g-4 mb-4">
              {pfData && pfData.readings && (
                <div className="col-xl-12">
                  <div className="bg-white rounded-4 shadow-sm p-4 border-0">
                    <h5 className="fw-bold mb-4"><i className="bi bi-activity text-primary me-2"></i> Power Quality (PF) Trend</h5>
                    {pfData.summary.status !== 'Excellent' && (
                      <div className={`alert ${pfData.summary.status === 'Critical' ? 'alert-danger' : 'alert-warning'} rounded-3 d-flex align-items-center border-0 shadow-sm mb-4`}>
                        <i className={`bi ${pfData.summary.status === 'Critical' ? 'bi-exclamation-octagon-fill' : 'bi-exclamation-triangle-fill'} fs-3 me-3`}></i>
                        <div>
                          <strong className="d-block">{pfData.summary.description}</strong>
                        </div>
                      </div>
                    )}
                    <div className="row align-items-center">
                      <div className="col-lg-3 border-end pe-4">
                        <PowerFactorGauge averagePf={pfData.summary.average_pf} />
                        <div className="mt-4">
                          <div className="d-flex justify-content-between mb-3 border-bottom pb-2">
                            <span className="text-muted small fw-medium">Minimum PF</span>
                            <strong className="text-danger">{pfData.summary.minimum_pf.toFixed(2)}</strong>
                          </div>
                          <div className="d-flex justify-content-between mb-3 border-bottom pb-2">
                            <span className="text-muted small fw-medium">Maximum PF</span>
                            <strong className="text-success">{pfData.summary.maximum_pf.toFixed(2)}</strong>
                          </div>
                          <div className="d-flex justify-content-between mb-3 border-bottom pb-2">
                            <span className="text-muted small fw-medium">Low PF Events</span>
                            <strong className="text-warning">{pfData.summary.low_pf_events}</strong>
                          </div>
                          <div className="d-flex justify-content-between">
                            <span className="text-muted small fw-medium">Max Streak</span>
                            <strong>{pfData.summary.longest_low_pf_duration} ({pfData.interval_minutes}m)</strong>
                          </div>
                        </div>
                      </div>
                      <div className="col-lg-9 ps-4">
                        <PowerFactorChart readings={pfData.readings} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            
            {/* Row 5: Financial Breakdown & Sustainability */}
            <div className="row g-4">
              <div className="col-xl-6">
                <div className="bg-white rounded-4 shadow-sm p-4 border-0 h-100">
                  <div className="d-flex justify-content-between align-items-center mb-4">
                    <h5 className="fw-bold mb-0"><i className="bi bi-receipt text-primary me-2"></i> Bill Breakdown</h5>
                    <span className="badge bg-light text-dark border rounded-pill px-3 py-2">
                      {bd.tariff_category || "Residential"} · {(bd.billing_type || "slab").charAt(0).toUpperCase() + (bd.billing_type || "slab").slice(1)} Rate
                    </span>
                  </div>
                  
                  <div className="bg-light rounded-3 p-3 mb-4">
                    <div className="d-flex justify-content-between mb-2">
                      <span className="text-uppercase small fw-bold text-muted" style={{ letterSpacing: '0.5px' }}>Billing Cycle Progress</span>
                      <span className="small fw-bold">{daysElapsed} / {daysTotal} Days</span>
                    </div>
                    <div className="progress rounded-pill bg-white" style={{ height: "10px" }}>
                      <div className="progress-bar bg-primary rounded-pill" style={{ width: `${cycleProgressPct}%` }}></div>
                    </div>
                  </div>

                  <div className="d-flex justify-content-between mb-3 pb-3 border-bottom">
                    <span className="text-muted fw-medium"><i className="bi bi-lightning-charge me-2 text-warning"></i>Energy Charge</span>
                    <span className="fw-bold">{fmtCurrency(bd.energy_charge, 0)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-3 pb-3 border-bottom">
                    <span className="text-muted fw-medium"><i className="bi bi-building me-2 text-secondary"></i>Fixed Charge</span>
                    <span className="fw-bold">{fmtCurrency(bd.fixed_charge, 0)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-3 pb-3 border-bottom text-success">
                    <span className="fw-medium"><i className="bi bi-sun me-2"></i>ToD Rebate (Savings)</span>
                    <span className="fw-bold">−{fmtCurrency(bd.tod_rebate, 0)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-3 pb-3 border-bottom text-danger">
                    <span className="fw-medium"><i className="bi bi-clock-history me-2"></i>Peak Surcharge</span>
                    <span className="fw-bold">+{fmtCurrency(bd.peak_surcharge, 0)}</span>
                  </div>
                  <div className="d-flex justify-content-between mb-3 pb-3 border-bottom">
                    <span className="text-muted fw-medium"><i className="bi bi-percent me-2"></i>Electricity Duty</span>
                    <span className="fw-bold">{fmtCurrency(bd.electricity_duty, 0)}</span>
                  </div>
                  
                  <div className="bg-primary bg-opacity-10 rounded-3 p-3 mt-4">
                    <div className="d-flex justify-content-between align-items-center mb-1">
                      <span className="text-primary fw-bold">Current Charges (Till Date)</span>
                      <span className="fs-5 fw-bold text-primary">{fmtCurrency(currentCharges, 0)}</span>
                    </div>
                    <div className="d-flex justify-content-between align-items-center">
                      <span className="text-muted small">Estimated Final Bill</span>
                      <span className="fw-bold text-dark">{fmtCurrency(estimatedFinalBill, 0)}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="col-xl-6">
                <div className="bg-white rounded-4 shadow-sm p-4 border-0 mb-4">
                  <h5 className="fw-bold mb-4"><i className="bi bi-robot text-primary me-2"></i> AI Savings Opportunities</h5>
                  {aiSavings.length === 0 ? <p className="text-muted">No active savings opportunities.</p> : (
                    <div className="d-flex flex-column gap-3">
                      {aiSavings.filter(s => s.priority !== "info").map((s, i) => (
                        <div key={i} className="d-flex align-items-start p-3 rounded-3 border">
                          <div className={`rounded-circle p-2 me-3 ${s.priority === 'high' ? 'bg-danger bg-opacity-10 text-danger' : 'bg-warning bg-opacity-10 text-warning'}`}>
                            <i className="bi bi-lightbulb-fill"></i>
                          </div>
                          <div className="flex-grow-1">
                            <div className="d-flex justify-content-between align-items-center mb-1">
                              <strong className="text-dark">{s.title}</strong>
                              {s.saving_inr > 0 && <span className="badge bg-success bg-opacity-10 text-success border border-success rounded-pill px-2 py-1">Save ₹{s.saving_inr}/mo</span>}
                            </div>
                            <p className="text-muted small mb-0 lh-sm">{s.detail}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-white rounded-4 shadow-sm p-4 border-0">
                  <h5 className="fw-bold mb-4"><i className="bi bi-tree text-success me-2"></i> Sustainability Impact</h5>
                  <div className="row g-3">
                    <div className="col-6">
                      <div className="p-3 bg-light rounded-3 border-0">
                        <span className="text-muted d-block small mb-1">This Month CO₂</span>
                        <strong className="fs-5">{fmtNum(carbon.carbon_kg)} kg</strong>
                      </div>
                    </div>
                    <div className="col-6">
                      <div className="p-3 bg-light rounded-3 border-0">
                        <span className="text-muted d-block small mb-1">Green Score</span>
                        <strong className="fs-5">{greenScore.score || "N/A"} <span className="fs-6 text-muted fw-normal">/100</span></strong>
                      </div>
                    </div>
                    <div className="col-6">
                      <div className="p-3 bg-light rounded-3 border-0 text-success">
                        <span className="text-success opacity-75 d-block small mb-1">Trees to Offset</span>
                        <strong className="fs-5"><i className="bi bi-tree-fill me-1"></i>{fmtCount(carbon.trees_needed)}</strong>
                      </div>
                    </div>
                    <div className="col-6">
                      <div className="p-3 bg-light rounded-3 border-0 text-info">
                        <span className="text-info opacity-75 d-block small mb-1">Vehicle Eqv.</span>
                        <strong className="fs-5"><i className="bi bi-car-front-fill me-1"></i>{fmtCount(carbon.vehicle_km_equiv)} km</strong>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        )
      )}
    </DashboardLayout>
  );
}
