from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import io

app = FastAPI()

# Parámetros
DUPLICATE_MINUTES = 3


@app.post("/procesar")
async def procesar(archivo: UploadFile):
    contenido = await archivo.read()

    # Intentar leer Excel o CSV
    try:
        df = pd.read_excel(io.BytesIO(contenido))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(contenido), encoding="utf-8", engine="python")
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"error": "No se pudo leer el archivo", "detalle": str(e)}
            )

    # Normalizar columnas
    df.columns = df.columns.str.lower().str.strip()

    # Detectar columna usuario
    user_col = next(
        (c for c in df.columns if "dni" in c or "user" in c or c == "id" or "usuario" in c),
        None
    )

    datetime_col = next(
        (c for c in df.columns if "fecha" in c and "hora" in c or "datetime" in c or "timestamp" in c),
        None
    )

    # Si fecha/hora vienen separadas
    if not datetime_col:
        fecha_col = next((c for c in df.columns if "fecha" in c or "date" in c), None)
        hora_col = next((c for c in df.columns if "hora" in c or "time" in c), None)
    else:
        fecha_col = hora_col = None

    if not user_col:
        return JSONResponse(
            status_code=400,
            content={"error": "No se detectó columna usuario (dni/user/id)"}
        )

    # Construir datetime final
    df["user_id"] = df[user_col]

    if datetime_col:
        df["datetime"] = pd.to_datetime(df[datetime_col], dayfirst=True, errors="coerce")
    else:
        df["datetime"] = pd.to_datetime(
            df[fecha_col].astype(str) + " " + df[hora_col].astype(str),
            dayfirst=True,
            errors="coerce"
        )

    # Limpiar
    df = df.dropna(subset=["datetime"])

    # Ordenar
    df = df.sort_values(["user_id", "datetime"])

    # Eliminar duplicados cercanos
    df["diff_min"] = df.groupby("user_id")["datetime"].diff().dt.total_seconds().div(60)
    df = df[(df["diff_min"].isna()) | (df["diff_min"] > DUPLICATE_MINUTES)].copy()
    df = df.drop(columns=["diff_min"])

    # RESULTADO FINAL: SOLO MARCAS ORDENADAS
    result = []

    for _, row in df.iterrows():
        result.append({
            "person_id": int(row["user_id"]),
            "datetime": row["datetime"].strftime("%Y-%m-%d %H:%M:%S"),
            "date": row["datetime"].strftime("%Y-%m-%d"),
            "time": row["datetime"].strftime("%H:%M:%S")
        })

    return {
        "success": True,
        "total": len(result),
        "data": result
    }
