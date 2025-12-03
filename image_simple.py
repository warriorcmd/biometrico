from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
import cv2
import numpy as np

app = FastAPI(
    title="API de Eliminación de Fondos (Método Simple)",
    description="API para remover fondos usando procesamiento de imagen básico",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_FORMATS = {"image/jpeg", "image/png", "image/jpg", "image/webp"}

@app.get("/")
async def root():
    return {
        "message": "API de Eliminación de Fondos (Método Simple) funcionando",
        "endpoints": {
            "POST /remove-background/": "Elimina el fondo de una imagen"
        }
    }

def remove_background_simple(image_bytes):
    """
    Remueve el fondo usando técnicas de procesamiento de imagen básicas.
    No es tan bueno como rembg pero funciona sin dependencias complejas.
    """
    # Convertir bytes a imagen numpy
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Crear máscara usando GrabCut
    mask = np.zeros(img.shape[:2], np.uint8)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    
    # Definir un rectángulo que probablemente contiene el objeto principal
    # (dejando un margen del 5% en cada lado)
    height, width = img.shape[:2]
    margin = int(min(height, width) * 0.05)
    rect = (margin, margin, width - 2*margin, height - 2*margin)
    
    # Aplicar GrabCut
    cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
    
    # Crear máscara binaria
    mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
    
    # Suavizar bordes de la máscara
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel)
    mask2 = cv2.GaussianBlur(mask2, (3, 3), 0)
    
    # Convertir a RGBA
    img_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    
    # Aplicar máscara al canal alpha
    img_rgba[:, :, 3] = mask2 * 255
    
    return img_rgba

@app.post("/remove-background/")
async def remove_background(file: UploadFile = File(...)):
    """
    Elimina el fondo de una imagen usando técnicas básicas de procesamiento.
    
    NOTA: Este método funciona mejor con:
    - Objetos centrados en la imagen
    - Fondos uniformes o de color sólido
    - Buena iluminación y contraste
    """
    try:
        # Validar tipo de archivo
        if file.content_type not in ALLOWED_FORMATS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no válido. Permitidos: {', '.join(ALLOWED_FORMATS)}"
            )
        
        # Leer archivo
        image_bytes = await file.read()
        
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Archivo vacío")
        
        # Remover fondo
        img_no_bg = remove_background_simple(image_bytes)
        
        # Convertir a PIL Image
        img_pil = Image.fromarray(img_no_bg, 'RGBA')
        
        # Guardar en buffer
        buffer = io.BytesIO()
        img_pil.save(buffer, format="PNG")
        buffer.seek(0)
        
        return StreamingResponse(
            buffer,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename=sin_fondo_{file.filename}"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
