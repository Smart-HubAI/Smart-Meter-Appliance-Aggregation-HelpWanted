import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { loginAPI, logoutAPI, getMe } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Restore session from localStorage on mount
  useEffect(() => {
    const savedToken = localStorage.getItem("smart_meter_token");
    const savedUser = localStorage.getItem("smart_meter_user");
    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        setToken(savedToken);
        setUser(parsed);
      } catch {
        localStorage.removeItem("smart_meter_token");
        localStorage.removeItem("smart_meter_user");
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (username, password) => {
    const data = await loginAPI(username, password);
    const userData = {
      username: data.username,
      role: data.role,
      consumer_id: data.consumer_id,
      role_display: data.role_display,
      redirect: data.redirect,
    };
    setToken(data.access_token);
    setUser(userData);
    localStorage.setItem("smart_meter_token", data.access_token);
    localStorage.setItem("smart_meter_user", JSON.stringify(userData));
    return userData;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAPI();
    } catch {
      // ignore — token may be expired
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem("smart_meter_token");
    localStorage.removeItem("smart_meter_user");
    navigate("/");
  }, [navigate]);

  const isAuthenticated = !!token && !!user;

  return (
    <AuthContext.Provider value={{ user, token, isAuthenticated, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export default AuthContext;
