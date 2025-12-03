from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import io
from datetime import timedelta

app = FastAPI()

# Parámetros ajustables
DUPLICATE_MINUTES = 3        # eliminar marcas dentro de X minutos (duplicados)
MAX_SHIFT_HOURS = 14         # jornada máxima razonable (incluye horas extras)
MIN_SESSION_HOURS = 0.01     # sesión mínima válida (evitar ceros exactos)
MAX_BREAK_HOURS = 18         # si entre dos marcas hay más de X horas, son entradas distintas
NORMAL_SHIFT_HOURS = 8       # jornada laboral estándar (para referencia de horas extras)
MORNING_CUTOFF_HOUR = 8      # marcas antes de esta hora pueden ser salidas de turno nocturno

@app.post("/procesar")
async def procesar(archivo: UploadFile):
    contenido = await archivo.read()

    # Intentar leer Excel o CSV (soporte básico)
    try:
        df = pd.read_excel(io.BytesIO(contenido))
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(contenido), encoding="utf-8", engine="python")
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": "No se pudo leer el archivo", "detalle": str(e)})

    # Normalizar columnas
    df.columns = df.columns.str.lower().str.strip()

    # Detectar columnas
    user_col = next((c for c in df.columns if "dni" in c or "user" in c or c == "id" or "usuario" in c), None)
    datetime_col = next((c for c in df.columns if "fecha" in c and "hora" in c or "datetime" in c or "timestamp" in c), None)
    if not datetime_col:
        # buscar fecha o hora por separado
        fecha_col = next((c for c in df.columns if "fecha" in c or "date" in c or "dia" in c), None)
        hora_col  = next((c for c in df.columns if "hora" in c or "time" in c), None)
    else:
        fecha_col = hora_col = None

    if not user_col:
        return JSONResponse(status_code=400, content={"error": "No se detectó columna usuario (dni/user/id)"})

    # Construir datetime
    df["user_id"] = df[user_col]
    if datetime_col:
        df["datetime"] = pd.to_datetime(df[datetime_col], dayfirst=True, errors="coerce")
    else:
        if not fecha_col or not hora_col:
            return JSONResponse(status_code=400, content={"error": "No se detectaron columnas de fecha/hora"})
        df["datetime"] = pd.to_datetime(df[fecha_col].astype(str) + " " + df[hora_col].astype(str), dayfirst=True, errors="coerce")

    df = df.dropna(subset=["datetime"])
    # ordenar
    df = df.sort_values(["user_id", "datetime"])

    # 1) eliminar duplicados muy cercanos (ej: dentro de 3 min)
    df["diff_min"] = df.groupby("user_id")["datetime"].diff().dt.total_seconds().div(60)
    df = df[(df["diff_min"].isna()) | (df["diff_min"] > DUPLICATE_MINUTES)].copy()
    df = df.drop(columns=["diff_min"])

    # 2) Estrategia mejorada: emparejar cronológicamente con detección inteligente
    result_sessions = []
    suspect_sessions = 0

    for uid, g in df.groupby("user_id"):
        # ordenar todas las marcas cronológicamente
        g = g.sort_values("datetime").reset_index(drop=True)
        marks = list(g["datetime"])
        
        # emparejar considerando patrones de turnos
        i = 0
        while i < len(marks):
            entrada = marks[i]
            
            # buscar la siguiente marca como posible salida
            if i + 1 < len(marks):
                salida = marks[i + 1]
                dur_h = (salida - entrada).total_seconds() / 3600.0
                
                # validar que tenga sentido como par entrada-salida
                flag = None
                
                if dur_h <= 0:
                    # si es negativo o cero, algo anda mal - registrar solo la entrada
                    result_sessions.append({
                        "person_id": int(uid),
                        "date_time_attendance": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                        "date_attendance": entrada.strftime("%Y-%m-%d"),
                        "time_attendance": entrada.strftime("%H:%M:%S"),
                        "type": "INGRESO"
                    })
                    i += 1
                    continue
                
                # Lógica inteligente para detectar si la segunda marca es salida o nueva entrada
                # Si la segunda marca es de madrugada (< MORNING_CUTOFF_HOUR), probablemente sea salida
                # aunque hayan pasado muchas horas
                if dur_h > MAX_BREAK_HOURS:
                    # Verificar si la segunda marca es de madrugada
                    if salida.hour < MORNING_CUTOFF_HOUR:
                        # Es turno nocturno - tratar como entrada-salida
                        pass  # continuar con el procesamiento normal
                    else:
                        # La primera marca es una entrada sin salida
                        result_sessions.append({
                            "person_id": int(uid),
                            "date_time_attendance": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                            "date_attendance": entrada.strftime("%Y-%m-%d"),
                            "time_attendance": entrada.strftime("%H:%M:%S"),
                            "type": "INGRESO"
                        })
                        # La segunda marca la procesaremos en la siguiente iteración
                        i += 1
                    continue
                
                # Es un par válido entrada-salida
                if dur_h > MAX_SHIFT_HOURS:
                    flag = "muy_larga"
                    suspect_sessions += 1
                
                # registrar la sesión con datos básicos
                result_sessions.append({
                    "person_id": int(uid),
                    "date_time_attendance": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                    "date_attendance": entrada.strftime("%Y-%m-%d"),
                    "time_attendance": entrada.strftime("%H:%M:%S"),
                    "type": "INGRESO"
                })
                
                result_sessions.append({
                    "person_id": int(uid),
                    "date_time_attendance": salida.strftime("%Y-%m-%d %H:%M:%S"),
                    "date_attendance": salida.strftime("%Y-%m-%d"),
                    "time_attendance": salida.strftime("%H:%M:%S"),
                    "type": "SALIDA"
                })
                
                i += 2  # avanzar dos posiciones
            else:
                # marca sin pareja (última marca sin salida)
                result_sessions.append({
                    "person_id": int(uid),
                    "date_time_attendance": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                    "date_attendance": entrada.strftime("%Y-%m-%d"),
                    "time_attendance": entrada.strftime("%H:%M:%S"),
                    "type": "INGRESO"
                })
                i += 1

    # ordenar por person_id + fecha/hora
    result_sessions = sorted(result_sessions, key=lambda x: (x["person_id"], x["date_time_attendance"]))

    return {
        "success": True,
        "total_sesiones": len(result_sessions),
        "data": result_sessions
    }
