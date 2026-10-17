# Product Requirements Document (PRD)

## Sistema Inteligente de Análisis de Sentimiento Organizacional

**Organización:** PluriOne S.A. de C.V. (Develop Talent & Technology)  
**Versión:** 1.0 - Borrador consolidado para validación  
**Fecha:** 8 de octubre de 2026  
**Estado:** Propuesta derivada de la documentación fuente; requiere validación de decisiones abiertas  
**Product owner de negocio propuesto:** Capital Humano  
**Responsable técnico documentado:** Julio Alfonso Monteverde Esquer  
**Asesor empresarial documentado:** C. Juan Méndez Herrera  
**Líder de proyecto documentado:** Ing. Edgar Loeffelmann (el apellido aparece con variantes tipográficas en las fuentes)

> Este PRD consolida y organiza la documentación disponible. Los puntos etiquetados como **Decisión pendiente** son discrepancias, vacíos o supuestos que requieren confirmación; no deben interpretarse como requisitos ya aprobados.

---

## 1. Resumen ejecutivo

PluriOne busca reducir el esfuerzo manual de lectura y clasificación de comentarios abiertos de clima organizacional y mejorar la oportunidad con la que Capital Humano identifica temas persistentes o incidentes de riesgo. La solución propuesta es una plataforma web que recibe retroalimentación interna, protege datos personales antes de su análisis en servicios cloud, genera análisis de sentimiento y temas mediante servicios NLP/IA, y presenta resultados agregados, alertas y una bandeja de seguimiento.

El producto integra una SPA responsiva en React, API asíncrona en FastAPI, persistencia relacional PostgreSQL, Azure AI Language y Azure OpenAI orquestados con LangChain, autenticación corporativa mediante Microsoft Entra ID y visualización ejecutiva con Power BI. El canal de respuesta incluye captura individual y, según las fuentes, importación histórica por lotes; las alertas de severidad alta deben producir un registro de incidente y notificación a Capital Humano.

El valor esperado es operativo y de decisión: convertir texto cualitativo en señales comparables por periodo y departamento, disminuir el tiempo de revisión manual, hacer visibles tendencias y facilitar la atención prioritaria. La IA debe apoyar el análisis y la priorización; las fuentes no definen que sus resultados determinen decisiones laborales individuales. Este PRD limita el uso a analítica organizacional y gestión humana de incidencias, y requiere confirmar las reglas de privacidad, acceso y conservación antes de producción.

### 1.1 Resultado de producto

Una persona colaboradora puede enviar una opinión identificada o anónima; Capital Humano puede revisar tendencias agregadas y atender alertas; las personas directivas pueden consultar indicadores consolidados; y TI puede gestionar accesos e integración sin exponer secretos.

### 1.2 Decisiones críticas pendientes

1. **Taxonomía:** elegir entre cinco y seis ejes organizacionales según documentos distintos.
2. **Calendario:** alinear los tres sprints con calendarios de QA incompatibles.
3. **Alcance del MVP:** confirmar importación CSV/XLSX/JSON, resúmenes ejecutivos exportables y corrección humana de clasificaciones.
4. **Anonimato real:** definir separación de identidad, metadatos permitidos, umbral de agregación, acceso a texto original y retención.
5. **Definición de IGS:** fijar fórmula, ponderación, tratamiento de respuestas y mínimo de muestra.
6. **Operación de alertas:** definir destinatarios, SLA, horario, escalamiento, estados y procedimiento para casos sensibles.
7. **Gobernanza de IA:** precisar dataset de evaluación, criterios por clase, cambios de prompts y aprobación productiva.

---

## 2. Contexto, oportunidad y objetivos

### 2.1 Problema

La documentación indica que PluriOne recopila opiniones mediante encuestas periódicas o buzones. Leer cientos de comentarios manualmente consume tiempo, introduce variabilidad entre analistas y puede retrasar la detección de insatisfacción, agotamiento o conflictos. El estado actual dificulta comparar señales entre departamentos y periodos de forma sistemática.

### 2.2 Objetivos

| ID | Objetivo | Indicador | Umbral documentado |
|---|---|---|---|
| OBJ-01 | Reducir trabajo manual de clasificación | Tiempo y esfuerzo de revisión por lote | Sin línea base; medir en piloto |
| OBJ-02 | Detectar tendencias de polaridad y temas | Exactitud en dataset etiquetado | Accuracy ≥85% con 200 comentarios |
| OBJ-03 | Priorizar riesgos para revisión humana | Recall de banderas rojas | ≥95% en conjunto de evaluación |
| OBJ-04 | Habilitar análisis oportuno | Latencia de análisis individual | <2.5 s en Propuesta; <3 s en SRS; resolver discrepancia |
| OBJ-05 | Proteger información personal | PII transferida a modelos externos | Meta propuesta: cero PII detectable tras sanitización; definir medición |
| OBJ-06 | Restringir acceso según función | Acceso correcto por rol | SSO corporativo y RBAC en cada recurso |
| OBJ-07 | Analizar clima por departamento | Métricas segmentadas | Respetando anonimato y muestra mínima por definir |

No se inventan umbrales que no aparecen en las fuentes. Establecer línea base del proceso actual y validar resultados en piloto.

### 2.3 Fuera de alcance

- Rastrear comentarios desde redes sociales públicas.
- Entrenar modelos LLM propietarios desde cero o instalar clústeres on-premise.
- Modificar nómina, asistencia u otros sistemas centrales.
- Desarrollar aplicaciones móviles nativas iOS/Android.
- Automatizar llamadas o integrar con conmutadores de voz.
- Tomar decisiones automatizadas de empleo, evaluación individual o sanción.

---

## 3. Usuarios y acceso

| Perfil | Necesidad | Capacidades previstas |
|---|---|---|
| Colaborador/a | Compartir experiencia de forma sencilla y confiable | Enviar comentario/encuesta; elegir anonimato si está habilitado; sin acceso a analítica global |
| Analista de Capital Humano | Detectar patrones y dar seguimiento | Consultar paneles autorizados, filtrar, revisar alertas, actualizar estado y generar reportes aprobados |
| Directivo/a | Comprender clima agregado | Lectura de KPIs consolidados, tendencias y resúmenes autorizados |
| Administrador/a | Mantener seguridad e integración | Gestionar roles/configuración, umbrales, endpoints, auditoría técnica y sincronización Entra ID |

### 3.1 Principios de autorización

- Microsoft Entra ID mediante OAuth 2.0 / OpenID Connect.
- El backend aplica RBAC; ocultar controles en frontend no es suficiente.
- Colaboradores no acceden a analítica global; directivos tienen vistas macro de solo lectura.
- El acceso al comentario original por RH debe ser explícito y auditable.
- Administración técnica no obtiene automáticamente acceso al contenido de comentarios.
- No se crean cuentas manuales en producción. Los JWT locales simulados descritos en planificación son solo para desarrollo.

**Pendiente:** mapear grupos/roles reales de Entra ID y definir autorización por departamento, dato y operación.

---

## 4. Requisitos funcionales

Prioridad **Alta** indica flujo principal/MVP en fuentes; **Media** indica capacidad mencionada no indispensable para el flujo mínimo. Validar durante refinamiento.

### 4.1 Identidad y control de acceso

| ID | Requisito | Prioridad | Criterios de aceptación |
|---|---|---|---|
| RF-01 | Inicio de sesión corporativo | Alta | Usuario autorizado inicia por Entra ID; no hay credenciales locales; fallo de autenticación no concede acceso. |
| RF-02 | Autorización por rol | Alta | API valida rol en cada ruta; acceso no autorizado es denegado; vistas respetan la matriz aprobada. |
| RF-03 | Sesión y tokens | Alta | Solicitudes requieren token válido; expiración máxima de 8 horas; expiración conduce a renovación segura o cierre. |
| RF-04 | Auditoría administrativa | Media | Cambios de roles/configuración registran actor, fecha, acción y resultado sin secretos. |

La arquitectura menciona JWT simétrico y validación de JWT con Entra. Definir proveedor emisor, issuer/audience, claves, rotación y renovación; no asumir que el backend emite tokens corporativos.

### 4.2 Captura e importación

| ID | Requisito | Prioridad | Criterios de aceptación |
|---|---|---|---|
| RF-05 | Captura individual responsiva | Alta | Formulario usable en escritorio, tableta y móvil; vacíos o texto sin contenido lingüístico se rechazan con explicación; envío exitoso confirma recepción. |
| RF-06 | Categorías de captura | Alta | Catálogo mostrado, si aplica, está administrado y alineado con ejes aprobados. |
| RF-07 | Envío anónimo | Alta | No persiste vínculo recuperable identidad-comentario; usa UUID aleatorio; identidad no llega a IA ni a vistas RH; interfaz explica alcance del anonimato. |
| RF-08 | Importación por lote | Media | Roles autorizados cargan CSV; validación de esquema; reporte de aceptados/rechazados; hasta 1,000 filas en ≤5 min bajo entorno acordado. |
| RF-09 | Formatos de importación | Media | CSV está respaldado por rendimiento; SRS también menciona XLSX/JSON. Aceptar formatos adicionales tras aprobar contrato. |
| RF-10 | Validación y sanitización | Alta | Rechaza archivos/filas inválidos; neutraliza entradas peligrosas; limpia PII antes de modelos externos; texto original se retiene solo conforme a política aprobada. |
| RF-11 | Duplicados de lote | Media | Comportamiento de reimportación/deduplicación está definido y evita doble conteo. |

Flujo de lote recomendado: carga → validación previa → resumen → confirmación → procesamiento asíncrono → estado y errores por fila.

### 4.3 NLP e IA

| ID | Requisito | Prioridad | Criterios de aceptación |
|---|---|---|---|
| RF-12 | Puntaje/etiqueta de polaridad | Alta | Puntaje en [-1,+1] y etiqueta Positivo/Neutro/Negativo según umbrales aprobados; guarda versión de análisis y fecha. |
| RF-13 | Emociones | Media | Retorna etiquetas del catálogo aprobado o ninguna si no hay evidencia suficiente; no fuerza clasificación. |
| RF-14 | Ejes organizacionales | Alta | Asigna uno o más ejes aprobados o “Sin clasificar”; no inventa etiquetas fuera del esquema. |
| RF-15 | Frases clave | Alta | Extrae frases para agregación, normaliza duplicados y excluye PII visible. |
| RF-16 | Orquestación en cascada | Alta | Azure AI Language calcula polaridad inicial; Azure OpenAI realiza análisis cualitativo; LangChain maneja prompts/reintentos; fallback y fallos quedan trazados. |
| RF-17 | Salida estructurada | Alta | Pydantic valida respuesta; salida inválida se reintenta limitadamente o queda como fallo recuperable; no se trata salida cruda como confiable. |
| RF-18 | Confianza/abstención | Media | Scores de confianza tienen definición; baja confianza queda señalada y no se muestra como certeza. |
| RF-19 | Reprocesamiento | Media | Conserva versiones previas, registra motivo/actor y evita duplicar entrada o alerta. |

#### 4.3.1 Polaridad y emociones

La Propuesta establece Positivo +0.25 a +1.00, Neutro -0.25 a +0.25 y Negativo -1.00 a -0.25. Los límites se solapan en ±0.25. Recomendación: Positivo >+0.25, Neutro entre -0.25 y +0.25 inclusive, Negativo <-0.25; confirmar con negocio.

Emociones listadas: Entusiasmo/Motivación, Satisfacción/Conformidad, Agradecimiento, Inconformidad/Molestia, Frustración/Impotencia y Estrés/Burnout. Validar catálogo y ejemplos lingüísticos en español corporativo.

#### 4.3.2 Ejes organizacionales en conflicto

- Propuesta y Planificación: cinco ejes: Liderazgo y management; Carga y ritmo de trabajo; Ambiente y clima laboral; Compensaciones y beneficios; Herramientas e instalaciones.
- Arquitectura y SRS hacen referencia a seis ejes e incluyen “Desarrollo y Crecimiento Profesional”.

No cerrar prompts, dashboards ni esquema hasta aprobar un catálogo único versionado.

#### 4.3.3 Índice Global de Satisfacción (IGS)

La Propuesta describe polaridad continua y promedio ponderado por empresa/departamento, pero no define fórmula. Antes de exponerlo, acordar ponderación, periodo, respuestas múltiples, neutralidad, denominador y muestra mínima. Explicar metodología en el panel.

### 4.4 Riesgos y alertas

| ID | Requisito | Prioridad | Criterios de aceptación |
|---|---|---|---|
| RF-20 | Evaluación de riesgo | Alta | Asigna Baja/Media/Alta y razón; riesgo alto crea alerta; registra modelo/regla usada. |
| RF-21 | Categorías de riesgo | Alta | Alta: acoso, discriminación, conducta antiética, intención inminente de renuncia o burnout. Media: insatisfacción persistente por salario/carga sin señal crítica. Baja: neutral/positivo/sugerencia. RH valida definiciones. |
| RF-22 | Notificación | Alta | Riesgo alto genera correo y banner; se registra hora/estado/error; se reintenta y escala según política. |
| RF-23 | Ticket automático | Alta | Crea ticket único OPEN vinculado al análisis y severidad; reintento no duplica. |
| RF-24 | Bandeja RH | Media | Permite filtrar por severidad, fecha, departamento y estado conforme a permisos. |
| RF-25 | Gestión de estado | Media | Actor y hora de cambio se registran. Alinear estados DB/API/UI: OPEN, IN_PROGRESS, CLOSED y etiquetas Pendiente, En revisión, Atendida. Definir “Falsa alarma”. |
| RF-26 | Escalamiento/SLA | Pendiente | Definir responsable, plazo de revisión y procedimiento para riesgo crítico. |
| RF-27 | Revisión humana | Media | Analista puede marcar resultado correcto/incorrecto/insuficiente; correcciones alimentan evaluación controlada, no ajuste automático sin revisión. |

Una bandera roja es una señal para revisión humana, no una conclusión factual sobre una persona o equipo. Evitar lenguaje acusatorio y presentar incertidumbre cuando exista.

### 4.5 Analítica, paneles y reportes

| ID | Requisito | Prioridad | Criterios de aceptación |
|---|---|---|---|
| RF-28 | Panel de sentimiento | Alta | Distribución de polaridad, evolución temporal, volumen y temas; filtros aplicados visibles. |
| RF-29 | Segmentación | Alta | Filtra por departamento/periodo respetando permisos y muestra mínima. |
| RF-30 | Power BI | Alta | Embed autenticado; token gestionado seguramente; acceso respeta rol y no expone datos no autorizados. |
| RF-31 | Exportación | Media | PDF/Excel está en SRS; restringida a datos autorizados y agregados. |
| RF-32 | Resumen IA | Media | Usuario autorizado elige periodo; resumen usa solo datos filtrados, refiere métricas agregadas y señala limitaciones; formato PDF/texto por decidir. |
| RF-33 | Integridad de agregados | Alta | Conteos/promedios concuerdan con registros elegibles; filtros/exclusiones documentados. |

KPIs candidatos: volumen de comentarios, distribución/tendencia de polaridad, IGS, volumen por eje, alertas por severidad y tiempo de atención. Definir denominadores para tasas.

### 4.6 Administración y operación

- Administrar catálogos, departamentos y umbrales con permisos explícitos.
- Guardar conexiones y credenciales en gestor de secretos; nunca mostrar valores en UI/logs.
- Exponer estado operativo de IA, API, base, correo y lotes.
- Registrar errores y trazas correlacionadas sin texto sensible.
- Permitir auditoría de cambios y accesos sensibles.

---

## 5. Requisitos no funcionales

| ID | Categoría | Requisito | Medición/aceptación |
|---|---|---|---|
| RNF-01 | Rendimiento | Lecturas API <300 ms | Acordar percentil/entorno; sugerencia p95 sin proveedor externo |
| RNF-02 | Rendimiento | Análisis IA <3 s; Propuesta indica <2.5 s | Resolver un solo SLA; aclarar percentil, timeout y dependencias incluidas |
| RNF-03 | Concurrencia | ≥50 usuarios concurrentes | Definir mezcla de operaciones y degradación aceptable |
| RNF-04 | Lotes | 1,000 comentarios CSV ≤5 min | Asíncrono; definir longitud promedio y error tolerable |
| RNF-05 | Seguridad | Cifrado tránsito/reposo | TLS 1.3 en tránsito; cifrar base y respaldos |
| RNF-06 | Privacidad | Sanitizar PII antes de nube | Pruebas de nombres, emails y teléfonos; medir falsos negativos |
| RNF-07 | Secretos | No incluir secretos en código | Variables/Key Vault y revisión del repo/pipeline |
| RNF-08 | Disponibilidad | Tolerancia a fallos | No hay SLA cuantitativo; definir disponibilidad, recuperación y mantenimiento |
| RNF-09 | Integridad | PostgreSQL ACID | Integridad referencial y consistencia entrada/análisis/ticket |
| RNF-10 | Compatibilidad | SPA responsiva | 1920x1080, 1366x768 y tablet/móvil; definir navegadores soportados |
| RNF-11 | Accesibilidad | UI clara y utilizable | Validar teclado, contraste, etiquetas y mensajes; estándar por definir |
| RNF-12 | Observabilidad | Correlación de flujos | Métricas/logs sin PII; definir retención |
| RNF-13 | Recuperación | Respaldos/restauración | RPO/RTO no documentados; acordar antes de producción |
| RNF-14 | Mantenibilidad | Capas desacopladas/API versionada | Migraciones y despliegue reproducibles |

### 5.1 Privacidad y seguridad por diseño

1. Minimizar datos recopilados y conservados.
2. Sanitizar PII localmente antes de servicios cloud; considerar falsos positivos/negativos.
3. En anonimato, no guardar una llave que permita reconstruir vínculo con identidad.
4. Aplicar menor privilegio y auditar acceso a contenido.
5. Cifrar comunicaciones, base y respaldos.
6. Definir retención/borrado para texto, resultados, auditoría y archivos.
7. Suprimir segmentos de bajo volumen para mitigar reidentificación.
   En el MVP, las analíticas sólo permiten consultar celdas disjuntas de departamento y mes calendario; se suprimen complementariamente las tendencias diarias cuando algún día tiene menos de cinco respuestas. No se permiten rangos arbitrarios solapados.
8. No inferir diagnósticos clínicos ni tratar intención estimada como hecho; mantener revisión humana.
9. Validar región, retención y tratamiento de datos de los servicios Azure antes de producción.

**Pendiente de cumplimiento:** las fuentes no fijan base de tratamiento, avisos, retención ni derechos de acceso/borrado; validarlo con responsables corporativos.

---

## 6. Flujos de usuario

### 6.1 Envío de retroalimentación

1. Colaborador accede con identidad corporativa o mecanismo aprobado.
2. Consulta explicación breve de uso y privacidad.
3. Escribe comentario y selecciona modalidad anónima/identificada cuando aplique.
4. UI valida y confirma recepción sin revelar análisis sensible.
5. Backend asigna UUID, persiste según política, sanitiza PII y analiza.
6. Resultado validado se almacena; riesgo alto crea ticket/notificación.
7. Agregados aparecen según permisos y reglas de muestra.

**Pendiente:** SSO obligatorio y anonimato aparecen juntos en las fuentes. Definir si anonimato significa que el contenido no se asocia a la identidad (recomendado), aunque la autenticación evite abuso; evaluar canal sin login si se requiere.

### 6.2 Atención de alerta

1. Evaluador asigna severidad, razón y versión de regla/modelo.
2. Riesgo alto crea ticket OPEN y notifica a RH.
3. Analista revisa con acceso autorizado y actualiza estado/motivo.
4. Sistema registra tiempos y cambios.
5. Panel agrega tendencias sin exponer comentarios identificables a roles no autorizados.

### 6.3 Consulta ejecutiva

Directivo abre panel autenticado, filtra periodo/departamento permitido, revisa KPI con metodología y volumen visible, y solicita resumen agregado si se confirma esa funcionalidad.

---

## 7. Arquitectura y modelo de datos

### 7.1 Componentes

| Capa | Stack documentado | Responsabilidad |
|---|---|---|
| Presentación | React, HTML5/CSS3, Power BI | Formularios, SPA, tickets y paneles |
| Negocio/API | Python 3.11, FastAPI, Pydantic, Uvicorn, SQLAlchemy | Validación, autorización, sanitización, lógica y REST |
| IA | LangChain, Azure AI Language, Azure OpenAI | Polaridad, análisis cualitativo, extracción y reintentos |
| Persistencia | PostgreSQL 15+ | Datos, JSONB, transacciones, roles y logs |
| DevOps | Docker, Docker Compose, GitHub Actions | Contenedores y CI/CD |

### 7.2 Entidades documentadas

- `users`: UUID, email, rol, estado, creación y departamento (este último aparece en SRS).
- `departments`: identificador, nombre, población/empleados totales.
- `feedback_entries`: UUID, texto, anonimato, fecha y departamento; usuario opcional según política.
- `sentiment_analysis`: UUID, entrada, polaridad, etiqueta, metadata JSONB y bandera.
- `key_phrases`: frase, análisis y ocurrencia.
- `alerts`: UUID, análisis, severidad, estado, responsable, resolución y fechas.

### 7.3 Discrepancias/vacíos del esquema

- Arquitectura omite `user_id` de `feedback_entries`, SRS lo incluye como FK; resolver para soportar anonimato.
- Definir cardinalidad entrada-análisis y guardar versión de modelo, prompt, catálogo y regla.
- Alinear estados OPEN/IN_PROGRESS/CLOSED con “Falsa alarma”.
- Agregar entidad de lote/errores por fila si importación entra en MVP.
- Determinar retención del texto original y permisos para verlo.
- Acordar fuente de `total_employees` antes de usarlo en ponderación.
- Normalizar timestamps a UTC.
- Evitar PII en frases clave o razones generadas.

### 7.4 API principal

La arquitectura propone `POST /api/v1/nlp/analyze-feedback`, bearer token, texto, indicador anónimo y departamento. Corregir errata `deparment_id`/`department_id`; definir códigos de error, límites de texto, idempotencia, timeout y respuesta asíncrona para lotes.

Respuesta lógica: identificador, fecha, texto limpio sujeto a política, sentimiento, emociones, ejes, frases clave y riesgo. Versionar y validar salida; no incluir PII innecesaria.

---

## 8. Calidad de IA y observabilidad

### 8.1 Evaluación de IA

- Polaridad: accuracy ≥85% en dataset de 200 comentarios etiquetados (Propuesta).
- Banderas rojas: recall ≥95%; confirmar si aplica al mismo dataset o a conjunto específico.
- Reportar precision además de recall para entender falsas alarmas; desglosar por etiqueta/eje cuando la muestra lo permita.
- Evaluar sanitización con casos representativos y revisión manual.
- Human-in-the-loop aparece como objetivo, pero no como historia detallada; aprobar alcance y permisos.

Un conjunto de 200 puede ser insuficiente para estimar clases raras como acoso/burnout. Informar tamaño por clase y evitar conclusiones basadas solo en accuracy global.

### 8.2 Métricas operativas

Latencia API p50/p95/p99; éxito/fallo/reintentos/cuota Azure; volumen y tiempo de cola/lote; salidas inválidas/abstenciones; alertas por severidad; entrega de correo; tiempo a primera revisión/cierre; errores de autorización/importación/persistencia; salud de base y respaldos.

---

## 9. Plan de entrega

### 9.1 Scrum y backlog fuente

Sprints de dos semanas, planning al inicio, daily por texto y review al cierre. Backlog documentado:

| HU | Contenido | Puntos |
|---|---|---:|
| HU-01 | Entra ID, JWT y rutas protegidas | 5 |
| HU-02 | FastAPI/PostgreSQL, migraciones, tablas | 3 |
| HU-03 | Sanitización PII | 5 |
| HU-04 | Formulario responsivo/anónimo | 3 |
| HU-05 | LangChain, Azure, polaridad/emociones/ejes | 8 |
| HU-06 | Resúmenes ejecutivos | 5 |
| HU-07 | Banderas rojas/ticket OPEN | 5 |
| HU-08 | Bandeja y actualización de incidencias | 3 |
| HU-09 | Power BI y KPIs | 5 |

Las historias suman 42 puntos, igual que las cargas de Sprint 1 (8), Sprint 2 (21) y Sprint 3 (13). Sin embargo, la asignación narrativa no ubica claramente todas las historias (p.ej., HU-06/HU-09). Revisar capacidad y dependencias.

### 9.2 Calendario en conflicto

SRS: QA 16-27 nov; documentación 30 nov-8 dic; DevOps 9-15 dic; capacitación 16-22 dic; cierre 22-24 dic. Propuesta: QA 23 nov-4 dic y cierre 7-24 dic. Tres sprints del plan terminan 20 nov. Aprobar una línea base integrada con revisores y buffer; este PRD no selecciona calendario autoritativo.

### 9.3 Definition of Done documentada

1. Código integrado a GitHub sin conflictos.
2. Pipeline CI/CD y Docker Compose validados.
3. Endpoints documentados en Swagger/OpenAPI (la fuente dice “Swagger/OpenAI”; interpretar como errata pendiente).
4. Aprobación visual/funcional, sin errores de consola ni excepciones 500 en flujo aceptado.
5. Sin secretos/credenciales en código.

Extensión recomendada para release: criterios aceptados, migración/rollback documentados, privacidad/retención definidas, telemetría sin PII y revisión de seguridad.

---

## 10. Riesgos y dependencias

| Riesgo/dependencia | Impacto | Mitigación |
|---|---|---|
| Latencia/cuotas/indisponibilidad Azure OpenAI | Alto | Asíncronía, rate limit, timeout, reintentos acotados, cola y fallback de polaridad; mostrar fallo/resultado parcial |
| Alucinación o respuesta fuera de esquema | Alto | Prompt restringido, esquema Pydantic, catálogo cerrado, pruebas y abstención |
| Fuga de PII | Crítico | Sanitización previa, pruebas adversariales y control de logs; no confiar solo en Regex |
| Retraso de credenciales Entra | Medio | Gestionar aprobación temprano; mock solo en desarrollo |
| Falsos positivos de riesgo | Alto | Medir precision, revisión RH y tuning versionado |
| Reidentificación en grupos pequeños | Alto | Muestra mínima, supresión y control de filtros |
| Taxonomía ambigua | Medio | Taller de negocio y catálogo versionado con ejemplos |
| Power BI con permisos excesivos | Alto | RLS/Entra, token backend y pruebas negativas |
| Desfase de esquema | Medio | Resolver anonimato/FK/estados antes de migraciones |
| QA en fechas incompatibles | Medio | Aprobar calendario y gate de QA |
| Falta de validadores | Medio | Reservar capacidad de RH para etiquetado, revisión y aceptación |

Dependencias: tenant y app Entra; suscripciones, modelos, región y cuotas Azure; correo; licencia/workspace/embed Power BI; PostgreSQL/secretos; dataset etiquetado y catálogo oficial de departamentos.

---

## 11. Criterios de lanzamiento

- Catálogos de ejes/emociones, umbrales de polaridad e IGS aprobados.
- Auth/RBAC probado con Entra real, incluidas denegaciones.
- Anonimato demostrado técnicamente; umbral de agregación aplicado.
- Sanitización validada antes de llamadas externas; secretos fuera de código/logs.
- API/lotes/alertas cumplen SLO acordados bajo carga representativa.
- IA evaluada por clase y errores revisados; falsas alarmas/abstenciones aceptadas por RH.
- Destinatarios, horario, atención y contingencia de alertas aprobados.
- Power BI aplica permisos previstos.
- Backups/restauración, retención, borrado, logging e incidentes documentados.
- QA, capacitación, manuales y acta de liberación con responsables/fechas confirmados.

---

## 12. Registro de decisiones pendientes

| Decisión | Recomendación | Responsable sugerido |
|---|---|---|
| Cinco vs. seis ejes | Incorporar “Desarrollo y Crecimiento Profesional” solo si negocio lo valida; versionar catálogo y ejemplos. | RH + líder |
| Límites ±0.25 | Intervalos no solapados con inclusividad explícita. | RH + NLP |
| Anonimato con SSO | Autenticar para acceso y eliminar vínculo identidad-comentario al guardar; declarar metadatos conservados. | TI/Seguridad + RH |
| Texto original | Minimizar retención; acceso limitado y plazo explícito. | Privacidad + RH |
| SLA de riesgo alto | Fijar horario, buzón, responsable y escalamiento. | RH |
| Falsa alarma | Estado final CLOSED y resolución FALSE_POSITIVE/motivo separado. | RH + ingeniería |
| Formatos de lote | MVP CSV; ampliar tras acordar esquemas. | Product Owner |
| Resumen/HITL/exportación | Confirmar primera release y capacidad/calendario. | Patrocinador + RH |
| IGS | Fórmula, denominador y muestra mínima antes de publicar. | Dirección + RH |
| QA | Aprobar calendario integrado. | Líder de proyecto |
| Dataset IA | Desglosar clases y ampliar si casos críticos son escasos. | RH + NLP |
| JWT/Entra | Documentar claims, issuer/audience, renovación y rotación. | TI/Seguridad |

---

## 13. Trazabilidad a fuentes

| Tema | Fuentes |
|---|---|
| Propósito, alcance y exclusiones | SRS §§1.2-1.2.2; Propuesta §2.1 |
| Perfiles y roles | SRS §§1.3, 2.2 |
| Requisitos funcionales | SRS §3; Propuesta §§3-5; Plan Operativo backlog HU-01 a HU-09 |
| Arquitectura, pipeline, datos y API | Diseño de Arquitectura: capas, pipeline, esquema y contratos; SRS §§2.3, 5-6 |
| Dimensiones/IGS | Propuesta §3.2; Diseño de Arquitectura; SRS RF-08 a RF-10 |
| Alertas | Propuesta §4; Arquitectura pipeline/esquema alerts; SRS RF-12 a RF-14 |
| RNF y calidad IA | SRS §§4.1-4.2; Propuesta §7.1 |
| Scrum, DoD, calendario y riesgos | Plan Operativo §§2-4; SRS §7; Propuesta §6 |

## 14. Fuentes documentales

1. **Diseño de arquitectura de Software.pdf** - Arquitectura, pipeline, datos, API y seguridad.
2. **Especificacion de Requisitos.pdf** - Alcance, roles, RF/RNF, interfaces, datos y fases.
3. **Planificacion Operativa.pdf** - Scrum, DoD, backlog, sprints y riesgos.
4. **Propuesta Técnica y Operativa..pdf** - Problema, alcance negociado, analítica, severidades y métricas.

---

## Apéndice A. Contrato lógico ilustrativo

```json
{
  "entry_id": "uuid",
  "analyzed_at": "ISO-8601 UTC",
  "analysis_version": "string",
  "sentiment_summary": {
    "label": "POSITIVE | NEUTRAL | NEGATIVE",
    "polarity_score": 0.0,
    "confidence_scores": {
      "positive": 0.0,
      "neutral": 0.0,
      "negative": 0.0
    }
  },
  "emotions_detected": [],
  "organizational_axes": [],
  "key_phrases": [],
  "risk_assessment": {
    "red_flag": false,
    "risk_level": "LOW | MEDIUM | HIGH",
    "reason_code": "string",
    "reason_summary": "string",
    "human_review_required": false
  }
}
```

Es una organización de los campos mostrados en las fuentes, no contrato aprobado. El esquema productivo debe decidir inclusión de texto limpio, protección de datos y respuesta síncrona/asíncrona.

## Apéndice B. Glosario

- **IGS:** Índice Global de Satisfacción; fórmula pendiente.
- **PII:** Información de identificación personal.
- **NLP:** Procesamiento de Lenguaje Natural.
- **RBAC:** Control de acceso basado en roles.
- **SRS:** Especificación de Requisitos de Software.
- **SSO:** Inicio de sesión único.
- **HITL:** Revisión humana dentro del flujo de IA.
- **DoD:** Definition of Done / definición de terminado.
