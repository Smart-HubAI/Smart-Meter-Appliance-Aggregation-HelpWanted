import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import DashboardLayout, { getNavItems } from "../components/DashboardLayout";
import {
  MonthlyTrendChart, DailyLoadChart,
  DistributionPieChart, HorizontalBarChart,
} from "../components/LineBarCharts";
import { getAdmin, getAdminPowerFactor, updateInvestigationStatus, getInvestigationHistory } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { fmtKwh, fmtPct, fmtCurrency, fmtPF, fmtPower, fmtNum, fmtCount } from "../utils/format";
import InvestigationModal from "../components/InvestigationModal";
function riskBandBadge(band) {
  const cls = { Critical: "risk-critical", High: "risk-high", Medium: "risk-medium", Low: "risk-low" }[band] || "risk-low";
  return <span className={`risk-band-badge ${cls}`}>{band}</span>;
}

function riskBar(value, max = 100) {
  const pct = Math.min(100, (value / max) * 100);
  const color = value >= 75 ? "#c62828" : value >= 50 ? "#ef6c00" : value >= 25 ? "#f9a825" : "#2e7d32";
  return (
    <div className="iq-risk-bar-wrap" style={{ width: "90px" }}>
      <div className="iq-risk-bar" style={{ width: `${pct}%`, background: color }}></div>
      <span className="iq-risk-bar-label ms-2">{fmtNum(value, 1)}</span>
    </div>
  );
}

function statusBadge(status) {
  let bg = "#ffc107"; // Open (Yellow)
  let text = "text-dark";
  if (status === "Assigned") { bg = "#0d6efd"; text = "text-white"; } // Blue
  else if (status === "In Progress") { bg = "#fd7e14"; text = "text-white"; } // Orange
  else if (status === "Resolved") { bg = "#198754"; text = "text-white"; } // Green
  else if (status === "Closed") { bg = "#495057"; text = "text-white"; } // Dark Gray
  
  return (
    <span className={`badge rounded-pill px-2 py-1 shadow-sm ${text}`} style={{ backgroundColor: bg, fontSize: "12px" }}>
      {status}
    </span>
  );
}

function KPICard({ icon, label, value, sub, variant = "" }) {
  return (
    <div className={`kpi-card ${variant}`}>
      <div className="kpi-label"><i className={`bi ${icon} me-1`}></i>{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <small className="text-muted d-block mt-1" style={{ fontSize: 11 }}>{sub}</small>}
    </div>
  );
}

function ChartCard({ title, subtitle, icon, children, footer }) {
  return (
    <div className="chart-card d-flex flex-column h-100 shadow-sm border-0 rounded-4" style={{ padding: '1.5rem', backgroundColor: '#fff' }}>
      <div className="mb-3">
        <h6 className="fw-bold mb-1"><i className={`bi ${icon} me-2 text-primary`}></i>{title}</h6>
        {subtitle && <small className="text-muted">{subtitle}</small>}
      </div>
      <div className="flex-grow-1">
        {children}
      </div>
      {footer && (
        <div className="mt-3 pt-3 border-top text-muted small fw-medium">
          {footer}
        </div>
      )}
    </div>
  );
}

export default function Admin() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { user } = useAuth();
  const navItems = getNavItems(user?.role || "admin");

  const [ctSearch, setCtSearch] = useState("");
  const [ctZoneFilter, setCtZoneFilter] = useState("All");
  const [ctCategoryFilter, setCtCategoryFilter] = useState("All");
  const [ctSeverityFilter, setCtSeverityFilter] = useState("All");
  const [ctAnomalyTypeFilter, setCtAnomalyTypeFilter] = useState("All");
  const [ctStatusFilter, setCtStatusFilter] = useState("All");
  
  const [ctSortBy, setCtSortBy] = useState("overall_risk_score");
  const [ctSortDir, setCtSortDir] = useState("desc");
  
  // Power Factor Table State
  const [pfData, setPfData] = useState([]);
  const [loadingPf, setLoadingPf] = useState(true);
  
  // Investigation Modal State
  const [isModalOpen, setModalOpen] = useState(false);
  const [selectedInvestigation, setSelectedInvestigation] = useState(null);
  const [pfSearch, setPfSearch] = useState("");
  const [pfZoneFilter, setPfZoneFilter] = useState("All");
  const [pfCategoryFilter, setPfCategoryFilter] = useState("All");
  const [pfStatusFilter, setPfStatusFilter] = useState("All");
  
  const [pfSortBy, setPfSortBy] = useState("average_pf");
  const [pfSortDir, setPfSortDir] = useState("asc");
  const consumerTable = data?.consumer_table || [];
  const investigationQueue = data?.utility_investigation_queue || [];
  const kpis = data?.kpis || {};
  const charts = data?.charts || {};

  const anomalyData = useMemo(() => {
    const invMap = {};
    investigationQueue.forEach(q => { invMap[q.consumer_id] = q; });
    
    return consumerTable.map(c => {
      const q = invMap[c.consumer_id] || {};
      
      const hasTampering = q.has_tampering || false;
      const riskScore = q.overall_risk_score || c.overall_risk_score || 0;
      const anomalies = q.anomalies || [];
      const currentLoad = q.current_load || c.current_load || 0;
      
      const severity = q.severity || "Low";
      const recAction = q.rec_action || "No Immediate Action";
      
      let anomalyType = "None";
      if (q.primary_anomaly && q.primary_anomaly !== "None") {
          const matched = anomalies.find(a => a.anomaly_type === q.primary_anomaly);
          if (matched) anomalyType = matched.anomaly_label || matched.anomaly_type;
          else anomalyType = q.primary_anomaly.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      } else if (anomalies.length > 0) {
          anomalyType = anomalies[0].anomaly_label || anomalies[0].anomaly_type;
      }
      
      return {
        ...c,
        anomalies,
        severity,
        anomalyType,
        recAction,
        tamperStatus: hasTampering,
        status: q.investigation_status || c.status,
        assigned_to: q.assigned_to || "",
        inv_remarks: q.inv_remarks || "",
        inv_last_updated: q.inv_last_updated || null,
        priority: q.priority || "Normal",
        overall_risk_score: riskScore,
        current_load: currentLoad,
      };
    });
  }, [consumerTable, investigationQueue]);

  const ctZones = useMemo(() => ["All", ...Array.from(new Set(anomalyData.map(r => r.zone).filter(Boolean))).sort()], [anomalyData]);
  const ctCategories = useMemo(() => ["All", ...Array.from(new Set(anomalyData.map(r => r.consumer_category).filter(Boolean))).sort()], [anomalyData]);
  const ctSeverities = ["All", "Critical", "High", "Medium", "Low"];
  const ctAnomalyTypes = useMemo(() => ["All", ...Array.from(new Set(anomalyData.map(r => r.anomalyType).filter(Boolean))).sort()], [anomalyData]);
  const ctStatuses = useMemo(() => ["All", ...Array.from(new Set(anomalyData.map(r => r.status).filter(Boolean))).sort()], [anomalyData]);

  const filteredCT = useMemo(() => {
    let rows = anomalyData.filter(r => {
      if (ctSearch) {
        const q = ctSearch.toLowerCase();
        if (!r.consumer_id?.toLowerCase().includes(q) && !r.name?.toLowerCase().includes(q)) return false;
      }
      if (ctZoneFilter !== "All" && r.zone !== ctZoneFilter) return false;
      if (ctCategoryFilter !== "All" && r.consumer_category !== ctCategoryFilter) return false;
      if (ctSeverityFilter !== "All" && r.severity !== ctSeverityFilter) return false;
      if (ctAnomalyTypeFilter !== "All" && r.anomalyType !== ctAnomalyTypeFilter) return false;
      if (ctStatusFilter !== "All" && r.status !== ctStatusFilter) return false;
      return true;
    });
    rows.sort((a, b) => {
      const mul = ctSortDir === "desc" ? -1 : 1;
      
      if (ctSortBy === "overall_risk_score") {
        if (a.overall_risk_score !== b.overall_risk_score) {
            return mul * ((a.overall_risk_score || 0) - (b.overall_risk_score || 0));
        }
        
        const sevMap = { "Critical": 4, "High": 3, "Medium": 2, "Low": 1 };
        const aSev = sevMap[a.severity] || 0;
        const bSev = sevMap[b.severity] || 0;
        if (aSev !== bSev) return mul * (aSev - bSev);
        
        const aLoad = a.current_load || 0;
        const bLoad = b.current_load || 0;
        if (aLoad !== bLoad) return mul * (aLoad - bLoad);
        
        return mul * (a.consumer_id || "").localeCompare(b.consumer_id || "");
      }
      
      const va = a[ctSortBy] ?? 0, vb = b[ctSortBy] ?? 0;
      if (typeof va === "string") return mul * va.localeCompare(vb);
      return mul * (va - vb);
    });
    return rows;
  }, [anomalyData, ctSearch, ctZoneFilter, ctCategoryFilter, ctSeverityFilter, ctAnomalyTypeFilter, ctStatusFilter, ctSortBy, ctSortDir]);

  const pfZones = useMemo(() => ["All", ...Array.from(new Set(pfData.map(r => r.zone).filter(Boolean))).sort()], [pfData]);
  const pfCategories = useMemo(() => ["All", ...Array.from(new Set(pfData.map(r => r.category).filter(Boolean))).sort()], [pfData]);
  const pfStatuses = ["All", "Critical", "Warning", "Excellent"];

  const filteredPf = useMemo(() => {
    let rows = pfData.filter(r => {
      if (pfSearch) {
        const q = pfSearch.toLowerCase();
        if (!r.consumer_id?.toLowerCase().includes(q) && !r.consumer_name?.toLowerCase().includes(q)) return false;
      }
      if (pfZoneFilter !== "All" && r.zone !== pfZoneFilter) return false;
      if (pfCategoryFilter !== "All" && r.category !== pfCategoryFilter) return false;
      if (pfStatusFilter !== "All" && r.status !== pfStatusFilter) return false;
      return true;
    });
    rows.sort((a, b) => {
      const mul = pfSortDir === "desc" ? -1 : 1;
      const va = a[pfSortBy] ?? 0, vb = b[pfSortBy] ?? 0;
      if (typeof va === "string") return mul * va.localeCompare(vb);
      return mul * (va - vb);
    });
    return rows;
  }, [pfData, pfSearch, pfZoneFilter, pfCategoryFilter, pfStatusFilter, pfSortBy, pfSortDir]);

  const criticalCases = anomalyData.filter(r => r.severity === "Critical").length;
  const openInv = anomalyData.filter(r => r.status === "Open").length;
  const assignedInv = anomalyData.filter(r => r.status === "Assigned").length;
  const inProgressInv = anomalyData.filter(r => r.status === "In Progress").length;
  const resolvedToday = anomalyData.filter(r => r.status === "Resolved" || r.status === "Closed").length;

  const resetFilters = () => {
    setCtSearch(""); setCtZoneFilter("All"); setCtCategoryFilter("All"); setCtSeverityFilter("All"); setCtAnomalyTypeFilter("All"); setCtStatusFilter("All");
  };

  const resetPfFilters = () => {
    setPfSearch(""); setPfZoneFilter("All"); setPfCategoryFilter("All"); setPfStatusFilter("All");
  };

  const load = () => { 
    setLoading(true); setError(null); setLoadingPf(true);
    getAdmin().then(setData).catch((err) => setError(err.message || "Failed to load")).finally(() => setLoading(false)); 
    getAdminPowerFactor().then(setPfData).catch((err) => console.error(err)).finally(() => setLoadingPf(false));
  };

  const silentLoad = () => {
    getAdmin().then(setData).catch(console.error);
    getAdminPowerFactor().then(setPfData).catch(console.error);
  };
  useEffect(() => { load(); }, []);

  const ctSort = (col) => {
    if (ctSortBy === col) setCtSortDir(d => d === "asc" ? "desc" : "asc");
    else { setCtSortBy(col); setCtSortDir("desc"); }
  };
  const ctSortIcon = (col) => ctSortBy === col ? (ctSortDir === "asc" ? " ▲" : " ▼") : "";

  const pfSort = (col) => {
    if (pfSortBy === col) setPfSortDir(d => d === "asc" ? "desc" : "asc");
    else { setPfSortBy(col); setPfSortDir("asc"); }
  };
  const pfSortIcon = (col) => pfSortBy === col ? (pfSortDir === "asc" ? " ▲" : " ▼") : "";

  const handleView = async (row) => {
    console.log("VIEW CLICKED");
    console.log(row);
    setSelectedInvestigation({ ...row, history: [], loading: true, newStatus: row.status, assignedTo: row.assigned_to || "", remarks: row.inv_remarks || "", error: "" });
    setModalOpen(true);
    try {
      const { history } = await getInvestigationHistory(row.consumer_id);
      setSelectedInvestigation(prev => ({ ...prev, history, loading: false }));
    } catch (err) {
      setSelectedInvestigation(prev => ({ ...prev, loading: false, error: "Failed to load history." }));
    }
  };

  const handleSave = async (payload) => {
    console.log("SAVE CLICKED");
    console.log("POST PAYLOAD", payload);
    setSelectedInvestigation(prev => ({ ...prev, error: "" }));
    try {
      await updateInvestigationStatus(payload);
      silentLoad();
      setModalOpen(false);
    } catch (err) {
      setSelectedInvestigation(prev => ({ ...prev, error: err.response?.data?.error || "Failed to update status." }));
    }
  };

  if (loading) return <DashboardLayout brandIcon="bi-building" brandTitle="Utility Admin" brandSubtitle="Loading…" navItems={navItems}><p className="text-muted">Loading utility dashboard…</p></DashboardLayout>;
  if (error || !data) return <DashboardLayout brandIcon="bi-building" brandTitle="Utility Admin" brandSubtitle="Error" navItems={navItems}><div className="alert alert-danger">{error || "Failed to load admin data"}<button type="button" className="btn btn-sm btn-outline-danger ms-2" onClick={load}>Retry</button></div></DashboardLayout>;

  return (
    <DashboardLayout brandIcon="bi-building" brandTitle="Utility Admin" brandSubtitle="Distribution Analytics" navItems={navItems}>
      <div className="top-bar mb-4 pb-3 border-bottom d-flex justify-content-between align-items-center">
        <div>
          <h4 className="mb-1 fw-bold">Utility Operations Dashboard</h4>
          <span className="text-muted small">Fleet-wide smart meter analytics &amp; consumer insights</span>
        </div>
        <span className="badge bg-danger shadow-sm py-2 px-3"><i className="bi bi-broadcast me-1"></i> Live Data</span>
      </div>

      <div className="row g-4 mb-5">
        <div className="col-sm-6 col-xl-3">
          <KPICard icon="bi-people-fill" label="Total Consumers" value={kpis.total_consumers} sub={`${kpis.connected_consumers} connected · ${kpis.disconnected_consumers} disconnected`} />
        </div>
        <div className="col-sm-6 col-xl-3">
          <KPICard icon="bi-lightning-charge-fill" label="Monthly Energy Sent" value={`${fmtKwh(kpis.monthly_energy_kwh)} kWh`} sub={`${kpis.energy_start_date || ""} – ${kpis.energy_end_date || ""}`} variant="accent" />
        </div>
        <div className="col-sm-6 col-xl-3">
          <KPICard icon="bi-currency-rupee" label="Monthly Revenue" value={fmtCurrency(kpis.monthly_revenue_inr, 0)} sub={kpis.revenue_source === "billing_table" ? `From billing · ${kpis.billing_month}` : "Tariff estimate"} />
        </div>
        <div className="col-sm-6 col-xl-3">
          <KPICard icon="bi-radioactive" label="Critical Consumers" value={anomalyData.filter(c => c.severity === "Critical").length} sub="Active critical severity alerts" variant="danger" />
        </div>
      </div>

      <div className="row g-5 mb-5">
        <div className="col-lg-8 col-md-12">
          <ChartCard 
            title="Monthly Energy Trend" 
            subtitle="Fleet-wide energy consumption over the last few months."
            icon="bi-calendar-month"
            footer={charts.monthly_energy_trend?.values ? `Current month total: ${fmtKwh(charts.monthly_energy_trend.values[charts.monthly_energy_trend.values.length - 1])} kWh` : "No data available"}
          >
            <MonthlyTrendChart labels={charts.monthly_energy_trend?.labels} values={charts.monthly_energy_trend?.values} />
          </ChartCard>
        </div>
        <div className="col-lg-4 col-md-12">
          <ChartCard 
            title="Zone-wise Consumption" 
            subtitle="Energy breakdown by operational zones."
            icon="bi-geo-alt"
          >
            <HorizontalBarChart data={charts.zone_consumption} dataKey="zone" valueKey="total_kwh" color="#1565c0" />
          </ChartCard>
        </div>
      </div>

      <div className="row g-5 mb-5">
        <div className="col-lg-6 col-md-12">
          <ChartCard 
            title="Daily Load Curve" 
            subtitle="Intraday aggregated consumption profile."
            icon="bi-activity"
          >
            <DailyLoadChart labels={charts.daily_load_curve?.labels} values={charts.daily_load_curve?.values} />
          </ChartCard>
        </div>
        <div className="col-lg-6 col-md-12">
          <ChartCard 
            title="Consumer Category" 
            subtitle="Distribution of consumers across billing categories."
            icon="bi-pie-chart"
          >
            <DistributionPieChart data={charts.category_distribution} dataKey="category" valueKey="count" />
          </ChartCard>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="row g-4 mb-4">
        <div className="col" onClick={() => {resetFilters(); setCtSeverityFilter("Critical");}} style={{cursor:"pointer"}}>
          <div className="card border-0 shadow-sm text-center py-3 rounded-4" style={{ backgroundColor: ctSeverityFilter==="Critical" ? '#ffebee':'#fff'}}>
            <h3 className="text-danger mb-0 fw-bold">{criticalCases}</h3>
            <small className="text-muted fw-bold">Critical Cases</small>
          </div>
        </div>
        <div className="col" onClick={() => {resetFilters(); setCtStatusFilter("Open");}} style={{cursor:"pointer"}}>
          <div className="card border-0 shadow-sm text-center py-3 rounded-4" style={{ backgroundColor: ctStatusFilter==="Open" ? '#fff8e1':'#fff'}}>
            <h3 className="text-warning mb-0 fw-bold">{openInv}</h3>
            <small className="text-muted fw-bold">Open Alerts</small>
          </div>
        </div>
        <div className="col" onClick={() => {resetFilters(); setCtStatusFilter("Assigned");}} style={{cursor:"pointer"}}>
          <div className="card border-0 shadow-sm text-center py-3 rounded-4" style={{ backgroundColor: ctStatusFilter==="Assigned" ? '#e3f2fd':'#fff'}}>
            <h3 className="text-primary mb-0 fw-bold">{assignedInv}</h3>
            <small className="text-muted fw-bold">Assigned</small>
          </div>
        </div>
        <div className="col" onClick={() => {resetFilters(); setCtStatusFilter("In Progress");}} style={{cursor:"pointer"}}>
          <div className="card border-0 shadow-sm text-center py-3 rounded-4" style={{ backgroundColor: ctStatusFilter==="In Progress" ? '#fff3e0':'#fff'}}>
            <h3 className="mb-0 fw-bold" style={{color: '#fd7e14'}}>{inProgressInv}</h3>
            <small className="text-muted fw-bold">In Progress</small>
          </div>
        </div>
        <div className="col" onClick={() => {resetFilters(); setCtStatusFilter("Resolved");}} style={{cursor:"pointer"}}>
          <div className="card border-0 shadow-sm text-center py-3 rounded-4" style={{ backgroundColor: ctStatusFilter==="Resolved" ? '#e8f5e9':'#fff'}}>
            <h3 className="text-success mb-0 fw-bold">{resolvedToday}</h3>
            <small className="text-muted fw-bold">Resolved Today</small>
          </div>
        </div>
      </div>

      <div className="iq-section mb-5 shadow-sm" style={{ borderRadius: '12px', overflow: 'hidden' }}>
        <div className="iq-section-header bg-white border-bottom p-4">
          <h5 className="mb-0 fw-bold"><i className="bi bi-shield-exclamation me-2 text-danger"></i>Operational Alerts &amp; Anomaly Intelligence <span className="badge bg-danger ms-2 fs-6">{filteredCT.length} / {anomalyData.length}</span></h5>
        </div>
        <div className="p-4 bg-light border-bottom">
          <div className="row g-3">
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Search</label>
              <div className="input-group input-group-sm">
                <span className="input-group-text bg-white border-end-0"><i className="bi bi-search text-muted"></i></span>
                <input type="text" className="form-control border-start-0 ps-0 shadow-none" placeholder="ID or Name..." value={ctSearch} onChange={e => setCtSearch(e.target.value)} />
                {ctSearch && <button className="btn btn-outline-secondary" onClick={() => setCtSearch("")}><i className="bi bi-x"></i></button>}
              </div>
            </div>
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Zone</label>
              <select className="form-select form-select-sm shadow-none" value={ctZoneFilter} onChange={e => setCtZoneFilter(e.target.value)}>
                {ctZones.map(z => <option key={z} value={z}>{z === "All" ? "All Zones" : z}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Category</label>
              <select className="form-select form-select-sm shadow-none" value={ctCategoryFilter} onChange={e => setCtCategoryFilter(e.target.value)}>
                {ctCategories.map(c => <option key={c} value={c}>{c === "All" ? "All Categories" : c}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Severity</label>
              <select className="form-select form-select-sm shadow-none" value={ctSeverityFilter} onChange={e => setCtSeverityFilter(e.target.value)}>
                {ctSeverities.map(s => <option key={s} value={s}>{s === "All" ? "All Severities" : s}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Anomaly Type</label>
              <select className="form-select form-select-sm shadow-none" value={ctAnomalyTypeFilter} onChange={e => setCtAnomalyTypeFilter(e.target.value)}>
                {ctAnomalyTypes.map(t => <option key={t} value={t}>{t === "All" ? "All Types" : t}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <label className="form-label small fw-bold text-muted mb-1">Status</label>
              <select className="form-select form-select-sm shadow-none" value={ctStatusFilter} onChange={e => setCtStatusFilter(e.target.value)}>
                {ctStatuses.map(s => <option key={s} value={s}>{s === "All" ? "All Statuses" : s}</option>)}
              </select>
            </div>
          </div>
          <div className="d-flex justify-content-end mt-3">
            <button className="btn btn-sm btn-outline-secondary px-4 rounded-pill" onClick={resetFilters}>Reset All Filters</button>
          </div>
        </div>
        
        <div className="table-responsive bg-white" style={{ maxHeight: "600px", overflowY: "auto", overflowX: "hidden" }}>
          <table className="table table-hover align-middle mb-0" style={{ fontSize: "13px", tableLayout: "fixed", width: "100%" }}>
            <thead className="table-light sticky-top shadow-sm" style={{ zIndex: 10 }}>
              <tr>
                <th onClick={() => ctSort("consumer_id")} className="px-2 py-2" style={{ cursor: "pointer", width: "90px" }}>ID{ctSortIcon("consumer_id")}</th>
                <th onClick={() => ctSort("zone")} className="px-2 py-2" style={{ cursor: "pointer", width: "150px" }}>Zone{ctSortIcon("zone")}</th>
                <th onClick={() => ctSort("consumer_category")} className="px-2 py-2" style={{ cursor: "pointer", width: "90px" }}>Category{ctSortIcon("consumer_category")}</th>
                <th onClick={() => ctSort("today_kwh")} className="px-2 py-2" style={{ cursor: "pointer", width: "90px" }}>Power (kW){ctSortIcon("today_kwh")}</th>
                <th onClick={() => ctSort("anomalyType")} className="px-2 py-2" style={{ cursor: "pointer", width: "170px" }}>Anomaly Type{ctSortIcon("anomalyType")}</th>
                <th onClick={() => ctSort("severity")} className="px-2 py-2" style={{ cursor: "pointer", width: "110px" }}>Severity{ctSortIcon("severity")}</th>
                <th onClick={() => ctSort("overall_risk_score")} className="px-2 py-2" style={{ cursor: "pointer", width: "140px" }}>Risk Score{ctSortIcon("overall_risk_score")}</th>
                <th className="px-2 py-2" style={{ width: "180px" }}>Recommended Action</th>
                <th className="px-2 py-2" style={{ width: "100px" }}>Status</th>
                <th className="px-2 py-2 text-center" style={{ width: "90px" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCT.map(row => {
                const isTampered = row.tamperStatus;
                const isCritical = row.severity === "Critical";
                
                return (
                <tr key={row.consumer_id} style={{ backgroundColor: isTampered ? '#fff5f5' : 'transparent' }}>
                  <td className="px-2 py-2 align-middle"><Link to={`/consumer/${row.consumer_id}`} className="fw-bold text-primary text-decoration-none text-truncate d-block">{row.consumer_id}</Link></td>
                  <td className="px-2 py-2 align-middle" style={{ wordWrap: "break-word", whiteSpace: "normal" }}>{row.zone}</td>
                  <td className="px-2 py-2 align-middle"><span className="badge bg-light text-dark border px-2 py-1">{row.consumer_category}</span></td>
                  <td className="px-2 py-2 align-middle">{fmtKwh(row.today_kwh)}</td>
                  <td className="px-2 py-2 align-middle fw-medium text-truncate" title={row.anomalyType}>{row.anomalyType}</td>
                  <td className="px-2 py-2 align-middle">
                    {isCritical ? (
                      <span className="badge bg-danger rounded-pill px-2 py-1 shadow-sm"><i className="bi bi-exclamation-triangle-fill me-1" style={{animation: 'flash 2s infinite'}}></i>Critical</span>
                    ) : row.severity === "High" ? (
                      <span className="badge rounded-pill px-2 py-1" style={{backgroundColor: '#ef6c00'}}><i className="bi bi-arrow-up-circle-fill me-1"></i>High</span>
                    ) : row.severity === "Medium" ? (
                      <span className="badge rounded-pill px-2 py-1" style={{backgroundColor: '#f9a825'}}><i className="bi bi-dash-circle-fill me-1"></i>Med</span>
                    ) : (
                      <span className="badge rounded-pill px-2 py-1 bg-success"><i className="bi bi-check-circle-fill me-1"></i>Low</span>
                    )}
                  </td>
                  <td className="px-2 py-2 align-middle">{riskBar(row.overall_risk_score)}</td>
                  <td className="px-2 py-2 align-middle" style={{ wordWrap: "break-word", whiteSpace: "normal" }}><small className="fw-bold text-secondary">{row.recAction}</small></td>
                  <td className="px-2 py-2 align-middle">
                    {statusBadge(row.status)}
                  </td>
                  <td className="px-2 py-2 align-middle text-center">
                    <button onClick={() => handleView(row)} className="btn btn-sm btn-outline-primary rounded-pill px-2 py-1" style={{ width: "70px", fontSize: "12px" }}>Manage</button>
                  </td>
                </tr>
              )})}
            </tbody>
          </table>
          {filteredCT.length === 0 && <div className="text-center py-5 text-muted"><i className="bi bi-inbox fs-1 d-block mb-3"></i>No alerts match your filters.</div>}
        </div>
      </div>

      {/* Power Factor Analytics Section */}
      <div className="iq-section mb-5 shadow-sm" style={{ borderRadius: '12px', overflow: 'hidden' }}>
        <div className="iq-section-header bg-white border-bottom p-4">
          <h5 className="mb-0 fw-bold"><i className="bi bi-activity me-2 text-primary"></i>Power Factor Analytics <span className="badge bg-primary ms-2 fs-6">{filteredPf.length} / {pfData.length}</span></h5>
        </div>
        <div className="p-4 bg-light border-bottom">
          <div className="row g-3">
            <div className="col-md-3">
              <label className="form-label small fw-bold text-muted mb-1">Search Consumer</label>
              <div className="input-group input-group-sm">
                <span className="input-group-text bg-white border-end-0"><i className="bi bi-search text-muted"></i></span>
                <input type="text" className="form-control border-start-0 ps-0 shadow-none" placeholder="ID or Name..." value={pfSearch} onChange={e => setPfSearch(e.target.value)} />
                {pfSearch && <button className="btn btn-outline-secondary" onClick={() => setPfSearch("")}><i className="bi bi-x"></i></button>}
              </div>
            </div>
            <div className="col-md-3">
              <label className="form-label small fw-bold text-muted mb-1">Zone</label>
              <select className="form-select form-select-sm shadow-none" value={pfZoneFilter} onChange={e => setPfZoneFilter(e.target.value)}>
                {pfZones.map(z => <option key={z} value={z}>{z === "All" ? "All Zones" : z}</option>)}
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label small fw-bold text-muted mb-1">Category</label>
              <select className="form-select form-select-sm shadow-none" value={pfCategoryFilter} onChange={e => setPfCategoryFilter(e.target.value)}>
                {pfCategories.map(c => <option key={c} value={c}>{c === "All" ? "All Categories" : c}</option>)}
              </select>
            </div>
            <div className="col-md-3">
              <label className="form-label small fw-bold text-muted mb-1">Status</label>
              <select className="form-select form-select-sm shadow-none" value={pfStatusFilter} onChange={e => setPfStatusFilter(e.target.value)}>
                {pfStatuses.map(s => <option key={s} value={s}>{s === "All" ? "All Statuses" : s}</option>)}
              </select>
            </div>
          </div>
          <div className="d-flex justify-content-end mt-3">
            <button className="btn btn-sm btn-outline-secondary px-4 rounded-pill" onClick={resetPfFilters}>Reset All Filters</button>
          </div>
        </div>

        <div className="table-responsive bg-white" style={{ maxHeight: "600px", overflowY: "auto" }}>
          {loadingPf ? (
            <div className="text-center py-5 text-muted"><div className="spinner-border text-primary mb-3" role="status"></div><br/>Loading power factor data...</div>
          ) : (
            <table className="table table-hover align-middle mb-0" style={{ fontSize: "0.90rem" }}>
              <thead className="table-light sticky-top shadow-sm" style={{ zIndex: 10 }}>
                <tr>
                  <th className="px-4 py-4" style={{ whiteSpace: "nowrap" }}>Consumer ID</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Name</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Zone</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Category</th>
                  <th onClick={() => pfSort("average_pf")} className="py-4" style={{ cursor: "pointer", whiteSpace: "nowrap" }}>Average PF{pfSortIcon("average_pf")}</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Min PF</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Max PF</th>
                  <th onClick={() => pfSort("low_pf_events")} className="py-4" style={{ cursor: "pointer", whiteSpace: "nowrap" }}>Low PF Events{pfSortIcon("low_pf_events")}</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Longest Low PF</th>
                  <th onClick={() => pfSort("status")} className="py-4" style={{ cursor: "pointer", whiteSpace: "nowrap" }}>Status{pfSortIcon("status")}</th>
                  <th className="py-4" style={{ whiteSpace: "nowrap" }}>Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredPf.map(row => (
                  <tr key={row.consumer_id} style={{ backgroundColor: row.status === 'Excellent' ? 'transparent' : row.color + '1A' }}>
                    <td className="px-4 py-3 align-middle"><Link to={`/consumer/${row.consumer_id}`} className="fw-bold text-primary text-decoration-none">{row.consumer_id}</Link></td>
                    <td className="py-3 align-middle">{row.consumer_name}</td>
                    <td className="py-3 align-middle">{row.zone}</td>
                    <td className="py-3 align-middle"><span className="badge bg-light text-dark border">{row.category}</span></td>
                    <td className="py-3 align-middle fw-bold">{row.average_pf.toFixed(4)}</td>
                    <td className="py-3 align-middle">{row.minimum_pf.toFixed(4)}</td>
                    <td className="py-3 align-middle">{row.maximum_pf.toFixed(4)}</td>
                    <td className="py-3 align-middle">{row.low_pf_events}</td>
                    <td className="py-3 align-middle">{row.longest_low_pf_duration} intervals</td>
                    <td className="py-3 align-middle">
                      <span className="badge rounded-pill px-3 py-1 shadow-sm text-nowrap" style={{ backgroundColor: row.color }}>
                        <i className={`bi ${row.status === 'Critical' ? 'bi-exclamation-triangle-fill' : row.status === 'Warning' ? 'bi-exclamation-circle-fill' : 'bi-check-circle-fill'} me-1`}></i>
                        {row.status}
                      </span>
                    </td>
                    <td className="py-3 align-middle text-muted small">{row.last_updated ? new Date(row.last_updated).toLocaleString() : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!loadingPf && filteredPf.length === 0 && <div className="text-center py-5 text-muted"><i className="bi bi-inbox fs-1 d-block mb-3"></i>No consumers match your filters.</div>}
        </div>
      </div>

      <InvestigationModal
        open={isModalOpen}
        row={selectedInvestigation}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        onChange={(updates) => setSelectedInvestigation(prev => ({ ...prev, ...updates }))}
      />

    </DashboardLayout>
  );
}
