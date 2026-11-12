import { useEffect, useRef } from 'react';

export default function CargaCsv({ manejarSubidaCsv, archivoCsv, setArchivoCsv, subiendoCsv, importacionActiva, mensajeCsv, tipoMensajeCsv, reintentarConsulta }) {
    const inputArchivoRef = useRef(null);
    const ocupada = subiendoCsv || importacionActiva;

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
                    disabled={ocupada}
                    onChange={(e) => setArchivoCsv(e.target.files[0])}
                    style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '5px', backgroundColor: '#ffffff', cursor: 'pointer' }}
                />
                <button
                    type="submit"
                    disabled={ocupada || !archivoCsv}
                    style={{
                        padding: '10px 15px',
                        backgroundColor: ocupada ? '#94a3b8' : '#10b981',
                        color: 'white', border: 'none', borderRadius: '5px',
                        cursor: ocupada || !archivoCsv ? 'not-allowed' : 'pointer',
                        fontWeight: 'bold'
                    }}
                >
                    {subiendoCsv ? 'Enviando archivo...' : importacionActiva ? 'Importación en curso...' : 'Procesar CSV en Segundo Plano'}
                </button>
            </form>
            {mensajeCsv && (
                <p role="status" aria-live="polite" style={{
                    marginTop: '15px',
                    marginBottom: '0',
                    fontWeight: '500',
                    color: ({ success: '#059669', warning: '#b45309', error: '#dc2626', progress: '#334155' })[tipoMensajeCsv] || '#334155'
                }}>
                {mensajeCsv}
            </p>
        )}
        {reintentarConsulta && (
            <button type="button" onClick={reintentarConsulta} style={{ marginTop: '12px', padding: '8px 12px' }}>
                Volver a consultar
            </button>
        )}
        </div>
    );
}
