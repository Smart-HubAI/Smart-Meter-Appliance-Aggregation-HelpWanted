import React from 'react';
import { fmtKwh } from "../utils/format";

function statusBadge(status) {
  let bg = "#ffc107"; // Open (Yellow)
  let text = "text-dark";
  if (status === "Assigned") { bg = "#0d6efd"; text = "text-white"; } // Blue
  else if (status === "In Progress") { bg = "#fd7e14"; text = "text-white"; } // Orange
  else if (status === "Resolved") { bg = "#198754"; text = "text-white"; } // Green
  else if (status === "Closed") { bg = "#495057"; text = "text-white"; } // Dark Gray
  
  return (
    <span className={`badge rounded-pill p-2 shadow-sm ${text}`} style={{ backgroundColor: bg, minWidth: "90px" }}>
      {status}
    </span>
  );
}

export default function InvestigationModal({ open, row, onClose, onSave, onChange }) {
  if (!open || !row) return null;
  console.log("MODAL RENDERED");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      consumer_id: row.consumer_id,
      status: row.newStatus,
      assigned_to: row.assignedTo,
      remarks: row.remarks
    });
  };

  return (
    <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1050 }}>
      <div className="modal-dialog modal-lg" style={{ marginTop: '5vh' }}>
        <div className="modal-content border-0 shadow-lg rounded-4 overflow-hidden">
          <div className="modal-header text-white bg-dark">
            <h5 className="modal-title fw-bold"><i className="bi bi-shield-exclamation me-2"></i>Investigation: {row.consumer_id}</h5>
            <button type="button" className="btn-close btn-close-white" onClick={onClose}></button>
          </div>
          <div className="modal-body p-4 bg-light" style={{ maxHeight: '80vh', overflowY: 'auto' }}>
            {/* Consumer Information */}
            <div className="card shadow-sm border-0 mb-4 rounded-3">
              <div className="card-body">
                <h6 className="fw-bold text-secondary mb-3">Consumer Information</h6>
                <div className="row g-3">
                  <div className="col-md-4">
                    <small className="text-muted d-block">Consumer ID</small>
                    <span className="fw-bold">{row.consumer_id}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Consumer Name</small>
                    <span className="fw-medium">{row.consumer_name || row.name || "N/A"}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Zone</small>
                    <span className="fw-medium">{row.zone || "N/A"}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Category</small>
                    <span className="badge bg-light text-dark border">{row.consumer_category || "N/A"}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Instantaneous Power (kW)</small>
                    <span className="fw-medium">{fmtKwh(row.today_kwh)}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Anomaly Type</small>
                    <span className="fw-medium text-danger">{row.anomalyType}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Severity</small>
                    <span className="fw-medium">{row.severity}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Risk Score</small>
                    <span className="fw-medium">{row.overall_risk_score}</span>
                  </div>
                  <div className="col-md-4">
                    <small className="text-muted d-block">Recommended Action</small>
                    <span className="fw-medium text-primary">{row.recAction}</span>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Investigation Details */}
            <div className="card shadow-sm border-0 mb-4 rounded-3">
              <div className="card-body">
                <h6 className="fw-bold text-secondary mb-3">Investigation Details</h6>
                {row.error && <div className="alert alert-danger py-2">{row.error}</div>}
                <form onSubmit={handleSubmit}>
                  <div className="row g-3">
                    <div className="col-md-4">
                      <small className="text-muted d-block mb-1">Current Status</small>
                      {statusBadge(row.status)}
                    </div>
                    <div className="col-md-4">
                      <small className="text-muted d-block mb-1">Priority</small>
                      <span className="fw-bold">{row.priority || "Normal"}</span>
                    </div>
                    <div className="col-md-4">
                      <small className="text-muted d-block mb-1">Last Updated</small>
                      <span className="text-muted small">{row.inv_last_updated ? new Date(row.inv_last_updated).toLocaleString() : "Never"}</span>
                    </div>
                    <div className="col-md-4 mt-4">
                      <label className="form-label fw-semibold small">Status Dropdown</label>
                      <select className="form-select" value={row.newStatus} onChange={e => onChange({ newStatus: e.target.value })}>
                        <option value="Open">Open</option>
                        <option value="Assigned">Assigned</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Resolved</option>
                        <option value="Closed">Closed</option>
                      </select>
                    </div>
                    <div className="col-md-8 mt-4">
                      <label className="form-label fw-semibold small">Assigned To</label>
                      <input type="text" className="form-control" placeholder="e.g. Field Team A, John Doe" value={row.assignedTo} onChange={e => onChange({ assignedTo: e.target.value })} />
                    </div>
                    <div className="col-12">
                      <label className="form-label fw-semibold small">Remarks</label>
                      <textarea className="form-control" rows="3" placeholder="Investigation details..." value={row.remarks} onChange={e => onChange({ remarks: e.target.value })}></textarea>
                    </div>
                  </div>
                  
                  <div className="mt-4 pt-3 border-top text-end">
                    <button type="button" className="btn btn-light me-2 px-4" onClick={onClose}>Cancel</button>
                    <button type="submit" className="btn btn-primary px-4 fw-bold">Save Changes</button>
                  </div>
                </form>
              </div>
            </div>

            {/* History Log */}
            <h6 className="fw-bold text-secondary mb-3">History</h6>
            <div className="card shadow-sm border-0 rounded-3">
              {row.loading ? (
                <div className="p-4 text-center text-muted">Loading history...</div>
              ) : !row.history || row.history.length === 0 ? (
                <div className="p-4 text-center text-muted">No history available.</div>
              ) : (
                <ul className="list-group list-group-flush rounded-3">
                  {row.history.map((h, i) => (
                    <li key={i} className="list-group-item p-3">
                      <div className="d-flex justify-content-between align-items-center mb-1">
                        <span className="fw-bold">{h.new_status} <small className="text-muted fw-normal">from {h.previous_status}</small></span>
                        <small className="text-muted">{new Date(h.timestamp).toLocaleString()}</small>
                      </div>
                      <div className="small text-secondary mb-1"><i className="bi bi-person-fill me-1"></i>{h.changed_by}</div>
                      {h.remarks && <div className="small text-dark p-2 bg-light rounded border">{h.remarks}</div>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
