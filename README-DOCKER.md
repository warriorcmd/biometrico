# 🐳 Servicios con Docker

Este proyecto contiene 3 servicios FastAPI independientes:

1. **Biometric Service** (puerto 8000) - Procesa archivos Excel/CSV de registros biométricos
2. **Image Service con IA** (puerto 8500) - Elimina fondos usando rembg con IA
3. **Image Simple Service** (puerto 8501) - Elimina fondos usando OpenCV básico

## 📋 Requisitos Previos

- Docker Desktop instalado
- Docker Compose (incluido con Docker Desktop)

## 🚀 Instrucciones de Uso

### 1. Ejecutar TODOS los servicios

```powershell
# Construir y ejecutar todos los servicios
docker-compose up --build

# O en segundo plano
docker-compose up -d --build
```

### 2. Ejecutar servicios INDIVIDUALES

```powershell
# Solo el servicio biométrico
docker-compose up biometric-api

# Solo el servicio de imagen con IA
docker-compose up image-api

# Solo el servicio de imagen simple
docker-compose up image-simple-api
```

### 3. Ver logs

```powershell
# Todos los servicios
docker-compose logs -f

# Servicio específico
docker-compose logs -f biometric-api
docker-compose logs -f image-api
docker-compose logs -f image-simple-api
```

### 4. Detener servicios

```powershell
# Detener todos
docker-compose down

# Detener uno específico
docker-compose stop biometric-api
```

## 🌐 Acceso a las APIs

Una vez iniciados los contenedores:

### 📊 Servicio Biométrico (Puerto 8000)
- **API**: http://localhost:8000
- **Documentación**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 🎨 Servicio de Imagen con IA (Puerto 8500)
- **API**: http://localhost:8500
- **Documentación**: http://localhost:8500/docs
- **ReDoc**: http://localhost:8500/redoc

### 🖼️ Servicio de Imagen Simple (Puerto 8501)
- **API**: http://localhost:8501
- **Documentación**: http://localhost:8501/docs
- **ReDoc**: http://localhost:8501/redoc

## 📝 Endpoints Principales

### 1️⃣ Servicio Biométrico - POST /procesar

Procesa archivos biométricos en formato Excel o CSV.

**Ejemplo con curl:**
```powershell
curl -X POST "http://localhost:8000/procesar" `
  -H "accept: application/json" `
  -H "Content-Type: multipart/form-data" `
  -F "archivo=@registros.xlsx"
```

**Ejemplo con Python:**
```python
import requests
files = {'archivo': open('registros.xlsx', 'rb')}
response = requests.post('http://localhost:8000/procesar', files=files)
print(response.json())
```

### 2️⃣ Servicio de Imagen IA - POST /remove-background/

Elimina el fondo de una imagen usando IA (rembg).

**Ejemplo con curl:**
```powershell
curl -X POST "http://localhost:8500/remove-background/" `
  -H "accept: application/json" `
  -F "file=@foto.jpg" `
  -o "sin_fondo.png"
```

**Ejemplo con Python:**
```python
import requests
files = {'file': open('foto.jpg', 'rb')}
response = requests.post('http://localhost:8500/remove-background/', files=files)
with open('sin_fondo.png', 'wb') as f:
    f.write(response.content)
```

### 3️⃣ Servicio de Imagen Simple - POST /remove-background/

Elimina el fondo usando procesamiento básico (OpenCV).

**Ejemplo con curl:**
```powershell
curl -X POST "http://localhost:8501/remove-background/" `
  -H "accept: application/json" `
  -F "file=@foto.jpg" `
  -o "sin_fondo.png"
```

## 🔧 Comandos Útiles

### Ver contenedores en ejecución
```powershell
docker ps
```

### Entrar a un contenedor (shell)
```powershell
docker-compose exec biometric-api bash
docker-compose exec image-api bash
docker-compose exec image-simple-api bash
```

### Reconstruir sin caché
```powershell
# Todos los servicios
docker-compose build --no-cache

# Un servicio específico
docker-compose build --no-cache biometric-api
```

### Ver uso de recursos
```powershell
docker stats
```

### Reiniciar un servicio específico
```powershell
docker-compose restart biometric-api
docker-compose restart image-api
docker-compose restart image-simple-api
```

### Eliminar todo y reiniciar limpio
```powershell
docker-compose down -v
docker-compose up --build
```

## 🐛 Solución de Problemas

### El puerto 8000 ya está en uso
```powershell
# Cambiar el puerto en docker-compose.yml
# Modificar la línea: "8000:8000" a "8001:8000" (por ejemplo)
```

### Problemas con dependencias
```powershell
# Reconstruir sin caché
docker-compose build --no-cache
docker-compose up
```

### Ver logs de errores
```powershell
docker-compose logs --tail=100 biometric-api
```

## 📦 Estructura del Proyecto

```
biometrico/
├── biometric_service.py     # API de procesamiento biométrico
├── image.py                 # API de eliminación de fondo con IA
├── image_simple.py          # API de eliminación de fondo simple
├── requirements.txt         # Dependencias de Python
├── Dockerfile.biometric     # Dockerfile para servicio biométrico
├── Dockerfile.image         # Dockerfile para servicio de imagen IA
├── docker-compose.yml       # Orquestación de todos los servicios
├── .dockerignore           # Archivos excluidos del build
└── README-DOCKER.md        # Esta documentación
```

## 🔄 Modo Desarrollo

El contenedor está configurado con hot-reload. Los cambios en el código se reflejan automáticamente sin necesidad de reiniciar el contenedor.

## 🌟 Características

- ✅ 3 servicios independientes y simultáneos
- ✅ Hot reload automático en desarrollo
- ✅ Logs en tiempo real por servicio
- ✅ Persistencia de código con volúmenes
- ✅ Puertos aislados sin conflictos
- ✅ Compatible con OpenCV, pandas, rembg/IA
- ✅ Fácil escalabilidad individual

## 📊 Monitoreo

El servicio incluye un health check que verifica el estado cada 30 segundos:

```powershell
# Ver estado del health check
docker inspect --format='{{json .State.Health}}' biometric-service
```

## 🚢 Despliegue en Producción

Para producción, considera:

1. Remover la opción `--reload` del CMD en Dockerfile
2. Usar variables de entorno para configuración
3. Implementar límites de recursos
4. Configurar reverse proxy (nginx)
5. Habilitar HTTPS

```yaml
# Ejemplo para producción en docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 512M
```
