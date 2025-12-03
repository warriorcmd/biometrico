from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from rembg import remove
import io
import os

app = FastAPI(
    title="API de Eliminación de Fondos",
    description="API para remover fondos de imágenes usando rembg con IA",
    version="1.0.0",
    root_path="/quitar_fondo"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Formatos de imagen permitidos
ALLOWED_FORMATS = {"image/jpeg", "image/png", "image/jpg", "image/webp"}

@app.get("/")
async def root():
    """Endpoint raíz para verificar que la API está funcionando"""
    return {
        "message": "API de Eliminación de Fondos funcionando correctamente",
        "endpoints": {
            "POST /remove-background/": "Elimina el fondo de una imagen"
        }
    }

@app.post("/remove-background/")
async def remove_background(file: UploadFile = File(...)):
    """
    Elimina el fondo de una imagen usando rembg con IA.
    Funciona con cualquier tipo de imagen y fondo.
    
    Args:
        file: Archivo de imagen (JPEG, PNG, WEBP)
        
    Returns:
        Imagen sin fondo en formato PNG
    """
    try:
        # Validar tipo de archivo
        if file.content_type not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato de archivo no válido. Formatos permitidos: {', '.join(ALLOWED_FORMATS)}"
            )
        
        # Leer archivo subido
        image_bytes = await file.read()
        
        # Validar que no esté vacío
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")
        
        # Intentar abrir la imagen
        try:
            input_image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"No se pudo leer la imagen: {str(e)}")
        
        # Usar rembg para eliminar el fondo con IA
        try:
            # remove() usa un modelo de IA para detectar y eliminar el fondo
            output_image = remove(input_image)
            
            # Guardar en buffer
            buffer = io.BytesIO()
            output_image.save(buffer, format="PNG")
            buffer.seek(0)
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error al remover el fondo: {str(e)}"
            )
        
        # Retornar como StreamingResponse
        return StreamingResponse(
            buffer, 
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=sin_fondo_{file.filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la imagen: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
