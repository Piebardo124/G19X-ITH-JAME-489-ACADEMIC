import React, { useState, useEffect } from 'react';

const ExecutiveSummary = ({ token }) => {
    const [summaryData, setSummaryData] = useState(null);
    const [lorading, setLoadinng] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/v1/nlp/summary', {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
        
                if(!response.ok) throw new Error('Error al obtener el resumen ejecutivo');
        
                const data = await response.json();
                setSummaryData(data);
                } catch (err) {
                    setError(err.message);
                } finally {
                    setLoadinng(false);
                }
            };
            
            fetchSummary();
    }, [tokens]);

    if (loading) return <div className="p-4 text-gray-600">Generando resumen con IA...</div>;
  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;

  return (
    <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-600 mb-6">
      <h3 className="text-xl font-bold text-gray-800 mb-2">Resumen Ejecutivo de Clima Laboral</h3>
      <p className="text-sm text-gray-500 mb-4">
        Comentarios analizados: <span className="font-semibold">{summaryData?.total_analyzed}</span>
      </p>
      <p className="text-gray-700 leading-relaxed italic">
        "{summaryData?.executive_summary}"
      </p>
    </div>
  );
};

export default ExecutiveSummary;