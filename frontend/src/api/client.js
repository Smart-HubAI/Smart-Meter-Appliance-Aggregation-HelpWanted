import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 120000,
});

// ---------------------------------------------------------------------------
// JWT interceptor — attach token to every request
// ---------------------------------------------------------------------------
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("smart_meter_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("smart_meter_token");
      localStorage.removeItem("smart_meter_user");
      window.location.href = "/";
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------
export const loginAPI = (username, password) =>
  api.post("/api/auth/login", { username, password }).then((r) => r.data);

export const logoutAPI = () =>
  api.post("/api/auth/logout").then((r) => r.data);

export const getMe = () =>
  api.get("/api/auth/me").then((r) => r.data);

// ---------------------------------------------------------------------------
// Data API
// ---------------------------------------------------------------------------
export const getConsumers = () => api.get("/api/consumers").then((r) => r.data);
export const getConsumer = (id) => api.get(`/api/consumer/${id}`).then((r) => r.data);
export const getConsumerHome = (id) => api.get(`/api/consumer/${id}/home`).then((r) => r.data);
export const getConsumersSummary = () => api.get("/api/consumers/summary").then((r) => r.data);
export const getAdmin = () => api.get("/api/admin").then((r) => r.data);
export const getAI = () => api.get("/api/ai").then((r) => r.data);
export const getValidation = () => api.get("/api/validation").then((r) => r.data);

export const getConsumerPowerFactor = (consumerId) => api.get(`/api/power-factor/consumer/${consumerId}`).then((r) => r.data);
export const getAdminPowerFactor = () => api.get("/api/power-factor/admin").then((r) => r.data);

export const updateInvestigationStatus = (data) => api.post("/api/admin/investigation/status", data).then((r) => r.data);
export const getInvestigationHistory = (consumerId) => api.get(`/api/admin/investigation/history/${consumerId}`).then((r) => r.data);

export default api;
