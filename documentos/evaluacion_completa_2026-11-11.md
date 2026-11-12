# Evaluación funcional, de seguridad y arquitectura — 11 de noviembre de 2026

Commit: `a9b1cd52a986ba4bd57a3601098fd15e29dac262`. Evaluación realizada por Codex a solicitud del autor, con Docker autorizado. Se revisaron backend, CLI, sanitización, motor, persistencia, frontend, Docker/Compose y dependencias npm. No se modificó código de la aplicación para aprobar las pruebas.

## Evidencias y resultado general

- **55 pruebas unitarias correctas y 76 comprobaciones integradas correctas**, con PostgreSQL real y ocho análisis sintéticos reales en integración. [Informe funcional](pruebas_sistema_2026-11-11.md), [log integrado](qa_sistema_20261111.log).
- Recorrido de navegador con cuatro roles, persistencia de estado de alerta, CSV y actualización de métricas **7 → 8 sin recargar**; aviso 429 visible.
- Evaluación vigente del mismo código: **87% de accuracy, 100% de recall, 100% de cobertura y p95 2.1595 s**, con 200 casos. [Informe y JSON](evaluacion_modelo_2026-11-11.md). Se reutiliza esa corrida del mismo día; no se inventa una segunda evaluación.
- Los casos adversos adicionales reprodujeron evasión con caracteres invisibles, ocultaciones incorrectas, HTTP 500 con NUL, credenciales de base excesivamente privilegiadas y deducción temporal de un valor agregado.
- npm audit: **cinco nodos afectados por avisos —uno alto y cuatro moderados—**, correspondientes a dos avisos raíz. Producción conserva un aviso alto transitivo. Esto no demuestra por sí solo explotación del navegador de PluriOne.

Las 76 comprobaciones originales no incluían todos los casos adversos nuevos. Por ello, sus resultados correctos son compatibles con los fallos que se describen a continuación. La prioridad se asigna según impacto y condiciones de explotación; un riesgo de arquitectura se distingue de un fallo reproducido.

## Hallazgos

### H01. Evasión de ocultación de teléfono mediante separadores invisibles

- **Severidad:** Alta
- **Componente:** Backend
- **Ubicación:** `app/services/sanitization.py:118`; patrón `_PHONE` en `app/services/sanitization.py:24`.
- **Descripción del Riesgo:** Reproducido localmente: `Mi telefono es 662\u200b123\u200b4567.` conserva el teléfono. La normalización NFC no elimina U+200B y el patrón no contempla ese separador. Al retirar los caracteres invisibles se recuperan los diez dígitos. Si llega por el flujo normal, el resultado de esta función es el texto destinado a almacenamiento y Azure. La prueba de evasión fue local, con Azure deshabilitado.
- **Solución Propuesta:** Normalizar de forma explícita los separadores invisibles admitidos antes de aplicar detectores, con regresiones de nombres, correos y teléfonos. Este cambio cubre los caracteres indicados; no constituye anonimización universal:

  ```python
  text = unicodedata.normalize("NFC", text)
  text = text.translate({ord("\u200b"): None, ord("\u2060"): None, ord("\ufeff"): None})
  ```

### H02. Pérdida de contenido por detecciones incorrectas de entidades

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/services/sanitization.py:6`, `app/services/sanitization.py:169` y `app/services/sanitization.py:179`.
- **Descripción del Riesgo:** Reproducido: `healthier balance` se sustituye por nombre oculto; también se alteran «Qué padre» y parte del relato de acoso E194. El reconocimiento español aplicado a ambos idiomas y la sustitución de entidades sin suficiente corroboración pueden borrar el sentido que necesita el modelo. La ocultación correcta de Ana López después de «jefa» sigue verificada, pero no cubre estos falsos positivos.
- **Solución Propuesta:** Revisar idioma y criterios de entidades y exigir pruebas de conservación semántica además de ocultación. Cambiar de modelo spaCy sin evaluar no acredita una solución. Estos son criterios de aceptación para una corrección, no una implementación completa del detector:

  ```python
  assert sanitize_text("The new schedule gives me a healthier balance between work and home") == (
      "The new schedule gives me a healthier balance between work and home"
  )
  assert "Ana López" not in sanitize_text("Mi jefa Ana López me humilla en las juntas.")
  ```

### H03. Texto con byte NUL provoca HTTP 500

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/schemas/feedback.py:14`; persistencia en `app/api/v1/endpoints/feedback.py:103`.
- **Descripción del Riesgo:** Reproducido con PostgreSQL real y Azure deshabilitado: un comentario con `\x00` pasa el esquema y termina en 500. En CSV se marca la fila fallida. Es validación incompleta y desperdicia procesamiento; no se demostró inyección SQL ni fuga de detalle al cliente.
- **Solución Propuesta:** Rechazar NUL en el validador compartido antes de sanitizar o llamar a IA, de modo que buzón devuelva 422 y CSV informe una fila inválida:

  ```python
  if isinstance(value, str):
      if "\x00" in value:
          raise ValueError("El comentario contiene un carácter nulo no permitido.")
      value = value.strip()
  ```

### H04. La API utiliza un superusuario de PostgreSQL

- **Severidad:** Alta
- **Componente:** Base de Datos
- **Ubicación:** `docker-compose.yml:31`, credenciales compartidas con `docker-compose.yml:7`.
- **Descripción del Riesgo:** La consulta de lectura al rol efectivo devolvió `rolsuper=true`, `rolcreatedb=true` y `rolcreaterole=true`. Una eventual ejecución arbitraria o acceso a esas credenciales excedería los datos de la aplicación. Es privilegio de PostgreSQL; el proceso de PostgreSQL corre como usuario `postgres`, y el backend Linux correctamente corre como UID 10001.
- **Solución Propuesta:** Crear un rol de ejecución separado, establecer su contraseña mediante un canal seguro y usarlo exclusivamente en DATABASE_URL. Ejecutar migraciones con otra identidad. Ejemplo de permisos a aplicar por el administrador en la base de la aplicación:

  ```sql
  CREATE ROLE plurione_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  GRANT USAGE ON SCHEMA public TO plurione_runtime;
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO plurione_runtime;
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO plurione_runtime;
  ```

  También se debe configurar CONNECT a la base concreta, contraseña y privilegios futuros de los objetos creados por migraciones. No basta crear el rol sin cambiar la conexión de la API.

### H05. Interfaz de desarrollo expuesta, usuario root y montajes de escritura

- **Severidad:** Media
- **Componente:** Docker
- **Ubicación:** `docker-compose.yml:25`, `docker-compose.yml:42`, `docker-compose.yml:45` y `docker-compose.yml:46`.
- **Descripción del Riesgo:** Los puertos 8000/5173 se publican en todas las interfaces; frontend ejecuta Vite de desarrollo y `id` confirmó UID 0. Sus fuentes están montadas con escritura. Es aceptable como entorno local controlado, pero aumenta el alcance de acceso desde la red y de una eventual ejecución comprometida. No se demostró exposición a Internet ni ejecución remota. HTTP también transmite las credenciales sin cifrado si se accede desde otra máquina.
- **Solución Propuesta:** Para demo local, limitar ambos puertos a loopback. Para despliegue, compilar la interfaz, servir los estáticos con HTTPS, usuario sin privilegios y sin montajes de fuentes. Fragmentos de Compose para el entorno local:

  ```yaml
  # En web:
  ports:
    - "127.0.0.1:8000:8000"
  # En frontend:
  ports:
    - "127.0.0.1:5173:5173"
  ```

  La migración del frontend a `user: node` requiere comprobar primero los permisos de `node_modules`; el cambio de puertos no resuelve por sí solo el usuario root ni sustituye una configuración de producción.

### H06. JWT persistente en localStorage y cierre sin revocación

- **Severidad:** Media
- **Componente:** Frontend
- **Ubicación:** `frontend/src/pages/Login.jsx:25`, `frontend/src/pages/Dashboard.jsx:208`, `app/core/security.py:17`.
- **Descripción del Riesgo:** Un JavaScript comprometido en el mismo origen podría leer el token, vigente ocho horas. Cerrar sesión elimina la copia del navegador; el backend no dispone de revocación de esa sesión. No se encontró un renderizado `dangerouslySetInnerHTML` ni se demostró una cadena XSS en esta revisión. El rol de la BD se valida en cada solicitud, por lo que editar el rol local no acredita elevación de privilegios.
- **Solución Propuesta:** Diseñar sesiones revocables, acortar la duración del acceso y coordinar frontend/backend para un transporte de sesión protegido. Si se adoptan cookies, requiere HTTPS, validación de origen y protección CSRF; añadir esta cookie aisladamente no migra OAuth2PasswordBearer:

  ```python
  response.set_cookie(
      "__Host-session", token, httponly=True, secure=True,
      samesite="strict", path="/", max_age=900,
  )
  ```

### H07. Deducción temporal pese al mínimo de cinco

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/api/v1/endpoints/feedback.py:420`, `app/api/v1/endpoints/feedback.py:521` y `app/api/v1/endpoints/feedback.py:524`.
- **Descripción del Riesgo:** Reproducido en QA: cinco análisis de valor cero muestran total 5/media 0; al agregarse un análisis 0.9 muestran total 6/media 0.15. La diferencia `6*0.15 - 5*0 = 0.9` recupera la contribución nueva. Un lector autorizado que conozca el momento y autor del envío podría asociarla. Los filtros mensuales evitan solapamientos espaciales, pero el mes abierto cambia con cada incorporación.
- **Solución Propuesta:** Publicar instantáneas de periodos cerrados o lotes con mínimo de nuevas contribuciones y evaluar un presupuesto de consultas o privacidad diferencial según el riesgo. Requiere diseño de publicación; este pseudocódigo expresa la regla y no sustituye su implementación transaccional:

  ```python
  if not period_is_closed and new_contributions_since_snapshot < minimum_new_contributions:
      return last_published_snapshot
  ```

### H08. Importación y notificaciones sin ejecución durable

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/api/v1/endpoints/feedback.py:129`, `app/api/v1/endpoints/feedback.py:233` y `app/api/v1/endpoints/feedback.py:331`.
- **Descripción del Riesgo:** Revisión estática: BackgroundTasks vive en el proceso web y cada fila se confirma por separado. Si el proceso termina, una importación puede quedar PROCESSING con parte del lote guardado. Volver a cargar puede duplicar comentarios porque no hay clave idempotente. Un fallo de correo no tiene reintento durable ni estado de entrega visible. No se mató el proceso durante una importación en esta repetición.
- **Solución Propuesta:** Persistir una tarea y una clave idempotente antes de responder 202, usar un trabajador recuperable y registrar intentos de notificación. La transacción por fila debe tener una identidad única por importación/fila. Ejemplo de restricción para el diseño nuevo, tras agregar sus columnas mediante migración:

  ```sql
  CREATE UNIQUE INDEX uq_feedback_import_row
      ON feedback_entries (import_id, source_row_number)
      WHERE import_id IS NOT NULL;
  ```

  Este índice requiere completar el esquema, almacenamiento seguro del trabajo y lógica del trabajador; no es una corrección aislada para copiar sobre el esquema actual.

### H09. Limitador en memoria y sin cuota global de IA

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/core/rate_limit.py:12` y `app/core/rate_limit.py:14`.
- **Descripción del Riesgo:** Los 429 funcionan en una instancia. El almacenamiento predeterminado `memory://` reinicia contadores al reiniciar el proceso y los divide entre réplicas. La cuota por IP tampoco limita el gasto global frente a muchas IP. No se realizó una prueba distribuida.
- **Solución Propuesta:** Configurar almacenamiento compartido, soporte Redis en las dependencias y un servicio Redis accesible solo por la red interna; agregar cuota global y límite de concurrencia de llamadas a IA. Configuración de almacenamiento prevista por el código:

  ```dotenv
  RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
  ```

  Debe desplegarse y probarse ese servicio antes de cambiar la variable; la variable sola no crea Redis.

### H10. Agregados cargan todas las filas del mes en memoria

- **Severidad:** Media
- **Componente:** Base de Datos
- **Ubicación:** `app/api/v1/endpoints/feedback.py:420`, `app/db/models.py:46` y `app/db/models.py:49`.
- **Descripción del Riesgo:** `query.all()` materializa los análisis y metadatos del departamento/mes para agregarlos en Python. El mes restringe fechas, no la cantidad de filas. Los modelos no declaran un índice compuesto de departamento y fecha. Puede crecer el consumo de memoria y tiempo bajo volumen o lectores concurrentes. En esta ruta se observaron consultas agregadas explícitas; no se demostró un patrón N+1.
- **Solución Propuesta:** Llevar conteos, sumas y agrupaciones a SQL y agregar el índice apropiado tras comprobar el plan con datos representativos:

  ```sql
  CREATE INDEX CONCURRENTLY ix_feedback_department_created
      ON feedback_entries (department_id, created_at);
  ```

  El índice mejora selección; no elimina la materialización. No se debe paginar los comentarios y calcular una media parcial como si fuera el total.

### H11. Idioma incorrecto implícito en Azure AI Language

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/services/ai_engine.py:80`.
- **Descripción del Riesgo:** La llamada omite idioma y el SDK instalado usa inglés `en`. El conjunto contiene 174 textos españoles y 26 ingleses. Es una configuración confirmada; no se ha aislado cuánto de los 26 errores explica. El accuracy global fue 87%, con recuperación de positivos de 78.57%.
- **Solución Propuesta:** Determinar el idioma por comentario y transmitirlo explícitamente, validando los idiomas soportados. Una vez disponible esa variable validada, la llamada debe incluirla:

  ```python
  response = language_client.analyze_sentiment(
      documents=[texto_seguro], language=language
  )[0]
  ```

  Se debe completar la determinación de `language` en los consumidores; fijar `es` para todos no cubre los textos ingleses. Repetir una comparación después del cambio.

### H12. Límite de CSV aplicado después del análisis multipart

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/api/v1/endpoints/feedback.py:302`, `app/api/v1/endpoints/feedback.py:315`.
- **Descripción del Riesgo:** El límite de 5 MB funciona sobre UploadFile, pero el servidor debe recibir y analizar multipart para construirlo antes de ejecutar ese cuerpo de función. Se confirmó que un multipart mal formado sin JWT recibe 400 de parser; el CSV bien formado sin JWT recibe 401. No se comprobó agotamiento de disco/memoria ni se afirma bypass del límite de importación.
- **Solución Propuesta:** Agregar límite de cuerpo, tiempo de recepción y concurrencia en el ingreso HTTP antes de FastAPI, ajustando el margen al contenedor multipart. Ejemplo para un proxy Nginx delante del backend:

  ```nginx
  location /api/ {
      client_max_body_size 6m;
      client_body_timeout 10s;
      proxy_pass http://web:8000;
  }
  ```

  Hay que impedir el acceso directo al puerto del backend para que no se evada el proxy y conservar el límite de archivo de 5 MB dentro de la aplicación.

### H13. Falta de presupuesto total de tiempo del pipeline

- **Severidad:** Media
- **Componente:** Backend
- **Ubicación:** `app/services/ai_engine.py:74`, `app/services/ai_engine.py:80`, `app/services/ai_engine.py:103`.
- **Descripción del Riesgo:** OpenAI tiene timeout de 10 s y cero reintentos, pero Azure Language utiliza los valores del SDK sin presupuesto total explícito del flujo. Se crean clientes por análisis. Las solicitudes lentas pueden ocupar trabajadores/conexiones. En las mediciones actuales el máximo fue 3.6086 s en modelo y 3.666 s en integración; no se simuló un bloqueo de red prolongado ni se demostró fuga de memoria.
- **Solución Propuesta:** Definir presupuestos de conexión, lectura y reintentos por servicio, además del plazo total de la tarea; cerrar o reutilizar clientes administrados por el ciclo de vida. Ejemplo de parámetros de transporte para revisar y probar con el SDK instalado:

  ```python
  language_client = TextAnalyticsClient(
      endpoint=os.environ["AZURE_LANGUAGE_ENDPOINT"],
      credential=AzureKeyCredential(os.environ["AZURE_LANGUAGE_KEY"]),
      connection_timeout=2, read_timeout=5, retry_total=0,
  )
  ```

  Estos límites no equivalen por sí solos a un timeout total ni garantizan el objetivo de tres segundos.

### H14. Esquema sin migraciones versionadas y carrera de administrador inicial

- **Severidad:** Baja
- **Componente:** Base de Datos
- **Ubicación:** `app/main.py:35`; `app/create_admin_cli.py:18` y `app/create_admin_cli.py:40`.
- **Descripción del Riesgo:** `create_all()` crea tablas ausentes y el migrador manual cubre dos columnas, sin historial general de versiones. Además, dos CLI simultáneos podrían verificar que no hay administrador y crear dos correos distintos, porque no existe restricción única del rol admin. Son riesgos estáticos; no se ejecutó una carrera simultánea ni se ensayó una actualización de esquema antiguo.
- **Solución Propuesta:** Versionar migraciones y aplicar exclusión/garantía en la base para el administrador único, después de revisar los administradores existentes:

  ```sql
  CREATE UNIQUE INDEX uq_single_initial_admin ON users ((role)) WHERE role = 'admin';
  ```

  Capturar la violación de unicidad y mantener credenciales de migración separadas. Confirmar primero que el requisito del producto sea conservar un único administrador.

### H15. Avisos vigentes en dependencias npm

- **Severidad:** Alta
- **Componente:** Frontend
- **Ubicación:** `frontend/package-lock.json:1548` (`follow-redirects` 1.16.1) y `frontend/package-lock.json:2220` (`minimatch` 10.2.6).
- **Descripción del Riesgo:** El escáner informa un paquete con aviso alto y cuatro nodos con avisos moderados por propagación. Son dos avisos raíz, no cinco ataques independientes. Producción conserva `follow-redirects`, transitivo de Axios 1.20.0. Su [aviso GHSA-mrwp-f3q8-3g9p](https://github.com/advisories/GHSA-mrwp-f3q8-3g9p) afecta 1.16.0–1.16.1 y corrige en 1.16.2; exige una combinación concreta de cabeceras y redirección. El aviso indica que su reproducción no afectó a Axios 1.20.0. No se demostró esa ruta en la aplicación ni en su bundle de navegador. El [aviso de minimatch](https://github.com/advisories/GHSA-g3hv-75wg-m249), corregido en 11.0.1, corresponde aquí a herramientas de desarrollo y patrones de glob no confiables. La severidad alta es la del aviso de paquete, con aplicabilidad a PluriOne pendiente de demostración.
- **Solución Propuesta:** Actualizar las transitivas dentro de los rangos compatibles, revisar el diff del lockfile y repetir lint/build/audit. Para paquetes que exijan cambio mayor del árbol de ESLint, planificar la actualización compatible; evitar `audit fix --force` sin revisión. Comprobaciones propuestas desde frontend:

  ```sh
  npm update follow-redirects
  npm run lint
  npm run build
  npm audit
  npm audit --omit=dev
  ```

  No se modificaron dependencias en esta revisión. No se ejecutó un escáner equivalente de advisories Python ni de imágenes; `pip check` solo acredita compatibilidad declarada.

### H16. Registro de excepciones puede incluir parámetros de persistencia

- **Severidad:** Baja
- **Componente:** Backend
- **Ubicación:** `app/api/v1/endpoints/feedback.py:263` y `app/create_admin_cli.py:45`.
- **Descripción del Riesgo:** La revisión estática encontró `logger.exception`, que puede incluir la representación de una excepción SQLAlchemy y sus parámetros ante determinados errores. Eso trasladaría datos a logs con otra retención y otros lectores. El caso NUL del CSV no volcó parámetros en la comprobación realizada; no se presenta una fuga general como reproducida.
- **Solución Propuesta:** Registrar un identificador del incidente y el tipo de excepción, y suprimir parámetros del motor. Ejemplo para la configuración de SQLAlchemy:

  ```python
  engine = create_engine(SQLALCHEMY_DATABASE_URL, hide_parameters=True)
  ```

  Evitar trazas con payloads de entrada y aplicar acceso/retención limitada a los logs. El filtrado de parámetros no sustituye la revisión del resto de mensajes.

## Controles comprobados

JWT restringe HS256, exige exp/sub y consulta usuario/rol actual en BD; las pruebas de firma/expiración y permisos pasaron. CORS usa orígenes concretos y no habilita credenciales de navegador. El mecanismo Bearer actual no envía automáticamente una cookie entre sitios; adoptar cookies exige revisar CSRF. React interpola texto escapado y no se encontraron sinks explícitos de HTML crudo en los componentes revisados.

Las consultas ORM revisadas utilizan parámetros para entrada de usuario; el intento de login con contenido SQL fue rechazado. SMTP usa STARTTLS con contexto de verificación de certificados. La aplicación backend corre sin root. PostgreSQL publica su puerto solo en loopback. `.env` está excluido de Git y del contexto Docker; `git ls-files` mostró únicamente `.env.example` dentro de esa familia, sin leer ni adjuntar secretos reales.

La ruta raíz no devolvió CSP, X-Content-Type-Options ni HSTS en TestClient. Para un despliegue HTTPS deben definirse en el proxy con una política compatible con el frontend. En el entorno local HTTP, HSTS no constituye una protección activa. No se efectuó una prueba de explotación XSS, carga sostenida, caída/reanudación de trabajos, varias réplicas, restauración de backup ni entrega SMTP real.

## Orden recomendado

1. Corregir H01 y H03 y mantener las regresiones de nombres ya correctas; abordar H02 y H11 con pruebas bilingües.
2. Separar privilegios de BD, restringir publicación de la demo y actualizar dependencias revisando compatibilidad.
3. Resolver privacidad temporal y sesiones según las garantías que se prometan al usuario.
4. Incorporar ejecución durable, idempotencia, presupuestos de IA y consultas agregadas antes de escalar.

Las soluciones arquitectónicas anteriores indican los cambios necesarios y fragmentos de apoyo; las que requieren esquema, trabajador, proxy o migración de autenticación se identifican expresamente y no se presentan como parches completos aislados. La regeneración de informes documenta el estado actual y no significa que estos riesgos hayan sido corregidos.
