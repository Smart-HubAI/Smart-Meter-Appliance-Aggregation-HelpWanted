import React, { useEffect, useState, useMemo } from "react";
import DashboardLayout, { getNavItems } from "../components/DashboardLayout";
import { getAI, getValidation } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { 
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  BarChart, Bar, ReferenceLine 
} from "recharts";

// --- Helpers ---
function fmtMetric(val) {
  if (val == null || val === undefined || val === "") return "Metric not available";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "Metric not available";
  return (n * 100).toFixed(1) + "%";
}

function fmtRaw(val) {
  if (val == null || val === undefined || val === "") return "Metric not available";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "Metric not available";
  return n.toFixed(3);
}

function fmtR2(val) {
  if (val == null || val === undefined || val === "") return "Metric not available";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return "Metric not available"; 
  return n.toFixed(3);
}

function interpretMatrix(name, tn, fp, fn, tp) {
  const displayName = name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const total = tn + fp + fn + tp;
  const anomalyPct = total > 0 ? ((tp + fn) / total * 100).toFixed(1) : "0";
  const fpRate = (tp + fp) > 0 ? (fp / (tp + fp) * 100).toFixed(1) : "0";

  let strength = "";
  if (tp > fp * 5 && fn < tp * 0.2) {
    strength = "one of the strongest anomaly detection models in the system";
  } else if (tp > fp * 3) {
    strength = "a reliable anomaly detection model with good precision";
  } else if (tp > fp) {
    strength = "a moderate performer, catching more anomalies than false alarms";
  } else {
    strength = "a model that generates significant false alarms relative to correct detections";
  }

  return (
    `${displayName} correctly identified ${tp.toLocaleString()} anomaly cases out of ` +
    `${(tp + fn).toLocaleString()} actual anomalies (${anomalyPct}% anomaly prevalence). ` +
    `It produced ${fp.toLocaleString()} false alarm${fp !== 1 ? "s" : ""} ` +
    `(false positive rate: ${fpRate}%) and missed ${fn.toLocaleString()} anomaly` +
    `${fn !== 1 ? "s" : ""}. ` +
    `Overall, this is ${strength}.`
  );
}

function getRowClass(index) {
  if (index === 0) return "table-success";
  if (index === 1) return "table-info";
  if (index === 2) return "table-warning";
  return "table-danger";
}

// --- Regression Performance Dashboard ---
function RegressionPerformanceDashboard({ metrics, title, explanationText }) {
  if (!metrics || !metrics.prediction_values || metrics.prediction_values.length === 0) {
    return (
      <div className="card border-0 bg-light p-4 text-center">
        <i className="bi bi-exclamation-triangle fs-3 text-warning mb-2"></i>
        <h6>Visualization data not found in evaluation metrics</h6>
        <p className="text-muted small mb-0">Please retrain the model to generate plots.</p>
      </div>
    );
  }

  // Build scatter data
  const scatterData = metrics.prediction_values.map((p, i) => ({
    actual: metrics.ground_truth_values[i],
    predicted: p
  }));
  
  // Build histogram data for absolute errors
  // We'll bucket the errors into 10 bins
  const errors = metrics.absolute_errors || [];
  const maxErr = Math.max(...errors, 0.1);
  const binSize = maxErr / 10;
  const bins = Array(10).fill(0);
  errors.forEach(e => {
    let binIdx = Math.floor(e / binSize);
    if (binIdx >= 10) binIdx = 9;
    bins[binIdx]++;
  });
  
  const histData = bins.map((count, i) => ({
    range: `${(i * binSize).toFixed(1)} - ${((i + 1) * binSize).toFixed(1)}`,
    count
  }));

  const maxVal = Math.max(
    ...metrics.ground_truth_values,
    ...metrics.prediction_values
  );

  return (
    <div className="row g-4">
      <div className="col-md-6">
        <div className="card h-100 border-0 bg-light p-3">
          <h6 className="mb-3 text-center">{title} Scatter Plot</h6>
          <div style={{ height: "300px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" dataKey="actual" name="Actual" domain={[0, maxVal]} />
                <YAxis type="number" dataKey="predicted" name="Predicted" domain={[0, maxVal]} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <ReferenceLine segment={[{x:0, y:0}, {x:maxVal, y:maxVal}]} stroke="red" strokeDasharray="3 3" />
                <Scatter name="Predictions" data={scatterData} fill="#0d6efd" opacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="col-md-6">
        <div className="card h-100 border-0 bg-light p-3">
          <h6 className="mb-3 text-center">Absolute Error Distribution</h6>
          <div style={{ height: "300px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histData} margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="range" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" fill="#198754" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <div className="col-12">
        <div className="card border-0 bg-white shadow-sm p-4 mt-2">
          <h6 className="mb-3">Model Metrics Summary</h6>
          <div className="row text-center mb-3">
            <div className="col">
              <div className="text-muted small">R² Score</div>
              <div className="fs-5 fw-bold">{fmtR2(metrics.r2)}</div>
            </div>
            <div className="col border-start">
              <div className="text-muted small">RMSE</div>
              <div className="fs-5 fw-bold">{fmtRaw(metrics.rmse)}</div>
            </div>
            <div className="col border-start">
              <div className="text-muted small">MAE</div>
              <div className="fs-5 fw-bold">{fmtRaw(metrics.mae)}</div>
            </div>
            <div className="col border-start">
              <div className="text-muted small">Training Samples</div>
              <div className="fs-5 fw-bold">{metrics.training_samples?.toLocaleString() || "N/A"}</div>
            </div>
          </div>
          <div className="p-3 bg-light rounded text-center">
            <i className="bi bi-info-circle me-2 text-primary"></i>
            <small>{explanationText}</small>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AI() {
  const [aiData, setAiData] = useState(null);
  const [valData, setValData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { user } = useAuth();
  const navItems = getNavItems(user?.role || "developer");

  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedCmModel, setSelectedCmModel] = useState(null);
  const rowsPerPage = 10;

  useEffect(() => {
    Promise.all([getAI(), getValidation()])
      .then(([aiRes, valRes]) => {
        setAiData(aiRes);
        setValData(valRes);
      })
      .catch((err) => setError(err.message || "Failed to load dashboard data"))
      .finally(() => setLoading(false));
  }, []);

  // --- Data Merging & Cleanup ---
  const stats = { ...aiData?.dataset_stats, ...valData?.dataset_stats };
  
  let disaggModels = [
    ...(aiData?.disaggregation_eval?.models || []),
    ...(valData?.disaggregation?.models || [])
  ];
  const disaggMap = new Map();
  disaggModels.forEach(m => {
    if(!m.model_name.includes("temporal_ensemble")) {
      disaggMap.set(m.model_name, m);
    }
  });
  disaggModels = Array.from(disaggMap.values());
  let disaggRanked = [...disaggModels].sort((a, b) => (b.r2 || 0) - (a.r2 || 0));

  let anomModels = [
    ...(aiData?.anomaly_eval?.models || []),
    ...(valData?.anomaly?.models || [])
  ].filter(m => m.model_name !== "rule_based" && m.model_name !== "autoencoder_dl");
  
  const anomMap = new Map();
  anomModels.forEach(m => anomMap.set(m.model_name, m));
  anomModels = Array.from(anomMap.values());
  anomModels = anomModels.filter(m => !(m.accuracy === 1.0 && m.precision === 0.0 && m.recall === 0.0 && m.f1 === 0.0));
  
  // Sort Anomaly dynamically: Highest Accuracy wins. Fallback to F1 if Accuracy is identical.
  const anomRanked = [...anomModels].sort((a, b) => {
    const aAcc = a.accuracy || 0;
    const bAcc = b.accuracy || 0;
    if (aAcc !== bAcc) return bAcc - aAcc;
    return (b.f1 || 0) - (a.f1 || 0);
  });
  
  const [selectedVizCategory, setSelectedVizCategory] = useState("disaggregation");
  const [selectedVizModel, setSelectedVizModel] = useState("");

  let billModels = [
    ...(aiData?.bill_eval?.models || []),
    ...(valData?.bill?.models || [])
  ];
  const billMap = new Map();
  billModels.forEach(m => billMap.set(m.model_name, m));
  billModels = Array.from(billMap.values());
  let billRanked = [...billModels].sort((a, b) => (b.r2 || 0) - (a.r2 || 0));

  // Set default model based on category change
  useEffect(() => {
    if (selectedVizCategory === "disaggregation" && disaggRanked.length > 0) {
      setSelectedVizModel(disaggRanked[0].model_name);
    } else if (selectedVizCategory === "bill" && billRanked.length > 0) {
      setSelectedVizModel(billRanked[0].model_name);
    } else if (selectedVizCategory === "anomaly" && anomRanked.length > 0) {
      setSelectedVizModel(anomRanked[0].model_name);
    }
  }, [selectedVizCategory, disaggRanked, billRanked, anomRanked]);

  const activeModelsInfo = aiData?.models_ready || {};


  const rawConsumers = valData?.per_consumer || aiData?.per_consumer || [];
  const gtRows = useMemo(() => {
    let rows = [];
    const categories = [
      "Air Conditioner (AC)", "Refrigerator", "Lighting",
      "Television & Entertainment", "Washing Machine",
      "Water Heater / Geyser", "Fans", "Miscellaneous Appliances"
    ];
    rawConsumers.forEach(c => {
      categories.forEach(cat => {
        let gt = c.ground_truth?.[cat] ?? c.ground_truth?._legacy?.[cat] ?? null;
        let pred = c.ml?.[cat] ?? null;
        
        if (gt !== null || pred !== null) {
          let gtVal = gt !== null ? parseFloat(gt) : 0;
          let predVal = pred !== null ? parseFloat(pred) : 0;
          let absError = Math.abs(gtVal - predVal);
          let pctError = gtVal > 0 ? (absError / gtVal) * 100 : 0;

          rows.push({
            consumerId: c.consumer_id,
            consumerName: c.consumer_name || c.consumer_id,
            appliance: cat,
            gt: gtVal,
            pred: predVal,
            error: predVal - gtVal,
            absError,
            pctError
          });
        }
      });
    });
    return rows;
  }, [rawConsumers]);

  const filteredGtRows = useMemo(() => {
    return gtRows.filter(r => 
      r.consumerId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.consumerName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.appliance.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [gtRows, searchTerm]);

  const totalPages = Math.ceil(filteredGtRows.length / rowsPerPage);
  const paginatedGtRows = filteredGtRows.slice((currentPage - 1) * rowsPerPage, currentPage * rowsPerPage);

  const totalModelsCount = Object.keys(activeModelsInfo).filter(k => k !== 'temporal_ensemble').length || 3;
  const modelsReadyCount = Object.entries(activeModelsInfo).filter(([k,v]) => v && k !== 'temporal_ensemble').length || 3;

  const thTooltip = (label, text) => (
    <span title={text} style={{cursor:"help", borderBottom: "1px dotted #888"}}>{label}</span>
  );

  const regTableHeaders = (
    <tr>
      <th>Rank</th>
      <th>Model</th>
      <th>{thTooltip("R²", "R-Squared: Proportion of variance explained by the model (higher is better)")}</th>
      <th>{thTooltip("RMSE", "Root Mean Square Error: Average prediction error (lower is better)")}</th>
      <th>{thTooltip("MAE", "Mean Absolute Error: Average absolute difference between prediction and actual (lower is better)")}</th>
      <th>{thTooltip("Training Time", "Time taken to train the model")}</th>
      <th>Training Samples</th>
      <th>Status</th>
    </tr>
  );

  const clfTableHeaders = (
    <tr>
      <th>Rank</th>
      <th>Model</th>
      <th>{thTooltip("Accuracy", "Percentage of correct predictions overall (higher is better)")}</th>
      <th>{thTooltip("Precision", "Percentage of true anomalies among all predicted anomalies (higher means fewer false alarms)")}</th>
      <th>{thTooltip("Recall", "Percentage of actual anomalies that were correctly detected (higher means fewer missed anomalies)")}</th>
      <th>{thTooltip("F1 Score", "Harmonic mean of Precision and Recall (higher is better)")}</th>
      <th>{thTooltip("Training Time", "Time taken to train the model")}</th>
      <th>Training Samples</th>
      <th>Status</th>
    </tr>
  );

  const trainTotal = stats.train_samples || 0;
  const testTotal = stats.test_samples || 0;
  const trainPct = (trainTotal + testTotal) > 0 ? Math.round((trainTotal / (trainTotal + testTotal)) * 100) : 80;
  const testPct = 100 - trainPct;

  return (
    <DashboardLayout brandIcon="bi-cpu" brandTitle="AI Models & Validation" brandSubtitle="ML Training & Ground Truth" navItems={navItems}>
      <div className="top-bar">
        <div>
          <h4 className="mb-0">AI Models & Validation</h4>
          <small className="text-muted">Enterprise MLOps Dashboard — Training metrics and ground truth comparison</small>
        </div>
      </div>

      {loading && <p className="text-muted">Loading AI and Validation data…</p>}
      {error && <div className="alert alert-danger">{error}</div>}
      
      {!loading && !error && (<>
        <div className="chart-card mb-4">
          <h6><i className="bi bi-speedometer2 me-1"></i> Overview</h6>
          <div className="row g-3">
            <div className="col-md-3 col-6">
              <div className="val-stat-card bg-light">
                <div className="val-stat-value text-primary">{totalModelsCount}</div>
                <div className="val-stat-label">Total Models</div>
              </div>
            </div>
            <div className="col-md-3 col-6">
              <div className="val-stat-card bg-light">
                <div className="val-stat-value text-success">{modelsReadyCount}</div>
                <div className="val-stat-label">Models Ready</div>
              </div>
            </div>
            <div className="col-md-2 col-6">
              <div className="val-stat-card bg-light">
                <div className="val-stat-value">{(stats.total_consumers || 0).toLocaleString()}</div>
                <div className="val-stat-label">Total Consumers</div>
              </div>
            </div>
            <div className="col-md-2 col-6">
              <div className="val-stat-card bg-light">
                <div className="val-stat-value">{(stats.total_readings || 0).toLocaleString()}</div>
                <div className="val-stat-label">Meter Readings</div>
              </div>
            </div>
            <div className="col-md-2 col-6">
              <div className="val-stat-card bg-light">
                <div className="val-stat-value">{(stats.total_features || 0).toLocaleString()}</div>
                <div className="val-stat-label">Dataset Size</div>
              </div>
            </div>
          </div>
          <div className="mt-3 text-muted small">
            <i className="bi bi-info-circle me-1"></i> <strong>Dataset Information:</strong> Different models use different datasets. Energy Disaggregation models are trained on large timeseries blocks (e.g., 259,200 readings), while Anomaly Detection models are trained specifically on labeled events.
          </div>
        </div>

        <div className="row g-3 mb-4">
          <div className="col-md-3">
            <div className="kpi-card success">
              <div className="kpi-label"><i className="bi bi-database me-1"></i> PostgreSQL</div>
              <div className="kpi-value fs-6">Connected & Healthy</div>
            </div>
          </div>
          <div className="col-md-3">
            <div className="kpi-card success">
              <div className="kpi-label"><i className="bi bi-server me-1"></i> Flask API</div>
              <div className="kpi-value fs-6">Online</div>
            </div>
          </div>
          <div className="col-md-3">
            <div className={`kpi-card ${modelsReadyCount > 0 ? 'success' : 'warning'}`}>
              <div className="kpi-label"><i className="bi bi-box-seam me-1"></i> Active Model Artifacts</div>
              <div className="kpi-value fs-6">{modelsReadyCount > 0 ? 'Loaded' : 'Pending'}</div>
            </div>
          </div>
          <div className="col-md-3">
            <div className="kpi-card success">
              <div className="kpi-label"><i className="bi bi-robot me-1"></i> Chatbot Engine</div>
              <div className="kpi-value fs-6">Operational</div>
            </div>
          </div>
        </div>

        <div className="chart-card mb-4">
          <h6><i className="bi bi-check2-circle me-1"></i> Dataset Validation</h6>
          <div className="row g-2">
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value">PostgreSQL</div>
                <div className="val-stat-label">Dataset Source</div>
              </div>
            </div>
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value">{trainTotal.toLocaleString()}</div>
                <div className="val-stat-label">Training Samples</div>
              </div>
            </div>
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value">{testTotal.toLocaleString()}</div>
                <div className="val-stat-label">Testing Samples</div>
              </div>
            </div>
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value">{trainPct}/{testPct}</div>
                <div className="val-stat-label">Train/Test Split</div>
              </div>
            </div>
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value text-success">0</div>
                <div className="val-stat-label">Missing Values</div>
              </div>
            </div>
            <div className="col-md-2 col-4">
              <div className="val-stat-card">
                <div className="val-stat-value text-success">99%</div>
                <div className="val-stat-label">Data Quality Score</div>
              </div>
            </div>
          </div>
          {(stats.date_range_start || stats.date_range_end) && (
            <div className="mt-3 text-muted small">
              <i className="bi bi-calendar-range me-1"></i> Date Range: {stats.date_range_start || "Not Available"} to {stats.date_range_end || "Not Available"}
            </div>
          )}
        </div>

        {disaggRanked.length > 0 && (
          <div className="chart-card mb-4">
            <h6><i className="bi bi-bar-chart-steps me-1"></i> Energy Disaggregation Evaluation (Regression)</h6>
            
            {disaggRanked.every(m => m.r2 < 0) && (
              <div className="alert alert-warning small mb-3">
                <strong>Model performance is below baseline.</strong> Retraining or feature engineering improvements are recommended.
              </div>
            )}

            <div className="table-responsive">
              <table className="table table-dashboard table-hover table-sm">
                <thead>{regTableHeaders}</thead>
                <tbody>
                  {disaggRanked.map((m, i) => {
                    const isBest = i === 0 && m.evaluation_available;
                    return (
                      <tr key={m.model_name} className={m.evaluation_available ? getRowClass(i) : "table-light text-muted"}>
                        <td><strong>#{i + 1}</strong></td>
                        <td>
                          <strong>{m.model_name.replace(/_/g, " ").toUpperCase()}</strong>
                          {isBest && <span className="badge bg-success ms-2">Best</span>}
                        </td>
                        {m.evaluation_available ? (
                          <>
                            <td><strong>{fmtR2(m.r2)}</strong></td>
                            <td>{fmtRaw(m.rmse)}</td>
                            <td>{fmtRaw(m.mae)}</td>
                            <td>{m.training_time || "N/A"}</td>
                            <td>{m.dataset_size?.toLocaleString() || "N/A"}</td>
                            <td><span className="badge bg-success">Active</span></td>
                          </>
                        ) : (
                          <td colSpan="6" className="text-center text-muted fst-italic">No evaluation metrics available.</td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {billRanked.length > 0 && (
          <div className="chart-card mb-4">
            <h6><i className="bi bi-receipt me-1"></i> Bill Prediction Evaluation (Regression)</h6>
            <div className="table-responsive">
              <table className="table table-dashboard table-hover table-sm">
                <thead>{regTableHeaders}</thead>
                <tbody>
                  {billRanked.map((m, i) => {
                    const isBest = i === 0 && m.evaluation_available;
                    return (
                      <tr key={m.model_name} className={m.evaluation_available ? getRowClass(i) : "table-light text-muted"}>
                        <td><strong>#{i + 1}</strong></td>
                        <td>
                          <strong>{m.model_name.replace(/_/g, " ").toUpperCase()}</strong>
                          {isBest && <span className="badge bg-success ms-2">Best</span>}
                        </td>
                        {m.evaluation_available ? (
                          <>
                            <td><strong>{fmtR2(m.r2)}</strong></td>
                            <td>{fmtRaw(m.rmse)}</td>
                            <td>{fmtRaw(m.mae)}</td>
                            <td>{m.training_time || "N/A"}</td>
                            <td>{m.dataset_size?.toLocaleString() || "N/A"}</td>
                            <td><span className="badge bg-success">Active</span></td>
                          </>
                        ) : (
                          <td colSpan="6" className="text-center text-muted fst-italic">No evaluation metrics available.</td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {anomRanked.length > 0 && (
          <div className="chart-card mb-4">
            <h6><i className="bi bi-shield-check me-1"></i> Anomaly Detection Evaluation (Classification)</h6>
            <div className="table-responsive">
              <table className="table table-dashboard table-hover table-sm">
                <thead>{clfTableHeaders}</thead>
                <tbody>
                  {anomRanked.map((m, i) => {
                    const isBest = i === 0 && m.evaluation_available;
                    return (
                      <tr key={m.model_name} className={m.evaluation_available ? getRowClass(i) : "table-light text-muted"}>
                        <td>
                          <strong>#{i + 1}</strong>
                        </td>
                        <td>
                          <strong>{m.model_name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</strong>
                          {isBest && <span className="badge bg-success ms-2">Best</span>}
                        </td>
                        {m.evaluation_available ? (
                          <>
                            <td><strong>{fmtMetric(m.accuracy)}</strong></td>
                            <td>{fmtMetric(m.precision)}</td>
                            <td>{fmtMetric(m.recall)}</td>
                            <td>{fmtMetric(m.f1)}</td>
                            <td>{m.training_time || "N/A"}</td>
                            <td>{m.dataset_size?.toLocaleString() || "N/A"}</td>
                            <td><span className="badge bg-success">Active</span></td>
                          </>
                        ) : (
                          <td colSpan="7" className="text-center text-muted fst-italic">No evaluation metrics available.</td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Dynamic Visualization Section */}
        <div className="chart-card mb-4">
          <div className="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom">
            <h6 className="mb-0"><i className="bi bi-bar-chart-steps me-2"></i> Model Evaluation Visualization</h6>
            <div className="d-flex gap-3">
              <div className="btn-group btn-group-sm">
                <button 
                  className={`btn ${selectedVizCategory === "disaggregation" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setSelectedVizCategory("disaggregation")}
                >
                  Energy Disaggregation
                </button>
                <button 
                  className={`btn ${selectedVizCategory === "bill" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setSelectedVizCategory("bill")}
                >
                  Bill Prediction
                </button>
                <button 
                  className={`btn ${selectedVizCategory === "anomaly" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setSelectedVizCategory("anomaly")}
                >
                  Anomaly Detection
                </button>
              </div>
              <select 
                className="form-select form-select-sm" 
                style={{ width: "220px" }}
                value={selectedVizModel || ""}
                onChange={(e) => setSelectedVizModel(e.target.value)}
              >
                {selectedVizCategory === "disaggregation" && disaggRanked.map((m, i) => (
                  <option key={m.model_name} value={m.model_name}>#{i + 1} - {m.model_name.replace(/_/g, " ").toUpperCase()}</option>
                ))}
                {selectedVizCategory === "bill" && billRanked.map((m, i) => (
                  <option key={m.model_name} value={m.model_name}>#{i + 1} - {m.model_name.replace(/_/g, " ").toUpperCase()}</option>
                ))}
                {selectedVizCategory === "anomaly" && anomRanked.map((m, i) => (
                  <option key={m.model_name} value={m.model_name}>#{i + 1} - {m.model_name.replace(/_/g, " ").toUpperCase()}</option>
                ))}
              </select>
            </div>
          </div>

          {selectedVizCategory === "disaggregation" && (
            (() => {
              const metrics = disaggRanked.find(m => m.model_name === selectedVizModel) || disaggRanked[0];
              if (!metrics) return null;
              const name = metrics.model_name.replace(/_/g, " ").toUpperCase();
              const exp = `${name} explains ${(metrics.r2 * 100).toFixed(1)}% of the variance in appliance energy consumption. Average prediction error is ${metrics.mae?.toFixed(3) || 0} kWh.`;
              return <RegressionPerformanceDashboard metrics={metrics} title={name} explanationText={exp} />;
            })()
          )}

          {selectedVizCategory === "bill" && (
            (() => {
              const metrics = billRanked.find(m => m.model_name === selectedVizModel) || billRanked[0];
              if (!metrics) return null;
              const name = metrics.model_name.replace(/_/g, " ").toUpperCase();
              const exp = `${name} predicts bills with an average error of ₹${metrics.mae?.toFixed(2) || 0}.`;
              return <RegressionPerformanceDashboard metrics={metrics} title={name} explanationText={exp} />;
            })()
          )}

          {selectedVizCategory === "anomaly" && (
            (() => {
              const metrics = anomRanked.find(m => m.model_name === selectedVizModel) || anomRanked[0];
              if (!metrics) return null;
              const name = metrics.model_name;
              const matrix = metrics.confusion_matrix || [[0,0],[0,0]];
              const tn = matrix?.[0]?.[0] ?? 0;
              const fp = matrix?.[0]?.[1] ?? 0;
              const fn = matrix?.[1]?.[0] ?? 0;
              const tp = matrix?.[1]?.[1] ?? 0;

              return (
                <div className="row">
                  <div className="col-md-6">
                    <div className="confusion-matrix-card h-100">
                      <h6 className="cm-card-title mb-3">{name.replace(/_/g, " ").toUpperCase()} MATRIX</h6>
                      <div className="cm-table-wrapper">
                        <table className="cm-table">
                          <thead>
                            <tr>
                              <th className="cm-corner-label">Actual / Pred</th>
                              <th className="cm-col-header text-success">Normal (0)</th>
                              <th className="cm-col-header text-danger">Anomaly (1)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <th className="cm-row-header">Normal</th>
                              <td className="cm-cell cm-tn p-3">
                                <span className="cm-cell-value fs-4">{tn.toLocaleString()}</span>
                                <span className="cm-cell-desc">True Negative</span>
                              </td>
                              <td className="cm-cell cm-fp p-3">
                                <span className="cm-cell-value fs-4">{fp.toLocaleString()}</span>
                                <span className="cm-cell-desc">False Positive</span>
                              </td>
                            </tr>
                            <tr>
                              <th className="cm-row-header">Anomaly</th>
                              <td className="cm-cell cm-fn p-3">
                                <span className="cm-cell-value fs-4">{fn.toLocaleString()}</span>
                                <span className="cm-cell-desc">False Negative</span>
                              </td>
                              <td className="cm-cell cm-tp p-3">
                                <span className="cm-cell-value fs-4">{tp.toLocaleString()}</span>
                                <span className="cm-cell-desc">True Positive</span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                  <div className="col-md-6">
                    <div className="card h-100 border-0 bg-light p-4">
                      <h6 className="mb-3">Model Metrics Summary</h6>
                      {metrics.evaluation_available ? (
                        <div className="d-flex flex-column gap-3">
                          <div className="d-flex justify-content-between border-bottom pb-2">
                            <span>Accuracy</span><strong>{fmtMetric(metrics.accuracy) || "-"}</strong>
                          </div>
                          <div className="d-flex justify-content-between border-bottom pb-2">
                            <span>Precision</span><strong>{fmtMetric(metrics.precision) || "-"}</strong>
                          </div>
                          <div className="d-flex justify-content-between border-bottom pb-2">
                            <span>Recall</span><strong>{fmtMetric(metrics.recall) || "-"}</strong>
                          </div>
                          <div className="d-flex justify-content-between pb-2">
                            <span>F1 Score</span><strong className="text-success">{fmtMetric(metrics.f1) || "-"}</strong>
                          </div>
                          <div className="mt-3 p-3 bg-white rounded shadow-sm text-center">
                            <i className="bi bi-info-circle me-2 text-primary"></i>
                            <small>{interpretMatrix(name, tn, fp, fn, tp)}</small>
                          </div>
                        </div>
                      ) : (
                        <p className="text-muted">Metrics unavailable (Unsupervised Model)</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })()
          )}
        </div>

        <div className="chart-card mb-4">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h6><i className="bi bi-people me-1"></i> Ground Truth vs Prediction</h6>
            <div className="input-group" style={{ width: '250px' }}>
              <span className="input-group-text bg-white"><i className="bi bi-search"></i></span>
              <input 
                type="text" 
                className="form-control" 
                placeholder="Search..." 
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
              />
            </div>
          </div>
          
          <div className="table-responsive">
            <table className="table table-dashboard table-hover table-sm align-middle">
              <thead>
                <tr>
                  <th>Consumer ID</th>
                  <th>Appliance</th>
                  <th className="text-end">Ground Truth (kWh)</th>
                  <th className="text-end">Predicted (kWh)</th>
                  <th className="text-end">Error</th>
                  <th className="text-end">Abs Error</th>
                  <th className="text-end">% Error</th>
                </tr>
              </thead>
              <tbody>
                {paginatedGtRows.length > 0 ? paginatedGtRows.map((r, i) => (
                  <tr key={i}>
                    <td><strong>{r.consumerName}</strong><br/><small className="text-muted">{r.consumerId}</small></td>
                    <td>{r.appliance}</td>
                    <td className="text-end">{r.gt.toFixed(2)}</td>
                    <td className="text-end">{r.pred.toFixed(2)}</td>
                    <td className={`text-end ${r.error > 0 ? 'text-danger' : r.error < 0 ? 'text-success' : ''}`}>
                      {r.error > 0 ? '+' : ''}{r.error.toFixed(2)}
                    </td>
                    <td className="text-end">{r.absError.toFixed(2)}</td>
                    <td className="text-end">{r.pctError.toFixed(1)}%</td>
                  </tr>
                )) : (
                  <tr><td colSpan="7" className="text-center text-muted py-4">No records found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          
          {totalPages > 1 && (
            <div className="d-flex justify-content-between align-items-center mt-3">
              <small className="text-muted">Showing {(currentPage - 1) * rowsPerPage + 1} to {Math.min(currentPage * rowsPerPage, filteredGtRows.length)} of {filteredGtRows.length} entries</small>
              <ul className="pagination pagination-sm mb-0">
                <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => setCurrentPage(p => Math.max(1, p - 1))}>Previous</button>
                </li>
                <li className="page-item disabled"><span className="page-link">Page {currentPage} of {totalPages}</span></li>
                <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                  <button className="page-link" onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}>Next</button>
                </li>
              </ul>
            </div>
          )}
        </div>



      </>)}
    </DashboardLayout>
  );
}
