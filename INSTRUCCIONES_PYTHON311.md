# Instalar Python 3.11 en paralelo (sin afectar Python 3.14)

## Paso 1: Descargar Python 3.11
1. Ve a: https://www.python.org/downloads/release/python-31110/
2. Descarga: "Windows installer (64-bit)"
3. Durante la instalación:
   - ✅ Marca "Add python.exe to PATH"
   - ✅ Personaliza la instalación
   - Instala en: `C:\Python311\`

## Paso 2: Crear entorno virtual con Python 3.11

```powershell
# Ve a la carpeta del proyecto
cd C:\Users\Develop-Sdrimsac\Documents\biometrico

# Crea entorno virtual con Python 3.11
C:\Python311\python.exe -m venv venv

# Activa el entorno virtual
.\venv\Scripts\Activate.ps1

# Instala las dependencias
pip install fastapi uvicorn rembg Pillow python-multipart

# Ejecuta la aplicación
python image.py
```

## Paso 3: Uso diario

Cada vez que quieras usar la API:

```powershell
cd C:\Users\Develop-Sdrimsac\Documents\biometrico
.\venv\Scripts\Activate.ps1
python image.py
```

Para salir del entorno virtual:
```powershell
deactivate
```

## Nota
Tu Python 3.14 seguirá funcionando normal para otros proyectos.
