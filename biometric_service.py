from fastapi import FastAPI, UploadFile
from fastapi.responses import JSONResponse
import pandas as pd
import io
import json

app = FastAPI(
    title="Biometric Service API",
    description="API para procesar archivos biométricos (Excel/CSV)",
    version="1.0.0",
    root_path="/biometrico"
)

@app.post("/procesar")
async def procesar(archivo: UploadFile):

    contenido = await archivo.read()
    df = None
    last_error = None
    
    # Detectar el tipo de archivo por extensión o contenido
    nombre_archivo = archivo.filename.lower() if archivo.filename else ""
    es_excel = nombre_archivo.endswith(('.xlsx', '.xls')) or contenido.startswith(b'PK\x03\x04')
    
    print(f"Archivo recibido: {archivo.filename}")
    print(f"¿Es Excel?: {es_excel}")
    print(f"Primeros bytes: {contenido[:20]}")
    
    # Intentar leer como Excel primero (más común en sistemas biométricos)
    if es_excel:
        try:
            print(f"Intentando leer como archivo Excel...")
            # Intentar con openpyxl primero
            try:
                df = pd.read_excel(io.BytesIO(contenido), engine='openpyxl')
                print(f"✓ Archivo Excel leído exitosamente con openpyxl")
            except ImportError:
                # Si openpyxl no está instalado, intentar con xlrd
                print("openpyxl no disponible, intentando con xlrd...")
                df = pd.read_excel(io.BytesIO(contenido), engine='xlrd')
                print(f"✓ Archivo Excel leído exitosamente con xlrd")
        except Exception as e:
            last_error = e
            print(f"✗ Error al leer Excel: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "No se pudo leer el archivo Excel",
                    "detalle": str(e),
                    "solucion": "Por favor, instala openpyxl ejecutando: pip install openpyxl"
                }
            )
    
    # Si no es Excel, intentar como CSV
    if not es_excel and (df is None or df.empty):
        print(f"Intentando leer como archivo CSV...")
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        delimiters = [',', ';', '\t']
        
        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    df = pd.read_csv(
                        io.BytesIO(contenido), 
                        encoding=encoding, 
                        delimiter=delimiter,
                        on_bad_lines='skip',
                        engine='python'
                    )
                    if df is not None and not df.empty and len(df.columns) >= 2:
                        print(f"✓ CSV leído con encoding={encoding}, delimiter={delimiter}")
                        break
                except Exception as e:
                    last_error = e
                    continue
            
            if df is not None and not df.empty and len(df.columns) >= 2:
                break
    
            if df is not None and not df.empty and len(df.columns) >= 2:
                break
    
    if df is None or df.empty:
        raise ValueError(f"No se pudo leer el archivo. Último error: {last_error}")

    # Normalize column names (remove spaces, lowercase)
    df.columns = df.columns.str.strip().str.lower()
    
    # Print available columns for debugging
    print(f"Columnas encontradas: {list(df.columns)}")
    
    # Mapeo flexible de columnas
    user_id_col = None
    datetime_col = None
    
    # Buscar columna de user_id/dni
    for col in df.columns:
        if any(x in col for x in ['dni', 'user_id', 'userid', 'usuario', 'id']):
            user_id_col = col
            break
    
    # Buscar columna de fecha/hora (puede ser una sola columna o dos separadas)
    fecha_col = None
    hora_col = None
    
    for col in df.columns:
        if 'fecha/hora' in col or 'fecha-hora' in col or 'datetime' in col or 'timestamp' in col:
            datetime_col = col
            break
        elif 'fecha' in col or 'date' in col or 'dia' in col:
            fecha_col = col
        elif 'hora' in col or 'time' in col or 'tiempo' in col:
            hora_col = col
    
    if not user_id_col:
        raise ValueError(f"No se encontró columna de usuario/DNI. Columnas disponibles: {list(df.columns)}")
    
    # Renombrar columna de user_id
    df = df.rename(columns={user_id_col: 'user_id'})
    
    # Procesar fecha/hora según el formato
    if datetime_col:
        # Caso: fecha y hora en una sola columna
        print(f"Usando columna combinada: {datetime_col}")
        df["datetime"] = pd.to_datetime(df[datetime_col], format='%d/%m/%Y %H:%M', errors='coerce')
    elif fecha_col and hora_col:
        # Caso: fecha y hora en columnas separadas
        print(f"Usando columnas separadas: {fecha_col} y {hora_col}")
        df["datetime"] = pd.to_datetime(df[fecha_col] + " " + df[hora_col])
    else:
        raise ValueError(f"No se encontraron columnas de fecha/hora. Columnas disponibles: {list(df.columns)}")
    
    df = df.sort_values(["user_id", "datetime"]).drop_duplicates()
    # Eliminar filas sin fecha válida
    df = df.dropna(subset=['datetime']).copy()

    def agrupar_sesiones(g):
        """
        Agrupa marcas alternando ENTRADA/SALIDA de forma inteligente.
        
        Lógica mejorada:
        1. Las marcas de madrugada (00:00-05:59) son SALIDAS de turno nocturno
        2. Para el resto del día, alterna ENTRADA → SALIDA basándose en el contexto
        3. Emparejar cronológicamente, considerando gaps grandes (>3h) como nuevas sesiones
        """
        marcas = sorted(g["datetime"].tolist())
        if not marcas:
            return []
        
        # Paso 1: Agrupar marcas cercanas (< 5 minutos) y decidir cuál mantener según contexto
        # ENTRADA: mantener el PRIMERO (llegó en el primer registro)
        # SALIDA: mantener el ÚLTIMO (se fue en el último registro)
        
        # Primero, hacer una pre-clasificación temporal para saber qué tipo es cada grupo
        grupos_duplicados = []
        i = 0
        while i < len(marcas):
            grupo = [marcas[i]]
            j = i + 1
            while j < len(marcas):
                diff_minutos = (marcas[j] - marcas[i]).total_seconds() / 60
                if diff_minutos <= 5:
                    grupo.append(marcas[j])
                    j += 1
                else:
                    break
            grupos_duplicados.append(grupo)
            i = j
        
        # Ahora procesar cada grupo con lógica inteligente
        filtered = []
        ultimo_tipo = None
        
        for grupo in grupos_duplicados:
            if len(grupo) == 1:
                filtered.append(grupo[0])
                # Determinar tipo para siguiente iteración
                hora = grupo[0].hour
                if hora < 6:
                    ultimo_tipo = 'SALIDA'
                elif ultimo_tipo is None:
                    ultimo_tipo = 'ENTRADA'
                elif len(filtered) > 1:
                    diff_horas = (grupo[0] - filtered[-2]).total_seconds() / 3600
                    if diff_horas > 12:
                        ultimo_tipo = 'ENTRADA'
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        ultimo_tipo = 'ENTRADA'
                    else:
                        ultimo_tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    ultimo_tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
            else:
                # Grupo de duplicados - determinar tipo primero
                hora = grupo[0].hour
                if hora < 6:
                    tipo_grupo = 'SALIDA'
                elif ultimo_tipo is None:
                    tipo_grupo = 'ENTRADA'
                elif len(filtered) > 0:
                    diff_horas = (grupo[0] - filtered[-1]).total_seconds() / 3600
                    if diff_horas > 12:
                        tipo_grupo = 'ENTRADA'
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        tipo_grupo = 'ENTRADA'
                    else:
                        tipo_grupo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    tipo_grupo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                
                # Seleccionar según el tipo
                if tipo_grupo == 'ENTRADA':
                    marca_seleccionada = grupo[0]  # PRIMERO
                    print(f"  🔄 Grupo ENTRADA: Manteniendo PRIMERO {marca_seleccionada.strftime('%Y-%m-%d %H:%M')} (descartando {len(grupo)-1} duplicados)")
                else:
                    marca_seleccionada = grupo[-1]  # ÚLTIMO
                    print(f"  🔄 Grupo SALIDA: Manteniendo ÚLTIMO {marca_seleccionada.strftime('%Y-%m-%d %H:%M')} (descartando {len(grupo)-1} duplicados)")
                
                filtered.append(marca_seleccionada)
                ultimo_tipo = tipo_grupo
        
        if len(filtered) != len(marcas):
            print(f"  Marcas después de filtrar duplicados: {len(filtered)} (original: {len(marcas)})")
        
        print(f"  Total marcas a procesar: {len(filtered)}")
        
        # Paso 2: Clasificar con lógica de alternancia mejorada
        marcas_clasificadas = []
        ultimo_tipo = None  # Rastrear el último tipo asignado
        
        for i, marca in enumerate(filtered):
            hora = marca.hour
            
            # Marcas de madrugada (00:00-05:59) son SALIDAS de turno nocturno
            if hora < 6:
                tipo = 'SALIDA'
                ultimo_tipo = 'SALIDA'
            else:
                # Para el resto del día, alternamos basándonos en el último tipo
                if ultimo_tipo is None:
                    # Primera marca del día
                    tipo = 'ENTRADA'
                elif i > 0:
                    diff_horas = (marca - filtered[i-1]).total_seconds() / 3600
                    
                    # Gap muy grande (>12h) sugiere que es un nuevo día/turno
                    if diff_horas > 12:
                        tipo = 'ENTRADA'
                    # Gap de 2+ horas después de una SALIDA = nueva sesión (INGRESO)
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        tipo = 'ENTRADA'
                        print(f"      Gap de {diff_horas:.1f}h después de SALIDA → Nueva sesión")
                    # Sin gap significativo, simplemente alternamos
                    else:
                        tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    # Alternancia simple
                    tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                
                ultimo_tipo = tipo
            
            marcas_clasificadas.append({
                'datetime': marca,
                'tipo': tipo,
                'hora': hora
            })
            
            print(f"    {marca.strftime('%Y-%m-%d %H:%M')} → {tipo}")
        
        # Paso 3: Emparejar ENTRADA → SALIDA consecutivas
        sesiones = []
        i = 0
        
        while i < len(marcas_clasificadas):
            marca_actual = marcas_clasificadas[i]
            
            if marca_actual['tipo'] == 'ENTRADA' and not marca_actual.get('usado'):
                # Buscar la siguiente SALIDA
                for j in range(i + 1, len(marcas_clasificadas)):
                    siguiente = marcas_clasificadas[j]
                    
                    if siguiente.get('usado'):
                        continue
                    
                    if siguiente['tipo'] == 'SALIDA':
                        ingreso = marca_actual['datetime']
                        salida = siguiente['datetime']
                        duracion = (salida - ingreso).total_seconds() / 3600
                        
                        # Validar que tenga sentido (hasta 16 horas)
                        if 0 < duracion <= 16:
                            sesiones.append((ingreso, salida))
                            
                            if salida.hour < 6:
                                print(f"  ✓ Sesión nocturna: {ingreso.strftime('%Y-%m-%d %H:%M')} → {salida.strftime('%Y-%m-%d %H:%M')} ({duracion:.1f}h)")
                            else:
                                print(f"  ✓ Sesión diurna: {ingreso.strftime('%Y-%m-%d %H:%M')} → {salida.strftime('%Y-%m-%d %H:%M')} ({duracion:.1f}h)")
                            
                            marca_actual['usado'] = True
                            siguiente['usado'] = True
                            break
            
            elif marca_actual['tipo'] == 'SALIDA' and not marca_actual.get('usado'):
                # SALIDA sin entrada, buscar entrada previa no usada
                for j in range(i - 1, -1, -1):
                    anterior = marcas_clasificadas[j]
                    
                    if anterior.get('usado'):
                        continue
                    
                    if anterior['tipo'] == 'ENTRADA':
                        ingreso = anterior['datetime']
                        salida = marca_actual['datetime']
                        duracion = (salida - ingreso).total_seconds() / 3600
                        
                        if 0 < duracion <= 16:
                            sesiones.append((ingreso, salida))
                            print(f"  ✓ Sesión nocturna (emparejada retroactivamente): {ingreso.strftime('%Y-%m-%d %H:%M')} → {salida.strftime('%Y-%m-%d %H:%M')} ({duracion:.1f}h)")
                            
                            anterior['usado'] = True
                            marca_actual['usado'] = True
                            break
            
            i += 1
        
        # Reportar marcas no emparejadas
        for m in marcas_clasificadas:
            if not m.get('usado'):
                print(f"  ⚠️ {m['tipo']} sin pareja: {m['datetime'].strftime('%Y-%m-%d %H:%M')}")
        
        return sesiones

    # Preparar datos crudos para enviar
    registros_crudos = []
    
    for uid, g in df.groupby('user_id'):
        print(f"\n📊 Procesando usuario: {uid}")
        sesiones = agrupar_sesiones(g)
        
        # Obtener todas las marcas del usuario ordenadas
        marcas = sorted(g["datetime"].tolist())
        
        # Paso 1: Agrupar marcas cercanas (< 5 minutos) y decidir cuál mantener según contexto
        grupos_duplicados = []
        i = 0
        while i < len(marcas):
            grupo = [marcas[i]]
            j = i + 1
            while j < len(marcas):
                diff_minutos = (marcas[j] - marcas[i]).total_seconds() / 60
                if diff_minutos <= 5:
                    grupo.append(marcas[j])
                    j += 1
                else:
                    break
            grupos_duplicados.append(grupo)
            i = j
        
        # Procesar cada grupo con lógica inteligente
        filtered = []
        ultimo_tipo = None
        
        for grupo in grupos_duplicados:
            if len(grupo) == 1:
                filtered.append(grupo[0])
                # Determinar tipo para siguiente iteración
                hora = grupo[0].hour
                if hora < 6:
                    ultimo_tipo = 'SALIDA'
                elif ultimo_tipo is None:
                    ultimo_tipo = 'ENTRADA'
                elif len(filtered) > 1:
                    diff_horas = (grupo[0] - filtered[-2]).total_seconds() / 3600
                    if diff_horas > 12:
                        ultimo_tipo = 'ENTRADA'
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        ultimo_tipo = 'ENTRADA'
                    else:
                        ultimo_tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    ultimo_tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
            else:
                # Grupo de duplicados
                hora = grupo[0].hour
                if hora < 6:
                    tipo_grupo = 'SALIDA'
                elif ultimo_tipo is None:
                    tipo_grupo = 'ENTRADA'
                elif len(filtered) > 0:
                    diff_horas = (grupo[0] - filtered[-1]).total_seconds() / 3600
                    if diff_horas > 12:
                        tipo_grupo = 'ENTRADA'
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        tipo_grupo = 'ENTRADA'
                    else:
                        tipo_grupo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    tipo_grupo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                
                # Seleccionar según el tipo: ENTRADA=primero, SALIDA=último
                if tipo_grupo == 'ENTRADA':
                    filtered.append(grupo[0])
                else:
                    filtered.append(grupo[-1])
                
                ultimo_tipo = tipo_grupo
        
        marcas = filtered
        
        # Clasificar cada marca como ENTRADA o SALIDA
        ultimo_tipo = None  # Rastrear el último tipo asignado
        
        for i, marca in enumerate(marcas):
            hora = marca.hour
            
            # Marcas de madrugada (00:00-05:59) son SALIDAS de turno nocturno
            if hora < 6:
                tipo = 'SALIDA'
                ultimo_tipo = 'SALIDA'
            else:
                # Para el resto del día, alternamos basándonos en el último tipo
                if ultimo_tipo is None:
                    # Primera marca del día
                    tipo = 'ENTRADA'
                elif i > 0:
                    diff_horas = (marca - marcas[i-1]).total_seconds() / 3600
                    
                    # Gap muy grande (>12h) sugiere que es un nuevo día/turno
                    if diff_horas > 12:
                        tipo = 'ENTRADA'
                    # Gap de 2+ horas después de una SALIDA = nueva sesión (INGRESO)
                    elif diff_horas >= 2 and ultimo_tipo == 'SALIDA':
                        tipo = 'ENTRADA'
                    # Sin gap significativo, simplemente alternamos
                    else:
                        tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                else:
                    # Alternancia simple
                    tipo = 'SALIDA' if ultimo_tipo == 'ENTRADA' else 'ENTRADA'
                
                ultimo_tipo = tipo
            
            # Preparar registro crudo con el formato solicitado
            registro = {
                'person_id': int(uid),
                'date_time_attendance': marca.strftime('%Y-%m-%d %H:%M:%S'),
                'date_attendance': marca.strftime('%Y-%m-%d'),
                'time_attendance': marca.strftime('%H:%M:%S'),
                'type': tipo,
                'biometrico': {
                    'datetime': marca.strftime('%Y-%m-%d %H:%M:%S'),
                    'hora': marca.hour,
                    'minuto': marca.minute,
                    'dia_semana': marca.strftime('%A'),
                    'timestamp': int(marca.timestamp())
                }
            }
            
            registros_crudos.append(registro)
            print(f"  ✓ {marca.strftime('%Y-%m-%d %H:%M:%S')} → {tipo}")
    
    # Ordenar todos los registros por fecha/hora
    registros_crudos.sort(key=lambda x: x['date_time_attendance'])
    
    # Devolver los datos crudos
    resultado = {
        'success': True,
        'total_registros': len(registros_crudos),
        'data': registros_crudos
    }

    return resultado
