import os
import pandas as pd
import hashlib
import json
import re

# --- CONFIGURACIÓN ---
# Esta ruta se mantiene como la original de tu entorno
ROOT_DIR = "../datos_simulaciones/simulation_data/R_2.0"

def parse_params(filepath):
    """
    Lee params.in manejando el bloque de granos y variables clave-valor.
    Mantiene TODA la lógica original de detección de polígonos y placeholders.
    """
    params = {}
    grain_defs = []
    reading_grains = False
    grains_to_read = 0

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                raw_line = line.strip()
                line = raw_line.split('#')[0].strip() # Quitar comentarios
                if not line: continue

                # 1. Detectar Bloque de Granos (no tiene ':', son números en fila)
                if reading_grains and grains_to_read > 0:
                    # Formato: [noGranos radio nLados dens fric rest]
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            g_def = {
                                'count': int(parts[0]),
                                'radius': float(parts[1]),
                                'sides': int(parts[2]), # 1=Disco, >1=Poligono
                                'friction': float(parts[4])
                            }
                            grain_defs.append(g_def)
                            grains_to_read -= 1
                        except ValueError:
                            pass # Saltar lineas malformadas
                    if grains_to_read == 0:
                        reading_grains = False
                    continue

                # 2. Detectar Clave : Valor
                if ':' in line:
                    parts = line.split(':')
                    key = parts[0].strip()
                    val_str = parts[1].strip()
                    
                    # Limpiar placeholders si existen (ej: @RHOLE@)
                    # Si detecta un @, descarta el archivo (es un template, no una simulación)
                    if '@' in val_str:
                        return None 

                    # Convertir a numero de forma segura (int o float)
                    try:
                        if '.' in val_str or 'e' in val_str.lower():
                            val = float(val_str)
                        else:
                            val = int(val_str)
                    except ValueError:
                        val = val_str # Queda como texto (T/F, nombres)
                    
                    params[key] = val

                    # Activar lectura de granos si encontramos la llave exacta
                    if key == 'noTipoGranos':
                        reading_grains = True
                        grains_to_read = int(val)

        # --- Lógica de Clasificación de Sistema ---
        if not grain_defs:
            return None # Archivo inválido o sin granos definidos

        # Determinar tipo de sistema según los lados de las partículas
        sides = [g['sides'] for g in grain_defs]
        if all(s == 1 for s in sides):
            sys_type = "Discos"
        elif all(s > 1 for s in sides):
            sys_type = "Poligonos"
        else:
            sys_type = "Mezcla"
        
        # Guardar info resumida para el DataFrame
        params['system_type'] = sys_type
        params['grain_json'] = json.dumps(grain_defs)
        params['total_particles'] = sum(g['count'] for g in grain_defs)
        
        return params

    except Exception as e:
        # En caso de error de lectura, devolvemos None para no romper el loop
        return None

def generate_hash(params):
    """Genera ID único basado en física (ignora tiradas y semillas)"""
    # Claves a ignorar para que TIRADA1, 2 y 3 tengan el mismo Hash si la física es igual
    ignore = ['RandomSeed', 'dirID', 'preFrameFile', 'fluxFile', 'veFile', 'path', 'tirada']
    clean = {k: v for k, v in params.items() if k not in ignore}
    s = json.dumps(clean, sort_keys=True)
    return hashlib.md5(s.encode()).hexdigest()[:8]

def main(base_dir=ROOT_DIR):
    """
    Función principal que escanea el directorio y genera el master_sim_index.csv.
    """
    print(f"Escaneando {base_dir} ...")
    data = []
    
    for root, dirs, files in os.walk(base_dir):
        if "params.in" in files:
            path = os.path.join(root, "params.in")
            p = parse_params(path)
            
            if p:
                # Lógica original para detectar la Tirada según el nombre de la carpeta
                if "TIRADA1" in root: t = 1
                elif "TIRADA2" in root: t = 2
                elif "TIRADA3" in root: t = 3
                else: t = 0
                
                p['tirada'] = t
                p['path'] = root
                p['sim_hash'] = generate_hash(p)
                data.append(p)

    if not data:
        print("No se encontraron simulaciones válidas.")
        return

    df = pd.DataFrame(data)
    
    # Reordenar columnas visualmente importantes (Lógica Original)
    first_cols = ['sim_hash', 'tirada', 'system_type', 'Radio_salida', 'Radio_silo', 'path']
    cols = first_cols + [c for c in df.columns if c not in first_cols]
    df = df[cols]
    
    csv_name = "../master_sim_index.csv"
    df.to_csv(csv_name, index=False)
    
    # Resumen final por consola
    print(f"\n--- ÉXITO ---")
    print(f"Base de datos generada: {csv_name}")
    print(f"Simulaciones encontradas: {len(df)}")
    print(f"Grupos físicos únicos: {df['sim_hash'].nunique()}")
    print("\nEjemplo de datos indexados:")
    print(df[['sim_hash', 'system_type', 'Radio_salida', 'tirada']].head())

# El bloque de seguridad: permite que el script se use solo o sea importado
if __name__ == "__main__":
    main()