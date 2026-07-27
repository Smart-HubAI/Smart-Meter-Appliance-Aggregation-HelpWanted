import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

const ROLE_REDIRECTS = {
  consumer: "/home",
  admin: "/admin",
  developer: "/admin",
};

export default function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, user, loading } = useAuth();
  const location = useLocation();
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    if (isAuthenticated && user && allowedRoles && !allowedRoles.includes(user.role)) {
      setDenied(true);
      const timer = setTimeout(() => {
        // Component will redirect via the Navigate below
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, user, allowedRoles]);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: "100vh" }}>
        <div className="text-center">
          <div className="spinner-border text-primary mb-2" role="status"></div>
          <p className="text-muted">Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  if (user && allowedRoles && !allowedRoles.includes(user.role)) {
    const redirectPath = ROLE_REDIRECTS[user.role] || "/";
    return (
      <div className="access-denied-page">
        <div className="access-denied-card">
          <i className="bi bi-shield-lock display-1 text-danger"></i>
          <h3>Access Denied</h3>
          <p className="text-muted">You do not have permission to access this page.</p>
          <p className="small text-muted">Redirecting to your dashboard…</p>
          <Navigate to={redirectPath} replace />
        </div>
      </div>
    );
  }

  return children;
}
