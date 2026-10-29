# Bitácora de pruebas del sistema — 29 de octubre de 2026

## Resultado

- 19 pruebas unitarias/regresión existentes: correctas.
- 76 comprobaciones integradas del script `scripts/qa_sistema.py`: correctas; 0 fallidas.
- Frontend: `npm run lint` y `npm run build` correctos dentro del contenedor (Vite 8.3.5).
- Backend: `pip check` sin dependencias rotas.
- Recorridos del navegador: buzón, login/logout con los cuatro roles, permisos visuales, métricas, alerta, CSV y aviso 429 comprobados.

Esto documenta una prueba funcional amplia del código actual. No constituye una prueba de carga, un pentest exhaustivo ni una nueva evaluación estadística del modelo sobre 200 casos.

## Entorno y aislamiento

Windows, Docker Desktop/Compose, backend Python 3.12, PostgreSQL 15 y frontend Node 20. La aplicación principal respondió HTTP 200 en los puertos 8000 y 5173 y PostgreSQL estuvo saludable.

Se creó una base PostgreSQL vacía y separada, `plurione_qa_20261029_72c9`, usando las mismas dependencias y modelos. El ciclo de vida de la aplicación creó sus tablas y departamentos. No se borró el volumen ni se alteraron las tablas de la base original.

Las comprobaciones API integradas usaron FastAPI TestClient con PostgreSQL real. Las pruebas de navegador usaron dos contenedores adicionales en `http://localhost:18000` y `http://localhost:15173`, conectados a esa misma base QA. El wrapper de pruebas permitió exclusivamente el origen adicional del frontend QA; la configuración CORS original se comprobó por separado.

Se conservaron las variables Azure para comprobar ambos servicios con comentarios sintéticos. Para SMTP se vaciaron las credenciales y, en las pruebas API, se interceptó la función de notificación. No se enviaron correos a destinatarios reales. La base QA y los dos contenedores adicionales se eliminaron al finalizar. La aplicación principal permaneció activa.

## Cobertura integrada

| Área | Comprobaciones ejecutadas | Resultado |
| --- | --- | --- |
| Usuarios | Administrador inicial, rechazo de segundo administrador, creación persistente de hr/analyst/executive | Correcto |
| Validaciones de cuentas | Rol admin rechazado por create_user, correo inválido y duplicado normalizado, contraseña corta y superior a 72 bytes, hash bcrypt persistido | Correcto |
| Login | Cuatro roles, normalización del correo y contraseña incorrecta | Correcto |
| JWT | Ausente, inválido y expirado rechazados; el rol de la base prevalece sobre un claim de rol distinto | Correcto |
| Autorización | Métricas accesibles por los cuatro roles; alertas y CSV permitidos para admin/hr/analyst y rechazados para executive | Correcto |
| Buzón | Texto corto/largo, solo números, is_anonymous=false y departamento inexistente rechazados | Correcto |
| Azure y persistencia | Seis comentarios analizados por los dos servicios; polaridad persistida; correo y teléfono sintéticos no persistidos en el comentario sanitizado | Correcto |
| Métricas | Agregados con seis respuestas válidas; texto original ausente; supresión para un grupo inferior a cinco; mes parcial rechazado | Correcto |
| Alertas | Generación por riesgo real de IA; cambios a IN_PROGRESS/CLOSED/FALSE_POSITIVE/OPEN; rechazo de estado inválido y modificación por executive | Correcto |
| Consulta de alertas | page_size superior a 100 y fechas invertidas rechazados | Correcto |
| CSV | Aceptación 202; resumen de 2 procesadas, 1 omitida y 1 fallida; extensión, cabecera, UTF-8 y exceso de 5 MB rechazados; máximo de 1000 filas aplicado | Correcto |
| Fallo de IA | Con una llave de Azure deshabilitada en el proceso QA, el comentario se guardó como no analizado y se informó al cliente | Correcto |
| Rate limiting | Sexta solicitud al login y al buzón recibió 429 con detail en español | Correcto |
| CORS | Origen localhost:5173 permitido; origen ajeno rechazado | Correcto |

La creación no administrativa se comprobó invocando la función de validación/persistencia `create_user`; el administrador se creó mediante `init_admin` con captura de entrada simulada. No se hizo una sesión humana interactiva de getpass para cada rol.

## Recorridos de interfaz

1. Se abrió el buzón QA y se envió un comentario sintético. El formulario mostró el estado de procesamiento, la API respondió 200 y el campo se limpió al terminar.
2. El administrador inició sesión y vio seis respuestas analizadas, la distribución oculta por privacidad, las alertas con el nivel «Alto» y el control CSV.
3. Desde la interfaz se cambió la alerta 2 a «En revisión» y se verificó el cambio visible.
4. Se cerró sesión y se entró como executive: aparecieron las métricas y no aparecieron la bandeja de alertas ni el formulario CSV.
5. Se entró como hr: aparecieron la bandeja y el formulario CSV. Se adjuntó `documentos/qa_interfaz_20261029.csv` y se comprobó el resumen «1 procesadas, 1 omitidas y 0 fallidas».
6. Se entró como analyst y se comprobó que estaban visibles la bandeja y el control CSV; se cerró sesión.
7. Se hicieron intentos inválidos de login y se verificó el aviso «Demasiados Intentos. Por favor, espera unos minutos» al recibir 429.

Evidencia visual del formulario: `documentos/qa_login_20261029.jpg`. El aviso 429 se comprobó en el árbol de accesibilidad del navegador y en los registros HTTP de la API. La distribución del formulario original se comprobó con un ancho de 400 px en un viewport de 1280 × 720.

## Hallazgos de esta ejecución

### Instrucción de pruebas del README no reproducible dentro de la imagen

El comando `docker compose exec web python -m unittest ...` falló al importar las seis suites: la imagen copia `app/`, pero no los archivos `test_*.py` ni `scripts/`. No fue un fallo de las aserciones del código. Al montar el repositorio en un contenedor temporal, las 19 pruebas pasaron.

Comando utilizado desde la raíz del proyecto en Windows:

```powershell
docker compose run --rm --no-deps -v "${PWD}:/workspace:ro" -w /workspace web python -m unittest -v test_privacy test_mvp_acceptance test_csv_import test_alerts test_email_service test_model_evaluation
```

### Primera respuesta de IA superior a tres segundos

Las latencias medidas desde TestClient incluyen el flujo HTTP de aplicación, sanitización, Azure y persistencia. No incluyen renderizado de navegador y no son directamente equivalentes a la medición del evaluador del modelo.

| Caso | Segundos |
| --- | ---: |
| 1 | 3.622 |
| 2 | 1.839 |
| 3 | 1.833 |
| 4 | 1.735 |
| 5 | 1.705 |
| 6 | 1.796 |

La primera respuesta superó tres segundos. Seis casos no bastan para certificar un percentil de producción ni para invalidar la evaluación anterior de 200 comentarios. Conviene medir por separado arranque, ejecución caliente y concurrencia antes de prometer un tiempo máximo.

## Límites de la comprobación

- El correo se probó con el SMTP simulado de la suite y con la invocación de notificación interceptada; no se verificó entrega real en una bandeja externa.
- No se repitió la evaluación de accuracy/recall con los 200 comentarios ni se solicitó un nuevo etiquetado humano.
- No se realizaron pruebas de carga sostenida, caída/reanudación de importaciones, restauración de respaldos ni despliegue con varias réplicas.
- La base QA partió vacía; las imágenes y dependencias aprovecharon la caché de Docker. No se acredita una instalación desde una máquina sin Docker/caché.
- Los riesgos de arquitectura de la auditoría estática previa no quedan resueltos porque estas pruebas funcionales hayan pasado.

## Repetir la prueba integrada

Usa un identificador nuevo para evitar colisiones y ejecuta desde la raíz. La ejecución realiza llamadas sintéticas a Azure y consume su cuota; el script no envía correos reales.

```powershell
$qaDatabase = 'plurione_qa_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
docker compose run --rm --no-deps -e "QA_DATABASE=$qaDatabase" -v "${PWD}:/workspace:ro" -w /workspace web python scripts/qa_sistema.py api
docker compose run --rm --no-deps -e "QA_DATABASE=$qaDatabase" -v "${PWD}:/workspace:ro" -w /workspace web python scripts/qa_sistema.py cleanup
```

`cleanup` elimina solo la base temporal seleccionada. El script exige el prefijo `plurione_qa_` y rechaza el nombre de la base original.
