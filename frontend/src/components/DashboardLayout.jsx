import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/**
 * Build navigation items based on the user's role.
 */
export function getNavItems(role) {
  const items = [];

  if (role === "consumer") {
    items.push({ to: "/home", label: "Home", icon: "bi-house-door", match: "/home" });
  }
  items.push({ to: "/consumer", label: "Consumer", icon: "bi-people", match: "/consumer" });

  if (role === "admin" || role === "developer") {
    items.push({ to: "/admin", label: "Admin", icon: "bi-building", match: "/admin" });
  }

  if (role === "developer") {
    items.push(
      { to: "/ai", label: "AI Models & Validation", icon: "bi-cpu", match: "/ai" }
    );
  }

  return items;
}

/**
 * Legacy constant for backward compatibility — includes all routes.
 */
export const MAIN_NAV = [
  { to: "/consumer", label: "Consumer", icon: "bi-people", match: "/consumer" },
  { to: "/admin", label: "Admin", icon: "bi-building", match: "/admin" },
  { to: "/ai", label: "AI Models & Validation", icon: "bi-cpu", match: "/ai" },
];

export default function DashboardLayout({
  brandIcon,
  brandTitle,
  brandSubtitle,
  navItems,
  children,
  sidebarExtra,
}) {
  const location = useLocation();
  const { user, logout } = useAuth();

  const displayUsername = user?.role === "consumer" ? (user.consumer_id || user.username) : user?.username;
  const displayRole = user?.role_display || "";

  return (
    <div className="dashboard-wrapper dashboard-page">
      <button
        className="sidebar-toggle"
        onClick={() => {
          const sidebar = document.querySelector('.sidebar');
          const overlay = document.querySelector('.sidebar-overlay');
          sidebar?.classList.toggle('open');
          overlay?.classList.toggle('active');
        }}
        aria-label="Toggle navigation"
      >
        <i className="bi bi-list"></i>
      </button>
      <div className="sidebar-overlay" onClick={() => {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        sidebar?.classList.remove('open');
        overlay?.classList.remove('active');
      }}></div>
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h5>
            <i className={`bi ${brandIcon} text-warning`}></i> {brandTitle}
          </h5>
          <small>{brandSubtitle}</small>
        </div>
        <nav className="sidebar-nav flex-column nav">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`nav-link ${location.pathname.startsWith(item.match || item.to) ? "active" : ""}`}
              onClick={() => {
                const sidebar = document.querySelector('.sidebar');
                const overlay = document.querySelector('.sidebar-overlay');
                sidebar?.classList.remove('open');
                overlay?.classList.remove('active');
              }}
            >
              <i className={`bi ${item.icon}`}></i> {item.label}
            </Link>
          ))}
        </nav>
        {sidebarExtra}

        {/* User info + logout */}
        {user && (
          <div className="sidebar-user-section">
            <div className="sidebar-user-info">
              <small className="text-muted">Logged in as:</small>
              <strong className="d-block">{displayUsername}</strong>
              <small className="text-muted">Role: {displayRole}</small>
            </div>
            <button
              type="button"
              className="btn btn-outline-light btn-sm w-100 mt-2"
              onClick={logout}
            >
              <i className="bi bi-box-arrow-right me-1"></i> Logout
            </button>
          </div>
        )}
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
