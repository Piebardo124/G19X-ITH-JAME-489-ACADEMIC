import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Buzon from './pages/Buzon';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

const DASHBOARD_ROLES = ['admin', 'hr', 'analyst', 'executive'];

function ProtectedDashboard() {
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role');

  if (!token || !DASHBOARD_ROLES.includes(role)) {
    return <Navigate to="/login" replace />;
  }

  return <Dashboard />;
}

function App () {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Buzon />} />

        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<ProtectedDashboard />} />

        <Route path="*" element={<Navigate to ="/"/>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
