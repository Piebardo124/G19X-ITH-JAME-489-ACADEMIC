import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Buzon from './pages/Buzon';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

function App () {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Buzon />} />

        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />

        <Route path="*" element={<Navigate to ="/"/>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
