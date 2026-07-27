import { Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import Login from "./pages/Login";
import ConsumerHome from "./pages/ConsumerHome";
import Consumer from "./pages/Consumer";
import Admin from "./pages/Admin";
import AI from "./pages/AI";
import ProtectedRoute from "./components/ProtectedRoute";
import Chatbot from "./components/Chatbot";

function AppContent() {
  const location = useLocation();
  const showChatbot = location.pathname !== "/";

  return (
    <>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route
          path="/home"
          element={
            <ProtectedRoute allowedRoles={["consumer", "admin", "developer"]}>
              <ConsumerHome />
            </ProtectedRoute>
          }
        />
        <Route
          path="/consumer"
          element={
            <ProtectedRoute allowedRoles={["consumer", "admin", "developer"]}>
              <Consumer />
            </ProtectedRoute>
          }
        />
        <Route
          path="/consumer/:consumerId"
          element={
            <ProtectedRoute allowedRoles={["consumer", "admin", "developer"]}>
              <Consumer />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={["admin", "developer"]}>
              <Admin />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai"
          element={
            <ProtectedRoute allowedRoles={["developer"]}>
              <AI />
            </ProtectedRoute>
          }
        />
      </Routes>
      {showChatbot && <Chatbot />}
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
