# Definición del MVP

## Sistema Inteligente de Análisis de Sentimiento Organizacional

**PluriOne S.A. de C.V.** · Demostración end-to-end para examen de residencia profesional técnica  
**Versión:** 2.1 · **Fecha:** 8 de octubre de 2026

> Para este MVP, las decisiones aprobadas de autenticación y visualización prevalecen sobre los documentos originales.

## 1. Objetivo

Demostrar un flujo completo que autentique usuarios localmente, reciba comentarios, proteja PII, los analice con NLP/IA, persista resultados en PostgreSQL y muestre métricas y alertas en una interfaz React.js.

**Flujo:** login → comentario → sanitización → análisis → validación JSON → PostgreSQL → dashboard/ticket.

## 2. Core Features (incluidas)

- **Autenticación y RBAC:** usuarios locales, JWT emitidos/validados por el backend y permisos por rol.
- **Captura y privacidad:** formulario React responsivo, validación de texto y opción anónima sin vínculo recuperable con la identidad. Sanitización previa a servicios externos con Regex/spaCy para nombres, correos y teléfonos.
- **Pipeline NLP:** FastAPI y LangChain orquestan Azure AI Language y Azure OpenAI. El análisis devuelve polaridad (-1 a +1), etiqueta, emociones, ejes, frases clave y evaluación de riesgo. Pydantic valida estrictamente el JSON.
- **Persistencia:** PostgreSQL almacena comentarios, análisis, frases clave y alertas.
- **Gestión y analítica:** dashboard y bandeja de tickets renderizados nativamente en React.js; consulta y actualización de alertas según rol.
- **Privacidad de agregados:** las métricas se consultan por un único departamento (o comentarios sin departamento) y mes calendario completo; no se permiten filtros de cohortes solapadas. Las categorías con menos de cinco respuestas se ocultan; si un día del mes no alcanza cinco respuestas, se oculta la tendencia diaria completa.
- **Alertas:** cada comentario de riesgo crítico genera un ticket en PostgreSQL con estado inicial `OPEN`.

## 3. Out of Scope

- Microsoft Entra ID, OAuth/OIDC corporativo y sincronización de directorio: se difieren a una fase de producción.
- Power BI, sus licencias e incrustación: se difieren; la visualización del MVP es React nativo.
- Cambios o integraciones con nómina y otros sistemas core: fases posteriores.
- Redes sociales, apps móviles nativas y entrenamiento de modelos desde cero.
- Exportación de reportes y resúmenes ejecutivos IA.

## 4. Criterios de éxito (Definition of Done)

- Usuario inicia sesión con JWT local; endpoints y vistas aplican RBAC.
- Comentario se sanitiza antes de IA, se analiza, pasa validación Pydantic y queda guardado en PostgreSQL.
- Resultados aparecen en el dashboard React; un caso crítico crea ticket `OPEN` visible en la bandeja.
- API de lectura estándar: latencia **<300 ms**.
- Inferencia de IA: latencia **<3 s**.
- Clasificación de polaridad: **accuracy ≥85%**.
- Detección de banderas rojas: **recall ≥95%**.
- API documentada con OpenAPI/Swagger; sin errores 500 en el flujo de demostración ni secretos en el código.

Las métricas de IA se evalúan con el conjunto etiquetado de QA descrito en la documentación (200 comentarios), reportando su composición por clase.

## 5. Notas para cerrar antes de la demo

- Acordar catálogo de ejes: algunos documentos describen cinco y otros seis.
- Los umbrales implementados son: Negativo ≤ -0.25, Neutral entre -0.24 y +0.24, Positivo ≥ +0.25. Mantener esta regla alineada en todos los documentos y pruebas.
- Confirmar estados de tickets adicionales a `OPEN` y usuarios/roles locales de prueba.
- Definir retención del texto original y verificar que los comentarios anónimos no sean reidentificables.
- Medir por separado lectura API e inferencia IA.

## Fuentes

Diseño de arquitectura de Software; Especificación de Requisitos; Planificación Operativa; Propuesta Técnica y Operativa.
