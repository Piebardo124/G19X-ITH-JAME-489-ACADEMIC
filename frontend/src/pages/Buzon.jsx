import {useState, useEffect} from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Buzon() {
  const [texto, setTexto] = useState('');
  const [departamentoId, setDepartamentoId] = useState('');
  const [cargando, setCargando] = useState(false);
  const [mensajeExito, setMensajeExito] = useState('');

  // Lista estatica de departamentos
  const [departamentos, setDepartamentos] = useState([]);

  // Cargado de departamentos al abrir pagina
  useEffect(() => {
    const fetchDepartamentos = async () => {
      try {
        const respuesta = await axios.get(`${API_BASE_URL}/api/v1/nlp/departments`);
        setDepartamentos(respuesta.data);
      } catch (error) {
        console.error("Error al cargar el catálogo de departamentos:", error);
        alert("No se pudo cargar el catálogo de departamentos. Por favor, recarga la página o intenta más tarde.");
      }
    };
    fetchDepartamentos();
  }, []);

  const manejarEnvio = async (e) => {
    e.preventDefault();

    const textoLimpio = texto.trim();
    if (textoLimpio.length < 5 || textoLimpio.length > 3000 || !/\p{L}{2,}/u.test(textoLimpio)) {
        alert("El comentario debe tener entre 5 y 3000 caracteres e incluir una palabra con al menos dos letras.");
        return;
    }

    setCargando(true);
    try {
      // Logica de React para llamar a FastAPI en Docker
      const respuesta = await axios.post(`${API_BASE_URL}/api/v1/nlp/analyze-feedback`, {
        text_content: textoLimpio,
        is_anonymous: true,
        department_id:  departamentoId ? parseInt(departamentoId) : null
      });

      setTexto('');
      setDepartamentoId('');

      setMensajeExito(respuesta.data.message || "Tu comentario fue registrado.");

      // Ocultar mensaje despues de 5 segundos
      setTimeout(() => setMensajeExito(''), 5000);
    } catch (error) {
      console.error("Error al enviar:", error.message);
      const detalle = error.response?.data?.detail;
      alert(detalle || "No se pudo enviar el comentario. Intenta de nuevo.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '50px auto', fontFamily: 'sans-serif', textAlign: 'center', backgroundColor: '#ffffff', padding: '30px', borderRadius: '10px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
      <h1 style={{ color: '#1e293b' }}>PluriOne - Buzón Organizacional</h1>
      <p style={{ color: '#64748b', marginBottom: '30px' }}>Tu voz es importante. Cuéntanos cómo te sientes en tu entorno de trabajo.</p>

      {mensajeExito && (
        <div style={{ backgroundColor: '#d1fae5', color: '#065f46', padding: '15px', borderRadius: '5px', marginBottom: '20px', fontWeight: 'bold' }}>
          {mensajeExito}
        </div>
      )}

      <form onSubmit={manejarEnvio} style={{ display: 'flex', flexDirection: 'column', gap: '20px', textAlign: 'left' }}>

        {/* Selector de Departamento Dinámico */}
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#334155' }}>Área o Departamento (Opcional)</label>
          <select
            value={departamentoId}
            onChange={(e) => setDepartamentoId(e.target.value)}
            style={{ width: '100%', padding: '10px', fontSize: '16px', borderRadius: '5px', border: '1px solid #cbd5e1' }}
          >
            <option value="">Selecciona tu área...</option>
            {departamentos.map(dep => (
              <option key={dep.id} value={dep.id}>{dep.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#334155' }}>Tus comentarios</label>
          <textarea
            rows="6"
            placeholder="Ej. Las nuevas herramientas nos han ayudado mucho, pero la carga de trabajo este mes ha sido muy pesada..."
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            style={{ width: '100%', padding: '10px', fontSize: '16px', borderRadius: '5px', border: '1px solid #cbd5e1', resize: 'vertical', boxSizing: 'border-box' }}
            required
            minLength="5"
            maxLength="3000"
          />
        </div>

        <div style={{ color: '#475569', fontSize: '15px' }}>
          Los comentarios se guardan sin vincularlos a una cuenta. Evita incluir nombres o datos que te identifiquen; la detección automática puede no ocultar todos los datos personales.
        </div>

        <button
          type="submit"
          disabled={cargando}
          style={{
            marginTop: '10px', padding: '15px', fontSize: '16px', fontWeight: 'bold', backgroundColor: cargando ? '#94a3b8' : '#2563eb',
            color: 'white', border: 'none', borderRadius: '5px', cursor: cargando ? 'not-allowed' : 'pointer', transition: 'background-color 0.3s'
          }}
        >
          {cargando ? 'Procesando y analizando datos...' : 'Enviar Retroalimentación'}
        </button>
      </form>
    </div>
  );
}
export default Buzon;
