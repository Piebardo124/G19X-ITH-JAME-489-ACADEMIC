function ListaMetricas({ titulo, elementos = [] }) {
    const maximo = Math.max(...elementos.map((elemento) => elemento.count || elemento.total_responses || 0), 1);
    return (
        <section style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px' }}>
        <h4 style={{ margin: '0 0 12px', color: '#334155' }}>{titulo}</h4>
        {elementos.length === 0 ? (
            <p style={{ margin: 0, color: '#64748b' }}>Sin datos suficientes.</p>
        ) : elementos.map((elemento) => {
            const cantidad = elemento.count || elemento.total_responses || 0;
            return (
            <div key={elemento.name || elemento.department_id || elemento.date} style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', fontSize: '14px' }}>
                <span>{elemento.name || elemento.department || elemento.date}</span>
                <strong>{elemento.average_polarity != null ? `${elemento.average_polarity > 0 ? '+' : ''}${elemento.average_polarity}` : cantidad}</strong>
                </div>
                <div aria-hidden="true" style={{ height: '7px', marginTop: '4px', backgroundColor: '#e2e8f0', borderRadius: '5px' }}>
                <div style={{ height: '100%', width: `${Math.max((cantidad / maximo) * 100, 3)}%`, backgroundColor: '#3b82f6', borderRadius: '5px' }} />
                </div>
            </div>
            );
        })}
        </section>
    );
}

export default function MetricasSentimiento({ analiticas, errorAnaliticas, departamentos, departamentoFiltro, setDepartamentoFiltro, periodoFiltro, setPeriodoFiltro }) {
    return (
        <section style={{ backgroundColor: '#f8fafc', border: '1px solid #cbd5e1', padding: '20px', borderRadius: '8px', marginBottom: '25px' }}>
        <h3 style={{ marginTop: 0, color: '#1e293b' }}>Métricas de sentimiento</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '18px' }}>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
            Departamento
            <select value={departamentoFiltro} onChange={(e) => setDepartamentoFiltro(e.target.value)} style={{ padding: '8px', border: '1px solid #cbd5e1', borderRadius: '5px' }}>
                <option value="" disabled>Selecciona un departamento</option>
                <option value="0">Sin departamento</option>
                {departamentos.map((departamento) => <option key={departamento.id} value={departamento.id}>{departamento.name}</option>)}
            </select>
            </label>
            <label style={{ display: 'grid', gap: '4px', color: '#334155', fontSize: '14px' }}>
            Mes calendario
            <input type="month" value={periodoFiltro} onChange={(e) => setPeriodoFiltro(e.target.value)} style={{ padding: '7px', border: '1px solid #cbd5e1', borderRadius: '5px' }} />
            </label>
        </div>

        {errorAnaliticas ? (
            <p style={{ color: '#b45309', margin: 0, fontWeight: 'bold' }}>{errorAnaliticas}</p>
        ) : analiticas ? (
            analiticas.status === 'insufficient_data' ? (
            <p style={{ color: '#92400e', backgroundColor: '#fef3c7', padding: '12px', borderRadius: '6px' }}>
                Se requieren al menos 5 comentarios analizados en este departamento y mes para mostrar agregados.
            </p>
            ) : (
            <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px', justifyContent: 'space-around', marginBottom: '18px' }}>
                <div style={{ textAlign: 'center' }}>
                    <h4 style={{ margin: '0 0 8px', color: '#334155' }}>Respuestas analizadas</h4>
                    <p style={{ fontSize: '24px', fontWeight: 'bold', margin: 0, color: '#2563eb' }}>{analiticas.total_responses}</p>
                </div>
                <div style={{ textAlign: 'center' }}>
                    <h4 style={{ margin: '0 0 8px', color: '#334155' }}>Polaridad promedio</h4>
                    <p style={{ fontSize: '24px', fontWeight: 'bold', margin: 0, color: analiticas.average_polarity >= 0.25 ? '#059669' : analiticas.average_polarity <= -0.25 ? '#dc2626' : '#d97706' }}>
                    {analiticas.average_polarity > 0 ? '+' : ''}{analiticas.average_polarity}
                    </p>
                </div>
                <div style={{ textAlign: 'center' }}>
                    <h4 style={{ margin: '0 0 8px', color: '#334155' }}>Distribución</h4>
                    {analiticas.distribution_suppressed ? (
                    <p style={{ color: '#92400e', fontSize: '13px', fontWeight: 'normal', margin: 0 }}>
                        Distribución oculta por privacidad: al menos una categoría tiene menos de 5 respuestas.
                    </p>
                    ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', fontSize: '14px', fontWeight: 'bold' }}>
                        <span style={{ color: '#059669' }}>Positivo: {analiticas.distribution?.Positivo || 0}</span>
                        <span style={{ color: '#d97706' }}>Neutral: {analiticas.distribution?.Neutral || 0}</span>
                        <span style={{ color: '#dc2626' }}>Negativo: {analiticas.distribution?.Negativo || 0}</span>
                    </div>
                    )}
                </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                <ListaMetricas titulo="Emociones frecuentes" elementos={analiticas.emotions} />
                <ListaMetricas titulo="Ejes organizacionales" elementos={analiticas.organizational_axes} />
                <ListaMetricas titulo="Frases clave frecuentes" elementos={analiticas.key_phrases} />
                <ListaMetricas titulo="Polaridad del departamento seleccionado" elementos={analiticas.department_averages} />
                <ListaMetricas titulo={analiticas.daily_trend_suppressed ? 'Tendencia diaria (oculta por privacidad)' : 'Tendencia diaria'} elementos={analiticas.daily_trend} />
                </div>
            </>
            )
        ) : (
            <p style={{ margin: 0, color: '#64748b' }}>Cargando métricas...</p>
        )}
        </section>
    );
}