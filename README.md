# UETS Backend — Python / FastAPI

Reemplazo del backend NestJS + MongoDB. 100 % compatible con el frontend Angular existente.

## Requisitos

- Python 3.11+
- MongoDB corriendo en `localhost:27017` (misma instancia que usaba NestJS)

## Instalación

```bash
cd backend
pip install -r requirements.txt
```

## Configuración

Edita `.env` (ya viene con valores para desarrollo):

| Variable | Descripción |
|---|---|
| `PORT` | Puerto del servidor (default: 8000) |
| `NODE_ENV` | `development` o `production` |
| `BACKEND_URL` | URL pública del backend (para URLs de imágenes) |
| `MONGODB_URI` | Conexión a MongoDB |
| `JWT_SECRET` | Secreto JWT (cambiar en producción) |
| `JWT_EXPIRES_IN` | Expiración del token (`8h`, `1d`, etc.) |
| `CORS_ORIGINS` | Orígenes permitidos (coma separados) |

## Ejecutar

```bash
cd backend
python run.py
```

El servidor arranca en `http://0.0.0.0:8000` con hot-reload en desarrollo.

## Actualizar el frontend

Cambia las URLs de API en los frontends de `:3000` a `:8000`:

**dashboard-web-uets** — `src/environments/environment.ts`:
```typescript
apiUrl: 'http://192.168.200.26:8000/api/v1'
```

**Uets** — `src/environments/environment.ts`:
```typescript
apiUrl: 'http://192.168.200.26:8000/api/v1'
```

## Documentación Swagger

Disponible solo en `development`:
- `http://localhost:8000/api/v1/docs`

## Endpoints implementados

| Módulo | Rutas |
|---|---|
| Auth | POST /auth/login · GET /auth/me |
| Users | CRUD /users |
| Eventos | CRUD + /publicos · /destacado · /slug/:slug · PATCH destacado/toggle-publicado |
| Noticias | CRUD + /publicas · /destacadas · /publica/:id |
| Especialidades | CRUD + /publicas · /publicas/:id |
| Autoridades | CRUD + /publicas · /publica/:id |
| Logros | CRUD + /publicos · /destacados · /categoria/:cat · /publico/:id |
| Estudiantes | CRUD + /stats/por-especialidad |
| Recursos | CRUD + /publicos |
| Configuracion | GET/PUT/DELETE /:clave · GET /publica/:clave · POST /imagenes |
| Imagenes | POST /imagenes · POST /imagenes/from-url · GET /imagenes/gridfs/:id |
| Actividad | GET · GET /recientes · POST · DELETE /limpiar · DELETE /:id |
| Notificaciones | CRUD + GET /unread-count · PATCH /:id/leer · PATCH /leer-todas |

## WebSocket

Compatible con **socket.io-client** en el frontend. Mismo comportamiento que NestJS.

Eventos emitidos automáticamente en cada operación CRUD:
- `evento:creado` / `evento:actualizado` / `evento:eliminado`
- `noticia:creado` / `noticia:actualizado` / `noticia:eliminado`
- `especialidad:creado` / `especialidad:actualizado` / `especialidad:eliminado`
- `autoridad:creado` / `autoridad:actualizado` / `autoridad:eliminado`
- `logro:creado` / `logro:actualizado` / `logro:eliminado`
- `recurso:creado` / `recurso:actualizado` / `recurso:eliminado`
- `configuracion:{clave}:actualizada`

## Imágenes (GridFS)

- Subida: `POST /api/v1/imagenes` — multipart/form-data, campo `file`
- Respuesta: `{ "url": "/api/v1/imagenes/gridfs/{id}", ... }`
- Las imágenes se optimizan a WebP (máx 1920px, calidad 82)
- Las imágenes de la colección NestJS en GridFS siguen siendo accesibles sin migración
