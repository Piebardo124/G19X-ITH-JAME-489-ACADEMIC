# Frontend de PluriOne

Interfaz React con Vite para el buzón anónimo, inicio de sesión, dashboard de métricas, alertas y carga CSV. La guía principal de configuración, backend, Azure y evaluación está en el [README de la raíz](../README.md).

## Ejecutar con Docker Compose

Desde la raíz del repositorio:

~~~powershell
docker compose up --build
~~~

Vite queda disponible en <http://localhost:5173>. La API debe responder en <http://localhost:8000>.

## Ejecutar solo el frontend

Requisitos: Node.js 20 o posterior y npm.

~~~powershell
npm install
npm run dev -- --host 0.0.0.0
~~~

Para apuntar a una API distinta de `http://localhost:8000`, crea `frontend/.env.local` con:

~~~dotenv
VITE_API_BASE_URL=http://localhost:8000
~~~

No agregues llaves de Azure, credenciales SMTP ni secretos de backend a variables `VITE_*`: Vite las expone al navegador.

## Comprobaciones

~~~powershell
npm run lint
npm run build
~~~
