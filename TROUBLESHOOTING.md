# 🔧 Guía de Solución de Problemas

## Error: onnxruntime executable stack (image-api)

### Síntoma
```
ImportError: /usr/local/lib/python3.11/site-packages/onnxruntime/capi/onnxruntime_pybind11_state.cpython-311-x86_64-linux-gnu.so: cannot enable executable stack as shared object requires: Invalid argument
```

### Causa
Problema de compatibilidad entre onnxruntime y ciertas configuraciones de seguridad del kernel Linux (especialmente con SELinux o kernels antiguos).

### Solución
El `Dockerfile.image` ya está configurado con versiones compatibles:
- `onnxruntime==1.16.3`
- `rembg[gpu]==2.0.57`

**En el VPS, ejecuta:**
```bash
# Reconstruir SOLO el servicio image-api
docker compose build --no-cache image-api

# Reiniciar el servicio
docker compose up -d image-api

# Verificar logs
docker compose logs -f image-api
```

### Alternativa: Si persiste el error
Si el error continúa, puedes comentar/eliminar el servicio `image-api` del `docker-compose.yml` temporalmente y usar solo `image-simple-api` que funciona sin IA.

---

## Error 405 Method Not Allowed en /biometrico/procesar

### Síntoma
```json
{"detail": "Method Not Allowed"}
```

### Causa
El endpoint `/procesar` solo acepta método POST, no GET.

### Solución
Usar POST con archivo adjunto:

**Con curl:**
```bash
curl -X POST "https://sdrclientes.shop/biometrico/procesar" \
  -H "accept: application/json" \
  -F "archivo=@registros.xlsx"
```

**Con Python:**
```python
import requests
files = {'archivo': open('registros.xlsx', 'rb')}
response = requests.post('https://sdrclientes.shop/biometrico/procesar', files=files)
print(response.json())
```

---

## Error 502 Bad Gateway

### Causas comunes:
1. **El servicio backend no está corriendo** - verifica con `docker compose ps`
2. **El servicio crasheó al iniciar** - revisa logs con `docker compose logs <servicio>`
3. **Problema de red entre nginx y contenedor** - verifica la red de Docker

### Verificación:
```bash
# Ver estado de todos los servicios
docker compose ps

# Ver logs de un servicio específico
docker compose logs -f <nombre-servicio>

# Reiniciar un servicio
docker compose restart <nombre-servicio>
```

---

## Puerto 80 ya en uso

### Síntoma
```
Error starting userland proxy: listen tcp4 0.0.0.0:80: bind: address already in use
```

### Solución
Cambiar el puerto en `docker-compose.yml`:

```yaml
nginx-proxy:
  ports:
    - "8080:80"  # En lugar de "80:80"
```

Luego acceder a: `http://sdrclientes.shop:8080/...`

---

## Reconstruir servicios desde cero

Si tienes problemas persistentes:

```bash
# Detener y eliminar todo
docker compose down -v

# Eliminar imágenes antiguas
docker compose rm -f
docker image prune -a

# Reconstruir sin caché
docker compose build --no-cache

# Iniciar
docker compose up -d

# Ver logs
docker compose logs -f
```

---

## Verificar conectividad interna

```bash
# Entrar al contenedor nginx
docker compose exec nginx-proxy sh

# Probar conectividad a los servicios
wget -O- http://biometric-api:8000/docs
wget -O- http://image-api:8500/docs
wget -O- http://image-simple-api:8501/docs
```

---

## Recursos útiles

- Documentación de rembg: https://github.com/danielgatis/rembg
- Documentación de onnxruntime: https://onnxruntime.ai/docs/
- FastAPI docs: https://fastapi.tiangolo.com/
