import os
import sys
import re
import numpy as np
from collections import defaultdict

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
DT_THRESHOLD = 0.5        # Segundos de silencio de la partícula PRINCIPAL para cortar.
WAIT_TIME_ATASCO = 5.0    # Penalización por atasco (size 0).
MIN_AVALANCHES = 5        # Mínimo de eventos para estadística.
REGEX_PATTERN = r"Chi_(\d+p\d+)_" 

# NOTA: Ya no hardcodeamos TARGET_TYPE. 
# El código decidirá cuál es el target basándose en el radio mayor.

# ==========================================
# 1. DETECCIÓN AUTOMÁTICA DE TIPOS
# ==========================================
def get_particle_definitions(folder_path):
    """
    Lee params.in para identificar qué ID corresponde a la partícula GRANDE (Target)
    y cuál a la PEQUEÑA (Intruder).
    
    Asume que el orden de aparición en params.in define el ID (0, 1, etc).
    Retorna: (target_id, n_big, n_small)
    """
    params_path = os.path.join(folder_path, "params.in")
    if not os.path.exists(params_path): return None, 0, 0
    
    particles_found = [] # Lista de tuplas: (ID, Radio, Cantidad)
    
    try:
        with open(params_path, 'r') as f:
            lines = f.readlines()

        start_index = -1
        for i, line in enumerate(lines):
            if "noTipoGranos" in line:
                start_index = i + 1; break
        
        if start_index == -1: return None, 0, 0

        current_id = 0
        current_idx = start_index
        
        while current_idx < len(lines):
            parts = lines[current_idx].strip().split()
            # Buscamos líneas con formato: Cantidad Radio ...
            if len(parts) >= 2:
                try:
                    count = int(parts[0])
                    radius = float(parts[1])
                    particles_found.append({'id': current_id, 'r': radius, 'n': count})
                    current_id += 1
                except: pass
            
            # Si ya leímos 2 tipos (o se acabó el bloque), paramos
            # Ajusta esto si tu params.in tiene formato distinto
            if len(lines[current_idx].strip()) == 0 and len(particles_found) > 0: break
            current_idx += 1

        if not particles_found: return None, 0, 0
        
        # LÓGICA DE DECISIÓN:
        # Ordenamos por RADIO descendente. El mayor radio es el TARGET.
        particles_found.sort(key=lambda x: x['r'], reverse=True)
        
        target_info = particles_found[0]
        target_id = target_info['id']
        n_big = target_info['n']
        
        n_small = 0
        if len(particles_found) > 1:
            n_small = particles_found[1]['n']
            
        return target_id, n_big, n_small

    except Exception as e:
        print(f"Error leyendo params.in: {e}")
        return None, 0, 0

# ==========================================
# 2. LECTURA DE FLUJO
# ==========================================
def load_data_with_types(filename):
    """
    Carga flujo completo: [(tiempo, tipo), ...]
    """
    data = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.startswith('#'): continue
                parts = line.split()
                if len(parts) < 3: continue
                try:
                    p_type = int(parts[1])
                    p_time = float(parts[2])
                    data.append((p_time, p_type))
                except ValueError: continue
    except: return []
    
    data.sort(key=lambda x: x[0])
    return data

# ==========================================
# 3. ANÁLISIS DE AVALANCHAS (CORREGIDO)
# ==========================================
def get_corrected_avalanche_stats(data, target_id, dt_thresh):
    """
    Calcula avalanchas IGNORANDO partículas que no sean target_id para el corte de tiempo.
    Esto evita que intrusos pequeños unan avalanchas grandes artificialmente.
    """
    if not data: return [], []
    
    sizes = []
    durations = []
    
    # Buscamos la primera partícula TARGET para inicializar relojes
    first_target_time = None
    for t, p_type in data:
        if p_type == target_id:
            first_target_time = t
            break
            
    if first_target_time is None: return [], []

    # Inicialización
    start_time = first_target_time
    last_target_time = first_target_time
    current_count = 0
    
    for t_curr, type_curr in data:
        
        # Solo nos importa si es la partícula PRINCIPAL (Big)
        if type_curr == target_id:
            
            # Calculamos silencio respecto al ÚLTIMO GRANDE que salió
            dt = t_curr - last_target_time
            
            # Chequeo de corte
            if dt > dt_thresh:
                if current_count > 0:
                    sizes.append(current_count)
                    durations.append(last_target_time - start_time)
                
                # Nueva avalancha
                current_count = 1
                start_time = t_curr
                last_target_time = t_curr
            else:
                # Continuamos acumulando
                current_count += 1
                last_target_time = t_curr
        
        else:
            # Es un intruso (pequeño/cuadrado chico).
            # NO reiniciamos el reloj (dt).
            # NO sumamos al tamaño (queremos size de la matriz principal).
            pass

    # Guardar última
    if current_count > 0:
        sizes.append(current_count)
        durations.append(last_target_time - start_time)
    
    return sizes, durations

# ==========================================
# 4. CEROS EXPLÍCITOS (C++)
# ==========================================
def count_explicit_zeros(folder_path, folder_name):
    csv_filename = f"{folder_name}_avalanche_data.csv"
    csv_path = os.path.join(folder_path, csv_filename)
    if not os.path.exists(csv_path): return 0
    zeros = 0
    try:
        with open(csv_path, 'r') as f:
            for line in f:
                if "nparticles" in line or line.startswith("#"): continue
                parts = line.replace(',', ' ').split()
                if len(parts) >= 4 and int(parts[-1]) == 0:
                    zeros += 1
    except: pass
    return zeros

# ==========================================
# MAIN
# ==========================================
def parse_chi(folder_name):
    match = re.search(REGEX_PATTERN, folder_name)
    return float(match.group(1).replace('p', '.')) if match else None

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 analyze_universal.py <RUTA_BASE>")
        sys.exit(1)

    base_root = sys.argv[1]
    # Estructura: data[BARRIDO][CHI]
    data_store = defaultdict(lambda: defaultdict(lambda: {'sizes': [], 'durations': [], 'n_big': 0, 'n_small': 0}))

    print(f"--- Iniciando análisis Universal (Detectando radios...) ---")
    
    tiradas = [d for d in os.listdir(base_root) if os.path.isdir(os.path.join(base_root, d)) and "TIRADA" in d.upper()]
    if not tiradas: tiradas = ["."]
    tiradas.sort()

    for tirada in tiradas:
        tirada_path = os.path.join(base_root, tirada)
        barridos = [d for d in os.listdir(tirada_path) if os.path.isdir(os.path.join(tirada_path, d)) and "BARRIDO" in d.upper()]

        for barrido in barridos:
            barrido_path = os.path.join(tirada_path, barrido)
            chi_folders = [d for d in os.listdir(barrido_path) if os.path.isdir(os.path.join(barrido_path, d))]

            for folder in chi_folders:
                chi = parse_chi(folder)
                if chi is None: continue
                
                full_path = os.path.join(barrido_path, folder)
                flx_path = os.path.join(full_path, "flx.dat")
                
                if not os.path.exists(flx_path): continue

                # 1. DETECTAR QUIÉN ES QUIÉN
                # target_id será el ID de la partícula más grande
                target_id, n_big, n_small = get_particle_definitions(full_path)
                
                if target_id is None:
                    # Fallback si falla params.in: asume 0
                    target_id = 0
                
                # 2. LEER Y PROCESAR
                raw_data = load_data_with_types(flx_path)
                
                # Aquí ocurre la magia: pasamos target_id dinámico
                real_sizes, real_durations = get_corrected_avalanche_stats(raw_data, target_id, DT_THRESHOLD)
                
                zeros = count_explicit_zeros(full_path, folder)

                # Acumular
                data_store[barrido][chi]['sizes'].extend(real_sizes + [0]*zeros)
                data_store[barrido][chi]['durations'].extend(real_durations + [WAIT_TIME_ATASCO]*zeros)
                
                if n_big > 0:
                    data_store[barrido][chi]['n_big'] = n_big
                    data_store[barrido][chi]['n_small'] = n_small

    # EXPORTAR
    print("\n--- Generando CSVs ---")
    for barrido, chi_data in data_store.items():
        results = []
        for chi, stats in chi_data.items():
            sizes = stats['sizes']
            durs = stats['durations']
            if len(sizes) < MIN_AVALANCHES: continue
            
            mean_s = np.mean(sizes)
            std_s = np.std(sizes) / np.sqrt(len(sizes))
            mean_d = np.mean(durs)
            
            results.append((chi, mean_s, std_s, mean_d, len(sizes), stats['n_big'], stats['n_small']))
        
        if not results: continue
        
        # Guardar ordenado por Chi
        res_arr = np.array(results)
        res_arr = res_arr[res_arr[:, 0].argsort()]
        
        out_name = f"{barrido}_universal_results.csv"
        np.savetxt(out_name, res_arr, delimiter=",", header="Chi,Mean_S,Err_S,Mean_T,N_Events,N_Big,N_Small", comments='', fmt="%.4f")
        print(f"Guardado: {out_name}")

if __name__ == "__main__":
    main()