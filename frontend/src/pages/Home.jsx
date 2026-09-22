import { Link } from "react-router-dom";

export default function Home() {
  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark" style={{ background: "#0a1628" }}>
        <div className="container">
          <Link className="navbar-brand fw-bold" to="/">
            <i className="bi bi-lightning-charge-fill text-warning"></i> Power Insights
          </Link>
          <div className="navbar-nav ms-auto flex-row gap-3">
            <Link className="nav-link active" to="/">Home</Link>
            <Link className="nav-link" to="/consumer">Consumer Dashboard</Link>
            <Link className="nav-link" to="/admin">Admin Dashboard</Link>
            <Link className="nav-link" to="/ai">AI Models</Link>
          </div>
        </div>
      </nav>

      <section className="hero-section">
        <div className="floating-shapes">
          <div className="floating-shape"></div>
          <div className="floating-shape"></div>
          <div className="floating-shape"></div>
        </div>
        <div className="container position-relative" style={{ zIndex: 1 }}>
          <div className="row align-items-center">
            <div className="col-lg-8">
              <span className="hero-badge mb-3">
                <i className="bi bi-star-fill text-warning"></i> Smart Meter Intelligence Platform
              </span>
              <h1 className="hero-title mb-3">
                AI-Powered Smart Meter Energy Disaggregation &amp; Consumer Analytics
              </h1>
              <p className="hero-subtitle mb-4">
                Professional Tata Power–style utility operations platform. 100 consumers, 288,000 AMI
                readings, ML disaggregation, fraud detection, revenue risk scoring, and operational prioritization.
              </p>
              <div className="hero-actions">
                <Link to="/consumer" className="btn-hero-primary">
                  <i className="bi bi-person-circle"></i> Consumer Dashboard
                </Link>
                <Link to="/admin" className="btn-hero-outline">
                  <i className="bi bi-building"></i> Utility Admin
                </Link>
              </div>
            </div>
            <div className="col-lg-4 d-none d-lg-block text-center">
              <i className="bi bi-speedometer2" style={{ fontSize: "12rem", opacity: 0.2 }}></i>
            </div>
          </div>
        </div>
      </section>

      <section className="container py-5">
        <div className="text-center mb-5">
          <h2 className="fw-bold text-primary">Platform Capabilities</h2>
          <p className="text-muted">Enterprise smart metering analytics with ML pipelines</p>
        </div>
        <div className="row g-4">
          {[
            ["bi-graph-up", "Consumption Analytics", "Daily, weekly, monthly trends from 15-minute AMI data."],
            ["bi-plug", "AI Energy Disaggregation", "Random Forest, XGBoost, Gradient Boosting NILM models."],
            ["bi-shield-exclamation", "Fraud & Anomaly Detection", "Isolation Forest, RF, XGBoost on daily features."],
            ["bi-currency-rupee", "Revenue Risk Scoring", "Outstanding dues, payment status, utility priority queue."],
            ["bi-cpu", "ML Operations", "Model comparison, training metrics, validation dashboards."],
            ["bi-people", "100 Consumer Fleet", "Segmented residential profiles with realistic appliance simulation."],
          ].map(([icon, title, desc]) => (
            <div className="col-md-6 col-lg-4" key={title}>
              <div className="feature-card">
                <div className="feature-icon"><i className={`bi ${icon}`}></i></div>
                <h5>{title}</h5>
                <p className="text-muted mb-0">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="footer-utility">
        Smart Meter Intelligence Platform · Flask REST API · React · SQLite · Scikit-Learn · XGBoost
      </footer>
    </>
  );
}
