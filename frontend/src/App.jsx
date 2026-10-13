import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Buzon from './pages/Buzon';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';

function App () {
  return (
    <BrowserRouter>
      <Routes>
        {/* Ruta publica para los empleados*/}
        <Route path="/" element={<Buzon />} />

        {/* Ruta administrativas para RH*/}
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<Dashboard />} />

        {/* Ruta por defecto*/}
        <Route path="*" element={<Navigate to ="/"/>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
