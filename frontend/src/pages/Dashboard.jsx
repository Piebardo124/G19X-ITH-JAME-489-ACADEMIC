import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Dashboard() {
  const role = localStorage.getItem('role');
  const puedeGestionarAlertas = ['admin', 'hr'].includes(role);
  const tituloPanel = role === 'executive'
    ? 'Panel Ejecutivo'
    : puedeGestionarAlertas ? 'Panel de Recursos Humanos' : 'Panel';

  // Estados para la bandeja de alertas
  const [alertas, setAlertas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [analiticas, setAnaliticas] = useState(null);
  const [errorAnaliticas, setErrorAnaliticas] = useState('');

  // Estado para la subida de archivos CSV
  const [archivoCsv, setArchivoCsv] = useState(null);
  const [subiendoCsv, setSubiendoCsv] = useState(false);
  const [mensajeCsv, setMensajeCsv] = useState('');
  const [csvImportId, setCsvImportId] = useState(null);

  const navigate = useNavigate();

  useEffect(() => {
    const obtenerPanel = async () => {
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/login');
        return;
      }

      const headers = { Authorization: `Bearer ${token}` };
      const solicitudes = [
        axios.get(`${API_BASE_URL}/api/v1/nlp/analytics`, { headers }),
      ];
      if (puedeGestionarAlertas) {
        solicitudes.push(axios.get(`${API_BASE_URL}/api/v1/alerts`, { headers }));
      }

      const resultados = await Promise.allSettled(solicitudes);
      const resultadoAnaliticas = resultados[0];
      if (resultadoAnaliticas.status === 'fulfilled') {
        setAnaliticas(resultadoAnaliticas.value.data);
      } else {
        const err = resultadoAnaliticas.reason;
        setErrorAnaliticas(err.response?.data?.detail || 'Analítica no disponible');
        if (err.response?.status === 401) {
          localStorage.removeItem('token');
          localStorage.removeItem('role');
          navigate('/login');
        }
      }

      if (puedeGestionarAlertas) {
        const resultadoAlertas = resultados[1];
        if (resultadoAlertas.status === 'fulfilled') {
          setAlertas(resultadoAlertas.value.data);
        } else {
          const err = resultadoAlertas.reason;
          setError('No se pudieron cargar las alertas.');
          if (err.response?.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('role');
            navigate('/login');
          }
        }
      }

      setCargando(false);
    };

    obtenerPanel();
  }, [navigate, puedeGestionarAlertas]);

  useEffect(() => {
    if (!csvImportId) return undefined;

    let cancelado = false;
    let timeoutId;
    const consultarEstado = async () => {
      try {
        const token = localStorage.getItem('token');
        const respuesta = await axios.get(`${API_BASE_URL}/api/v1/nlp/upload-csv/${csvImportId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (cancelado) return;

        const carga = respuesta.data;
        if (['QUEUED', 'PROCESSING'].includes(carga.status)) {
          setMensajeCsv(`Procesando CSV: ${carga.processed_rows} filas procesadas...`);
          timeoutId = setTimeout(consultarEstado, 2000);
          return;
        }

        const resumen = `${carga.processed_rows} procesadas, ${carga.skipped_rows} omitidas y ${carga.failed_rows} fallidas.`;
        if (carga.status === 'FAILED') {
          setMensajeCsv(`Error: no se pudo completar la carga. ${carga.errors || ''}`);
        } else if (carga.status === 'COMPLETED_WITH_WARNINGS') {
          setMensajeCsv(`Carga terminada con observaciones: ${resumen} ${carga.errors || ''}`);
        } else {
          setMensajeCsv(`Carga completada: ${resumen}`);
        }
        setCsvImportId(null);
      } catch (err) {
        if (!cancelado) {
          setMensajeCsv(`Error al consultar el estado de la carga: ${err.response?.data?.detail || 'intenta recargar el panel.'}`);
          setCsvImportId(null);
        }
      }
    };

    consultarEstado();
    return () => {
      cancelado = true;
      clearTimeout(timeoutId);
    };
  }, [csvImportId]);

  // Funcion para el boton de salir
  const cerrarSesion = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  
  // Conector de Endpoint PATCH
  const marcarComoAtendida = async (id) => {
    try {
      const token = localStorage.getItem('token');

      // Peticion de actualizacion de FastAPI
      await axios.patch(`${API_BASE_URL}/api/v1/alerts/${id}`,
        { status: 'CLOSED' },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setAlertas(alertas.map(alerta => 
        alerta.id === id ? { ...alerta, status: 'CLOSED' } : alerta
      ));

    } catch (err) {
      console.error("Error al actualizar la alerta:", err);
      alert("Hubo un error al intentar actualizar el estatus.");
    }
  };

  // Manejar archivos de subida CSV
  const manejarSubidaCsv = async (e) => {
    e.preventDefault();
    if (!archivoCsv) return;

    setSubiendoCsv(true);
    setMensajeCsv('');

    const formData = new FormData();
    formData.append('file', archivoCsv);

    try {
      const token = localStorage.getItem('token');
      const respuesta = await axios.post(`${API_BASE_URL}/api/v1/nlp/upload-csv`, formData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      setMensajeCsv(respuesta.data.message);
      setCsvImportId(respuesta.data.import_id);
      setArchivoCsv(null);

      // Reseteo campo de archivo en HTML
      document.getElementById('csvInput').value = '';
    } catch (err) {
      console.error("Error al subir CSV:", err);
      const errorDetail = err.response?.data?.detail || "Error desconocido al procesar el archivo.";
      setMensajeCsv(`Error: ${errorDetail}`);
    } finally {
      setSubiendoCsv(false);
    }
  }

  return (
    <div style={{ maxWidth: '800px', margin: '50px auto', fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>{tituloPanel}</h2>
        <button 
          onClick={cerrarSesion}
          style={{ padding: '8px 12px', backgroundColor: '#ef4444', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
        >
          Cerrar Sesión
        </button>
      </div>
      <p style={{ color: '#64748b' }}>Monitoreo de incidencias y riesgo de burnout.</p>

      {/* Panel Analítico Resumen */}
      <div style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', padding: '20px', borderRadius: '8px', marginBottom: '25px', display: 'flex', gap: '20px', justifyContent: 'space-around' }}>
          {errorAnaliticas ? (
              <p style={{ color: '#b45309', margin: 0, fontWeight: 'bold' }}>{errorAnaliticas}</p>
          ) : analiticas ? (
              <>
                  <div style={{ textAlign: 'center' }}>
                      <h3 style={{ margin: '0 0 10px 0', color: '#334155' }}>Volumen Global</h3>
                      <p style={{ fontSize: '24px', fontWeight: 'bold', margin: 0, color: '#2563eb' }}>{analiticas.total_responses}</p>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                      <h3 style={{ margin: '0 0 10px 0', color: '#334155' }}>IGS Promedio</h3>
                      <p style={{ fontSize: '24px', fontWeight: 'bold', margin: 0, color: analiticas.average_polarity == null ? '#64748b' : analiticas.average_polarity >= 0.25 ? '#059669' : analiticas.average_polarity <= -0.25 ? '#dc2626' : '#d97706' }}>
                          {analiticas.average_polarity == null ? 'Sin datos' : `${analiticas.average_polarity > 0 ? '+' : ''}${analiticas.average_polarity}`}
                      </p>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                      <h3 style={{ margin: '0 0 10px 0', color: '#334155' }}>Distribución</h3>
                      <div style={{ display: 'flex', gap: '10px', fontSize: '14px', fontWeight: 'bold' }}>
                          <span style={{ color: '#059669' }}>Pos: {analiticas.distribution?.Positivo || 0}</span>
                          <span style={{ color: '#d97706' }}>Neu: {analiticas.distribution?.Neutral || 0}</span>
                          <span style={{ color: '#dc2626' }}>Neg: {analiticas.distribution?.Negativo || 0}</span>
                      </div>
                  </div>
              </>
          ) : (
              <p style={{ margin: 0, color: '#64748b' }}>Cargando analíticas...</p>
          )}
      </div>

      {puedeGestionarAlertas && <>
      {/* Panel de Carga Masiva (CSV) */}
      <div style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', padding: '20px', borderRadius: '8px', marginBottom: '25px' }}>
        <h4 style={{ marginTop: '0', color: '#334155' }}>Carga Masiva de Comentarios Históricos</h4>
        <form onSubmit={manejarSubidaCsv} style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input 
            id="csvInput"
            type="file" 
            accept=".csv"
            onChange={(e) => setArchivoCsv(e.target.files[0])}
            style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '5px', backgroundColor: '#ffffff', cursor: 'pointer' }}
          />
          <button 
            type="submit" 
            disabled={subiendoCsv || !archivoCsv}
            style={{ 
              padding: '10px 15px', 
              backgroundColor: subiendoCsv ? '#94a3b8' : '#10b981', 
              color: 'white', border: 'none', borderRadius: '5px', 
              cursor: subiendoCsv || !archivoCsv ? 'not-allowed' : 'pointer',
              fontWeight: 'bold'
            }}
          >
            {subiendoCsv ? 'Enviando al Motor IA...' : 'Procesar CSV en Segundo Plano'}
          </button>
        </form>
        {mensajeCsv && (
          <p style={{
            marginTop: '15px',
            marginBottom: '0',
            fontWeight: '500',
            color: mensajeCsv.startsWith('Carga completada:') ? '#059669' : mensajeCsv.startsWith('Carga terminada con observaciones:') ? '#b45309' : '#dc2626'
          }}>
            {mensajeCsv}
          </p>
        )}
      </div>

      {/* Condicionales de carga y error */}
      {cargando ? (
        <p>Cargando información...</p>
      ) : error ? (
        <p style={{ color: 'red' }}>{error}</p>
      ) : (
        <div style={{ overflowX: 'auto', marginTop: '20px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc', borderBottom: '2px solid #cbd5e1' }}>
                <th style={{ padding: '12px' }}>ID</th>
                <th style={{ padding: '12px' }}>Nivel de Riesgo</th>
                <th style={{ padding: '12px' }}>Motivo detectado por IA</th>
                <th style={{ padding: '12px' }}>Estatus</th>
                <th style={{ padding: '12px', textAlign: 'center' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {alertas.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ padding: '15px', textAlign: 'center', color: '#64748b' }}>
                    Sin alertas registradas por el momento.
                  </td>
                </tr>
              ) : (
                alertas.map((alerta) => (
                  <tr key={alerta.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                    <td style={{ padding: '12px', color: '#64748b' }}>#{alerta.id}</td>
                    <td style={{ padding: '12px', fontWeight: 'bold', color: alerta.risk_level === 'ALTO' ? '#ef4444' : '#f59e0b' }}>
                      {alerta.risk_level}
                    </td>
                    <td style={{ padding: '12px' }}>{alerta.reason}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '4px 8px', borderRadius: '12px', fontSize: '0.85em', fontWeight: 'bold',
                        backgroundColor: alerta.status === 'CLOSED' ? '#d1fae5' : '#fee2e2',
                        color: alerta.status === 'CLOSED' ? '#059669' : '#b91c1c'
                      }}>
                        {alerta.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      {/* El botón solo se muestra si el estatus no es "Atendida" */}
                      {alerta.status !== 'CLOSED' && (
                        <button
                          onClick={() => marcarComoAtendida(alerta.id)}
                          style={{
                            padding: '6px 12px', backgroundColor: '#3b82f6', color: 'white',
                            border: 'none', borderRadius: '5px', cursor: 'pointer', fontSize: '0.85em'
                          }}
                        >
                          Marcar Atendida
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      </>}
    </div>
  );
}

export default Dashboard;
