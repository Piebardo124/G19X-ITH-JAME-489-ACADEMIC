# Pruebas del sistema — 11 de noviembre de 2026

## Versión y resultado

Commit: `a9b1cd52a986ba4bd57a3601098fd15e29dac262` (`Limpia de codigo y soluciones`). Ejecución por Codex a solicitud del autor. Inicio de integración: `2026-11-11T18:20:06Z` (10:20 local, America/Los_Angeles). Entorno temporal retirado a las 10:29 local. La documentación se terminó después de la ejecución.

| Verificación repetida | Resultado | Evidencia |
| --- | --- | --- |
| Pruebas unitarias/regresión | **55 correctas**, 0 fallidas; 0.822 s, `OK`, salida 0 | — |
| Integración con PostgreSQL y Azure reales | **76 PASS, 0 FAIL**, salida 0 | [qa_sistema_20261111.log](qa_sistema_20261111.log) |
| ESLint | Sin errores; salida 0 | — |
| Build de frontend | Correcto; 84 módulos, 348 ms, salida 0 | — |
| Dependencias Python | `pip check`: sin dependencias rotas | Salida de herramientas; aviso no bloqueante de caché de pip |
| Sintaxis backend | `compileall` con caché en `/tmp/plurione-pycache`: sin errores reportados | Salida de herramientas |
| Dependencias npm | Auditoría completa: 1 aviso alto y 4 moderados; producción: 1 alto | — |
| Modelo de 200 casos | Corrida real del mismo día y código: 87% accuracy, 100% recall, p95 2.1595 s | [Evaluación del modelo](evaluacion_modelo_2026-11-11.md) |

La evaluación de 200 casos ya realizada se reutiliza como evidencia vigente del mismo commit y de los mismos hashes de código y datos. No se efectuó otra corrida de 200 ni se presentan dos mediciones independientes. Pasar las pruebas funcionales no elimina los hallazgos de seguridad.

## Entorno y aislamiento

Windows/PowerShell, Docker 29.7.2, Compose v5.5.1, Python 3.12.15, PostgreSQL 15, Node 20 y Vite 8.3.5. Los cambios locales al iniciar correspondían a documentación y evidencias de la demo/evaluación, sin cambios en `app/`, `scripts/`, frontend, Docker ni requisitos.

Se creó la base **`plurione_qa_20261111_35c1878b`** con las tablas y departamentos de la aplicación. Las 76 comprobaciones utilizaron FastAPI TestClient y esa base real. El script interceptó el envío de notificaciones y deshabilitó SMTP: no se comprobó entrega de correo externo.

Para navegador se crearon `plurione-qa-web-35c1878b` y `plurione-qa-front-35c1878b`, en `127.0.0.1:18000` y `127.0.0.1:15173`. La interfaz se compiló temporalmente con `VITE_API_BASE_URL=http://localhost:18000`; el modo `serve` del script agregó exclusivamente el origen de prueba 15173 a CORS. El CORS de la aplicación original se comprobó por separado en integración.

Las comprobaciones adversas deshabilitaron Azure y SMTP. Los conteos de la base original antes y después de ellas fueron idénticos: **4 usuarios, 31 comentarios y 12 alertas**. El navegador escribió únicamente en QA. Se detuvieron los dos contenedores temporales y se eliminó únicamente esa base. Los tres servicios de `plurione-demo` quedaron activos, con PostgreSQL healthy.

## Cobertura de las 76 comprobaciones integradas

| Área | Resultado observado |
| --- | --- |
| Cuentas | Administrador inicial; rechazo del segundo; creación hr, analyst y executive; validación de rol, correo, duplicado normalizado y contraseñas; hashes bcrypt persistidos |
| Autenticación | Login normalizado con cuatro roles; contraseña incorrecta 401; JWT ausente, inválido o expirado 401; el rol de base de datos prevalece sobre un claim distinto |
| Autorización | Métricas para cuatro roles; alertas y CSV para admin/hr/analyst; executive recibe 403 en esas acciones |
| Buzón | Rechazo de texto corto/largo, solo dígitos, no anónimo y departamento inexistente |
| IA y almacenamiento | Seis comentarios con Azure real disponibles; persistencia de análisis; correo/teléfono sintéticos ocultos en el caso de riesgo |
| CSV | Aceptación 202; resumen 2 procesadas, 1 omitida y 1 fallida; estado con observaciones; extensión, cabecera, UTF-8, máximo de 5 MB y límite de 1000 filas |
| Métricas | Muestra mínima, ausencia de texto original, supresión de grupos menores de cinco y rechazo de mes parcial |
| Alertas | Generación real de riesgo; cambios OPEN/IN_PROGRESS/CLOSED/FALSE_POSITIVE; rechazo de estado inválido y modificación por executive; límite de página y fechas |
| Fallo de IA | Comentario guardado como no analizado, con aviso al cliente, al deshabilitar la configuración en el proceso QA |
| Límites y CORS | 429 en sexto intento de login y buzón; origen 5173 permitido y origen ajeno rechazado |

Las creaciones CLI se ejecutaron invocando sus funciones y simulando la entrada del administrador. No fueron sesiones humanas de `getpass`.

Latencias HTTP de los seis envíos de integración: **3.666, 2.261, 1.282, 1.457, 1.891 y 1.828 segundos**. Incluyen aplicación, IA y persistencia; no son la misma medición que el evaluador del modelo. El primer envío superó tres segundos.

## Recorrido visual nuevo

Se utilizó la interfaz real de QA, sin modificar su estado mediante JavaScript de página:

1. Buzón: envío sintético positivo, estado de procesamiento y mensaje «Comentario recibido y analizado correctamente»; formulario limpio al finalizar.
2. Admin: métricas de RH/noviembre con 7 análisis y promedio +0.73, distribución suprimida, bandeja y CSV visibles. Alerta #2 cambiada a Atendida; el estado se conservó después de recargar.
3. Executive: panel ejecutivo con métricas; cero bandejas de alertas y cero controles CSV en el DOM.
4. Analyst: métricas, bandeja y control CSV visibles.
5. HR: carga de un CSV con una fila válida de RH y una `x` omitida. Resumen visible: **1 procesadas, 1 omitidas y 0 fallidas**. El total cambió **7 → 8 sin recargar**, conservando +0.73.
6. Se cerró sesión entre roles. Seis intentos inválidos consecutivos mostraron el aviso del límite de solicitudes y respuesta HTTP 429.

El primer intento del automatizador de adjuntar archivo agotó la espera del selector. Se recuperó la pestaña y se completó la selección mediante el input real. Una espera del texto final también venció antes de actualizarse la captura; la observación posterior mostró el resumen y el total correcto. Se registran como incidencias de automatización, sin atribuirlas a fallos del sistema.

## Comprobaciones adversas adicionales

Las comprobaciones adicionales produjeron los siguientes resultados:

| Caso | Resultado real |
| --- | --- |
| Nombre después de «jefa» | Correctamente oculto |
| Teléfono con U+200B entre grupos | **Permanece visible**, evadiendo la sanitización |
| Expresión inglesa `healthier balance` | **Oculta como nombre**, perdiendo contenido útil |
| Byte NUL en buzón | **HTTP 500**, en vez de rechazo de validación |
| Byte NUL en CSV | Una fila fallida y `COMPLETED_WITH_WARNINGS`; no se observó volcado de parámetros SQL en ese caso |
| Rol PostgreSQL de la aplicación | **Superusuario**, puede crear bases y roles |
| Privacidad temporal | Cinco valores cero dan media 0; tras añadir 0.9, seis valores dan media 0.15: se recupera el valor añadido por diferencia |
| Cadena de intento SQL en login | HTTP 401; no hubo bypass en esta comprobación |
| CSV sin JWT | HTTP 401 |
| Multipart mal formado sin JWT | HTTP 400 de parser antes de autenticación; no se hizo una prueba de agotamiento de recursos |

Los fallos reproducidos están fuera de las 76 comprobaciones funcionales del script existente. Por ello, **76 PASS no significa ausencia de errores**.

## Reproducción y límites

Desde la raíz, con un identificador nuevo y el entorno de demo activo:

```powershell
$qaDatabase = 'plurione_qa_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
docker compose -p plurione-demo run --rm --no-deps -T -e "QA_DATABASE=$qaDatabase" -v "${PWD}:/workspace:ro" -w /workspace web python scripts/qa_sistema.py api
docker compose -p plurione-demo run --rm --no-deps -T -e "QA_DATABASE=$qaDatabase" -v "${PWD}:/workspace:ro" -w /workspace web python scripts/qa_sistema.py cleanup
```

La integración usa comentarios sintéticos y consume cuota de Azure. Los comandos anteriores ejecutan las 76 comprobaciones integradas y su limpieza; las comprobaciones adversas adicionales no forman parte de ese procedimiento. La limpieza elimina exclusivamente la base temporal identificada. No se probaron carga sostenida, varias réplicas, reinicio durante una importación, entrega SMTP real ni restauración de respaldos. La auditoría npm no sustituye un escáner de vulnerabilidades Python o de imágenes de contenedores, que no se ejecutó en esta repetición.
