import { useEffect, useRef } from 'react';

export default function CargaCsv({ manejarSubidaCsv, archivoCsv, setArchivoCsv, subiendoCsv, mensajeCsv }) {
    const inputArchivoRef = useRef(null);

    useEffect(() => {
        if (!archivoCsv && inputArchivoRef.current) {
            inputArchivoRef.current.value = '';
        }
    }, [archivoCsv]);

    return (
        <div style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', padding: '20px', borderRadius: '8px', marginBottom: '25px' }}>
            <h4 style={{ marginTop: '0', color: '#334155' }}>Carga Masiva de Comentarios Históricos</h4>
            <form onSubmit={manejarSubidaCsv} style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap' }}>
                <input
                    ref={inputArchivoRef}
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
    );
}
