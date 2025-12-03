from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import io
from datetime import timedelta

app = FastAPI()

# Parámetros ajustables
DUPLICATE_MINUTES = 3        # eliminar marcas dentro de X minutos (duplicados)
NIGHT_CUTOFF_HOUR = 6        # marcas antes de esta hora se asignan al día anterior (turnos noche)
MAX_SHIFT_HOURS = 13         # si una sesión dura más de esto se marca como sospechosa
MIN_SESSION_HOURS = 0.01     # sesión mínima válida (evitar ceros exactos)

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

    # 2) asignar día laboral real (marcas entre 00:00 y NIGHT_CUTOFF_HOUR -> día anterior)
    df["date_real"] = df["datetime"].dt.date
    df.loc[df["datetime"].dt.hour < NIGHT_CUTOFF_HOUR, "date_real"] = df.loc[df["datetime"].dt.hour < NIGHT_CUTOFF_HOUR, "date_real"] - pd.to_timedelta(1, unit='d')

    # 3) agrupar por user + date_real y recolectar listas de marcas
    result_sessions = []
    suspect_sessions = 0

    for uid, g in df.groupby("user_id"):
        # orden por marca absoluta
        g = g.sort_values("datetime").reset_index(drop=True)
        # agrupar por date_real
        daily_groups = { d: grp.sort_values("datetime") for d, grp in g.groupby("date_real") }

        # convertimos a lista ordenada por fecha_real ascendente
        days_sorted = sorted(daily_groups.keys())

        for idx, day in enumerate(days_sorted):
            marks = list(daily_groups[day]["datetime"])
            # Si hay cantidad impar, intentar "tomar prestada" la primera marca del siguiente día
            if len(marks) % 2 == 1:
                # intentar tomar la primera marca del día siguiente si existe
                if idx + 1 < len(days_sorted):
                    next_day = days_sorted[idx + 1]
                    next_marks = list(daily_groups[next_day]["datetime"])
                    if next_marks:
                        # solo si la marca del siguiente día es de madrugada (ej: < NIGHT_CUTOFF_HOUR) o razonable
                        cand = next_marks[0]
                        # si la marca candidata ocurre en la madrugada del next_day (hora < NIGHT_CUTOFF_HOUR)
                        if cand.hour < NIGHT_CUTOFF_HOUR:
                            # anexarla para emparejar salida nocturna
                            marks.append(cand)
                            # también remover esa marca del siguiente grupo para no duplicarla
                            daily_groups[next_day] = daily_groups[next_day].iloc[1:]
                        else:
                            # si no es madrugada, preferimos dejar la marca sin pareja y tratarla como sospechosa
                            pass

            # emparejar secuencialmente
            for i in range(0, len(marks), 2):
                if i+1 < len(marks):
                    entrada = marks[i]
                    salida  = marks[i+1]
                    dur_h = (salida - entrada).total_seconds() / 3600.0

                    flag = None
                    if dur_h <= 0:
                        flag = "negativa_o_zero"
                    elif dur_h > MAX_SHIFT_HOURS:
                        flag = "muy_larga"
                        suspect_sessions += 1

                    # solo registrar sesiones mínimas razonables
                    if dur_h >= MIN_SESSION_HOURS:
                        result_sessions.append({
                            "user_id": int(uid),
                            "entrada": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                            "salida": salida.strftime("%Y-%m-%d %H:%M:%S"),
                            "horas": round(dur_h, 2),
                            "date_real": str(day),
                            "flag": flag
                        })
                else:
                    # marca sin pareja restante -> la registramos como incompleta para revisión
                    entrada = marks[i]
                    result_sessions.append({
                        "user_id": int(uid),
                        "entrada": entrada.strftime("%Y-%m-%d %H:%M:%S"),
                        "salida": None,
                        "horas": None,
                        "date_real": str(day),
                        "flag": "sin_pareja"
                    })

    # ordenar por user + entrada
    result_sessions = sorted(result_sessions, key=lambda x: (x["user_id"], x["entrada"] or ""))

    return {
        "success": True,
        "total_sesiones": len(result_sessions),
        "suspect_sessions": suspect_sessions,
        "data": result_sessions
    }
