const ESTADOS_ALERTA = {
    OPEN: { label: 'Pendiente', background: '#fee2e2', color: '#b91c1c' },
    IN_PROGRESS: { label: 'En revisión', background: '#fef3c7', color: '#92400e' },
    CLOSED: { label: 'Atendida', background: '#d1fae5', color: '#059669' },
    FALSE_POSITIVE: { label: 'Falsa alarma', background: '#e0e7ff', color: '#3730a3' },
};

export default function BandejaAlertas({ alertas, filtrosAlertas, setFiltrosAlertas, actualizarEstadoAlerta, departamentos, cargando, error, pagina, hayMas, cambiarPagina }) {
    return (
        <>
        <section style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', padding: '20px', borderRadius: '8px', marginBottom: '25px' }}>
            <h3 style={{ marginTop: 0, color: '#1e293b' }}>Bandeja de alertas</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
                Estado
                <select value={filtrosAlertas.status_filter} onChange={(event) => setFiltrosAlertas((actuales) => ({ ...actuales, status_filter: event.target.value }))} style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }}>
                <option value="">Todos</option>
                <option value="OPEN">Pendiente</option>
                <option value="IN_PROGRESS">En revisión</option>
                <option value="CLOSED">Atendida</option>
                <option value="FALSE_POSITIVE">Falsa alarma</option>
                </select>
            </label>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
                Riesgo
                <select value={filtrosAlertas.risk_level} onChange={(event) => setFiltrosAlertas((actuales) => ({ ...actuales, risk_level: event.target.value }))} style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }}>
                <option value="">Todos</option>
                <option value="ALTO">Alto</option>
                </select>
            </label>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
                Departamento
                <select value={filtrosAlertas.department_id} onChange={(event) => setFiltrosAlertas((actuales) => ({ ...actuales, department_id: event.target.value }))} style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }}>
                <option value="">Todos</option>
                <option value="0">Sin departamento</option>
                {departamentos.map((departamento) => <option key={departamento.id} value={departamento.id}>{departamento.name}</option>)}
                </select>
            </label>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
                Desde
                <input type="date" value={filtrosAlertas.date_from} onChange={(event) => setFiltrosAlertas((actuales) => ({ ...actuales, date_from: event.target.value }))} style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }} />
            </label>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
                Hasta
                <input type="date" value={filtrosAlertas.date_to} onChange={(event) => setFiltrosAlertas((actuales) => ({ ...actuales, date_to: event.target.value }))} style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }} />
            </label>
            </div>
        </section>

        {cargando ? (
            <p>Cargando información...</p>
        ) : error ? (
            <p style={{ color: 'red' }}>{error}</p>
        ) : (
            <div style={{ overflowX: 'auto', marginTop: '20px', marginBottom: '25px' }}>
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
                            backgroundColor: (ESTADOS_ALERTA[alerta.status] || ESTADOS_ALERTA.OPEN).background,
                            color: (ESTADOS_ALERTA[alerta.status] || ESTADOS_ALERTA.OPEN).color
                        }}>
                            {(ESTADOS_ALERTA[alerta.status] || ESTADOS_ALERTA.OPEN).label}
                        </span>
                        </td>
                        <td style={{ padding: '12px', textAlign: 'center' }}>
                        <select
                            aria-label={`Estado de alerta ${alerta.id}`}
                            value={alerta.status}
                            onChange={(event) => actualizarEstadoAlerta(alerta.id, event.target.value)}
                            style={{ padding: '6px', border: '1px solid #cbd5e1', borderRadius: '5px' }}
                        >
                            <option value="OPEN">Pendiente</option>
                            <option value="IN_PROGRESS">En revisión</option>
                            <option value="CLOSED">Atendida</option>
                            <option value="FALSE_POSITIVE">Falsa alarma</option>
                        </select>
                        </td>
                    </tr>
                    ))
                )}
                </tbody>
            </table>
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', padding: '12px' }}>
                <button type="button" disabled={pagina <= 1 || cargando} onClick={() => cambiarPagina((actual) => actual - 1)}>
                    Anterior
                </button>
                <span>Página {pagina}</span>
                <button type="button" disabled={!hayMas || cargando} onClick={() => cambiarPagina((actual) => actual + 1)}>
                    Siguiente
                </button>
            </div>
            </div>
        )}
        </>
    );
}
