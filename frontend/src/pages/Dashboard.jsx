import { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

import CargaCsv from '../components/CargaCsv';
import MetricasSentimiento from '../components/MetricasSentimiento';
import BandejaAlertas from '../components/BandejaAlertas';
import { mensajeError } from '../utils/errors';
import {
  clearCsvImport, csvImportMessage, csvImportStorageKey, loadCsvImport, pollCsvImport, saveCsvImport,
} from '../utils/csvImport';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Dashboard() {
  const role = localStorage.getItem('role');
  const puedeGestionarAlertas = ['admin', 'hr', 'analyst'].includes(role);
  const csvStorageKey = csvImportStorageKey(localStorage.getItem('token'));
  const tituloPanel = role === 'executive'
    ? 'Panel Ejecutivo'
    : puedeGestionarAlertas ? 'Panel de Recursos Humanos' : 'Panel';

  const [alertas, setAlertas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [analiticas, setAnaliticas] = useState(null);
  const [errorAnaliticas, setErrorAnaliticas] = useState('');
  const [departamentos, setDepartamentos] = useState([]);
  const [departamentoFiltro, setDepartamentoFiltro] = useState('');
  const [periodoFiltro, setPeriodoFiltro] = useState(() => {
    const ahora = new Date();
    return `${ahora.getFullYear()}-${String(ahora.getMonth() + 1).padStart(2, '0')}`;
  });

  const [archivoCsv, setArchivoCsv] = useState(null);
  const [subiendoCsv, setSubiendoCsv] = useState(false);
  const [mensajeCsv, setMensajeCsv] = useState('');
  const [tipoMensajeCsv, setTipoMensajeCsv] = useState('progress');
  const [csvImportId, setCsvImportId] = useState(() => puedeGestionarAlertas ? loadCsvImport(csvStorageKey) : null);
  const [errorConsultaCsv, setErrorConsultaCsv] = useState(false);
  const [csvPollKey, setCsvPollKey] = useState(0);
  const [alertRefreshKey, setAlertRefreshKey] = useState(0);
  const [paginaAlertas, setPaginaAlertas] = useState(1);
  const [hayMasAlertas, setHayMasAlertas] = useState(false);
  const [filtrosAlertas, setFiltrosAlertas] = useState({
    status_filter: '',
    risk_level: '',
    department_id: '',
    date_from: '',
    date_to: '',
  });

  const navigate = useNavigate();

  useEffect(() => {
    let cancelado = false;
    const obtenerPanel = async () => {
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/login');
        return;
      }

      const headers = { Authorization: `Bearer ${token}` };
      const solicitudes = [];
      let indiceAnaliticas = null;
      let indiceAlertas = null;

      if (departamentoFiltro && periodoFiltro) {
        setAnaliticas(null);
        setErrorAnaliticas('');
        const [anio, mes] = periodoFiltro.split('-').map(Number);
        const ultimoDia = new Date(anio, mes, 0).getDate();
        const params = {
          department_id: Number(departamentoFiltro),
          start_date: `${periodoFiltro}-01`,
          end_date: `${periodoFiltro}-${String(ultimoDia).padStart(2, '0')}`,
        };
        indiceAnaliticas = solicitudes.length;
        solicitudes.push(axios.get(`${API_BASE_URL}/api/v1/nlp/stats`, { headers, params }));
      } else {
        setAnaliticas(null);
        setErrorAnaliticas('Selecciona un departamento y un mes para consultar métricas protegidas.');
      }

      if (puedeGestionarAlertas) {
        indiceAlertas = solicitudes.length;
        const params = Object.fromEntries(
          Object.entries(filtrosAlertas).filter(([, value]) => value !== '')
        );
        params.page = paginaAlertas;
        params.page_size = 50;
        solicitudes.push(axios.get(`${API_BASE_URL}/api/v1/alerts/`, { headers, params }));
      }

      if (solicitudes.length === 0) {
        setCargando(false);
        return;
      }

      setCargando(true);
      const resultados = await Promise.allSettled(solicitudes);
      if (!cancelado) {
        if (indiceAnaliticas !== null) {
          const resultadoAnaliticas = resultados[indiceAnaliticas];
          if (resultadoAnaliticas.status === 'fulfilled') {
            setAnaliticas(resultadoAnaliticas.value.data);
            setErrorAnaliticas('');
          } else {
            const err = resultadoAnaliticas.reason;
            setErrorAnaliticas(mensajeError(err, 'Analítica no disponible'));
            if (err.response?.status === 401) {
              localStorage.removeItem('token');
              localStorage.removeItem('role');
              navigate('/login');
            }
          }
        }

        if (indiceAlertas !== null) {
          const resultadoAlertas = resultados[indiceAlertas];
          if (resultadoAlertas.status === 'fulfilled') {
            setAlertas(resultadoAlertas.value.data);
            setError('');
            setHayMasAlertas(resultadoAlertas.value.headers['x-has-more'] === 'true');
          } else {
            const err = resultadoAlertas.reason;
            setError('No se pudieron cargar las alertas.');
            setHayMasAlertas(false);
            if (err.response?.status === 401) {
              localStorage.removeItem('token');
              localStorage.removeItem('role');
              navigate('/login');
            }
          }
        }

        setCargando(false);
      }
    };

    obtenerPanel();
    return () => {
      cancelado = true;
    };
  }, [navigate, puedeGestionarAlertas, departamentoFiltro, periodoFiltro, filtrosAlertas, alertRefreshKey, paginaAlertas]);

  const cambiarFiltrosAlertas = (actualizar) => {
    setFiltrosAlertas(actualizar);
    setPaginaAlertas(1);
  };

  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/v1/nlp/departments`)
      .then((respuesta) => {
        setDepartamentos(respuesta.data);
        if (respuesta.data.length > 0) {
          setDepartamentoFiltro((actual) => actual || String(respuesta.data[0].id));
        }
      })
      .catch((err) => console.error('No se pudieron cargar los departamentos:', err.message));
  }, []);

  useEffect(() => {
    if (!csvImportId || !puedeGestionarAlertas) return undefined;

    return pollCsvImport({
      requestStatus: async ({ signal }) => {
        const token = localStorage.getItem('token');
        const response = await axios.get(`${API_BASE_URL}/api/v1/nlp/upload-csv/${csvImportId}`, {
          headers: { Authorization: `Bearer ${token}` }, signal, timeout: 15000,
        });
        return response.data;
      },
      onProgress: (job) => {
        setMensajeCsv(csvImportMessage(job).message);
        setTipoMensajeCsv('progress');
        setErrorConsultaCsv(false);
      },
      onTerminal: (job) => {
        const result = csvImportMessage(job);
        setMensajeCsv(result.message);
        setTipoMensajeCsv(result.type);
        setErrorConsultaCsv(false);
        // Una carga fallida puede conservar resultados parciales.
        setPaginaAlertas(1);
        setAlertRefreshKey((actual) => actual + 1);
        clearCsvImport(csvStorageKey);
        setCsvImportId(null);
      },
      onProblem: ({ error, retrying }) => {
        const detail = mensajeError(error, 'No se pudo contactar con el servidor.');
        setMensajeCsv(`No se pudo consultar la carga: ${detail} ${retrying
          ? 'Volveremos a consultar automáticamente.'
          : 'Puedes volver a consultar su estado.'} El archivo no necesita enviarse de nuevo.`);
        setTipoMensajeCsv('warning');
        setErrorConsultaCsv(true);
      },
      onMissing: () => {
        setMensajeCsv('La importación ya no está disponible; revisa los resultados antes de reenviar el archivo.');
        setTipoMensajeCsv('warning');
        setErrorConsultaCsv(false);
        clearCsvImport(csvStorageKey);
        setCsvImportId(null);
      },
      onSessionExpired: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('role');
        navigate('/login');
      },
    });
  }, [csvImportId, csvPollKey, csvStorageKey, navigate, puedeGestionarAlertas]);

  const cerrarSesion = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };


  const actualizarEstadoAlerta = async (id, status) => {
    try {
      const token = localStorage.getItem('token');

      await axios.patch(`${API_BASE_URL}/api/v1/alerts/${id}`,
        { status },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setAlertRefreshKey((actual) => actual + 1);

    } catch (err) {
      console.error("Error al actualizar la alerta:", err.message);
      setError('No se pudo actualizar el estado de la alerta. Intenta de nuevo.');
    }
  };

  const manejarSubidaCsv = async (e) => {
    e.preventDefault();
    if (!archivoCsv || subiendoCsv || csvImportId) return;

    setSubiendoCsv(true);
    setMensajeCsv('');
    setTipoMensajeCsv('progress');

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
      saveCsvImport(csvStorageKey, respuesta.data.import_id);
      setCsvImportId(respuesta.data.import_id);
      setErrorConsultaCsv(false);
      setArchivoCsv(null);
    } catch (err) {
      console.error("Error al subir CSV:", err.message);
      const errorDetail = mensajeError(err, "Error desconocido al procesar el archivo.");
      setMensajeCsv(`Error: ${errorDetail}`);
      setTipoMensajeCsv('error');
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

      {/* Métricas */}
      <MetricasSentimiento
        analiticas={analiticas}
        errorAnaliticas={errorAnaliticas}
        departamentos={departamentos}
        departamentoFiltro={departamentoFiltro}
        setDepartamentoFiltro={setDepartamentoFiltro}
        periodoFiltro={periodoFiltro}
        setPeriodoFiltro={setPeriodoFiltro}
      />

      {puedeGestionarAlertas && (
        <>
          {/* Tabla de Alertas */}
          <BandejaAlertas
            alertas={alertas}
            filtrosAlertas={filtrosAlertas}
            setFiltrosAlertas={cambiarFiltrosAlertas}
            pagina={paginaAlertas}
            hayMas={hayMasAlertas}
            cambiarPagina={setPaginaAlertas}
            actualizarEstadoAlerta={actualizarEstadoAlerta}
            departamentos={departamentos}
            cargando={cargando}
            error={error}
          />

          {/* Carga de archivo */}
          <CargaCsv
            manejarSubidaCsv={manejarSubidaCsv}
            archivoCsv={archivoCsv}
            setArchivoCsv={setArchivoCsv}
            subiendoCsv={subiendoCsv}
            importacionActiva={Boolean(csvImportId)}
            mensajeCsv={mensajeCsv}
            tipoMensajeCsv={tipoMensajeCsv}
            reintentarConsulta={errorConsultaCsv && csvImportId ? () => setCsvPollKey((actual) => actual + 1) : undefined}
          />
        </>
      )}
    </div>
  );
}

export default Dashboard;
