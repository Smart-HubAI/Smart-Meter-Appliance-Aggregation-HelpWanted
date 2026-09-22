import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // If already logged in, redirect
  if (isAuthenticated && user) {
    navigate(user.redirect || "/home", { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const userData = await login(username, password);
      navigate(userData.redirect || "/home", { replace: true });
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.message ||
        err?.message ||
        "Invalid username or password.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="floating-shapes">
        <div className="floating-shape"></div>
        <div className="floating-shape"></div>
        <div className="floating-shape"></div>
      </div>
      <div className="login-card">
        <div className="login-header">
          <i className="bi bi-lightning-charge-fill text-warning"></i>
          <h3>Smart Meter Intelligence Platform</h3>
          <p className="text-muted">Sign in to access your dashboard</p>
        </div>

        {error && (
          <div className="alert alert-danger py-2 mb-3 border-0 shadow-sm">
            <i className="bi bi-exclamation-triangle-fill me-1"></i> {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label htmlFor="username" className="form-label fw-semibold small text-secondary">
              Username
            </label>
            <div className="input-group">
              <span className="input-group-text bg-light border-end-0">
                <i className="bi bi-person text-muted"></i>
              </span>
              <input
                type="text"
                id="username"
                className="form-control border-start-0 ps-0"
                placeholder="Enter username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
          </div>

          <div className="mb-4">
            <label htmlFor="password" className="form-label fw-semibold small text-secondary">
              Password
            </label>
            <div className="input-group">
              <span className="input-group-text bg-light border-end-0">
                <i className="bi bi-lock text-muted"></i>
              </span>
              <input
                type="password"
                id="password"
                className="form-control border-start-0 ps-0"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary-custom w-100 btn-lg"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                Signing in…
              </>
            ) : (
              <>
                <i className="bi bi-box-arrow-in-right me-1"></i> Login
              </>
            )}
          </button>
        </form>

        <div className="login-footer">
          <small className="text-muted">
            Secure utility platform · Authorized access only
          </small>
        </div>
      </div>
    </div>
  );
}
