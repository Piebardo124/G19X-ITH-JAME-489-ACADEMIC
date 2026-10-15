import {useState} from 'react';
import axios from 'axios';
import {useNavigate} from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    // Gancho react para cambiar de pantallas
    const navigate = useNavigate();

    const manejarLogin = async (e) => {
        e.preventDefault();
        setError('');

        try {

            const formData = new URLSearchParams();
            formData.append('username', email);
            formData.append('password', password);

            const respuesta = await axios.post(`${API_BASE_URL}/api/v1/auth/login`, formData);

            // Guardado de Token en memoria del navegador
            localStorage.setItem('token', respuesta.data.access_token);
            localStorage.setItem('role', respuesta.data.role);

            navigate('/dashboard');
        } catch(err) {
            console.error("Error de login:", err.message);
            setError('Usuario o contraseña incorrectos');
        }
    };

    return (
    <div style={{ maxWidth: '400px', margin: '100px auto', fontFamily: 'sans-serif', textAlign: 'center' }}>
      <h2>Acceso Recursos Humanos</h2>
      <p>Inicia sesión para ver las incidencias</p>
      
      <form onSubmit={manejarLogin} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <input
          type="email"
          placeholder="Correo electrónico"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ padding: '10px', fontSize: '16px', borderRadius: '5px' }}
        />
        <input
          type="password"
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ padding: '10px', fontSize: '16px', borderRadius: '5px' }}
        />
        
        {error && <p style={{ color: 'red', margin: '0' }}>{error}</p>}
        
        <button 
          type="submit"
          style={{ 
            padding: '12px', fontSize: '16px', backgroundColor: '#10b981', 
            color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer' 
          }}
        >
          Entrar al Sistema
        </button>
      </form>
    </div>
  );
}

export default Login;