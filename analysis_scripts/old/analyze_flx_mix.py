import os
import sys
import re
import numpy as np
import csv
from collections import defaultdict

# ==========================================
# CONFIGURACIÓN
# ==========================================
DT_THRESHOLD = 0.5        # Umbral de corte (segundos)
TARGET_TYPE = 0       # "all", 0, o 1
MIN_AVALANCHES = 5        # Mínimo de avalanchas totales para validar el punto
# El nombre del archivo de salida será dinámico según el tipo de barrido (ej: BARRIDO_2D_DISK_results.csv)

# Tiempo de espera del atasco en C++
WAIT_TIME_ATASCO = 5.0    

# Umbral de radio para distinguir Big vs Small en params.in
RADIUS_THRESHOLD = 0.3
REGEX_PATTERN = r"Chi_(\d+p\d+)_" 

# ==========================================
# 1. LECTURA DE PARAMS.IN (Metadata)
# ==========================================
def get_particle_counts_from_params(folder_path):
    params_path = os.path.join(folder_path, "params.in")
    if not os.path.exists(params_path): return 0, 0
    
    n_big = 0; n_small = 0
    try:
        with open(params_path, 'r') as f:
            lines = f.readlines()

        start_index = -1
        for i, line in enumerate(lines):
            if "noTipoGranos" in line:
                start_index = i + 1; break
        
        if start_index == -1: return 0, 0

        particles_found = []
        current_idx = start_index
        while current_idx < len(lines):
            parts = lines[current_idx].strip().split()
            if len(parts) >= 2:
                try:
                    count = int(parts[0])
                    radius = float(parts[1])
                    particles_found.append((radius, count))
                except: pass
            if len(particles_found) >= 2: break
            current_idx += 1

        if not particles_found: return 0, 0
        particles_found.sort(key=lambda x: x[0], reverse=True)

        if len(particles_found) == 2:
            n_big = particles_found[0][1]
            n_small = particles_found[1][1]
        elif len(particles_found) == 1:
            if particles_found[0][0] > RADIUS_THRESHOLD:
                n_big = particles_found[0][1]
            else:
                n_small = particles_found[0][1]
    except: return 0, 0
    return n_big, n_small

# ==========================================
# 2. ANÁLISIS DE FLX.DAT (Avalanchas Reales)
# ==========================================
def load_and_filter_data(filename, target_type):
    times = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                if line.startswith('#'): continue
                parts = line.split()
                if len(parts) < 3: continue 
                p_type = int(parts[1])
                p_time = float(parts[2])
                if target_type == "all" or p_type == target_type:
                    times.append(p_time)
    except: return np.array([])
    return np.array(times)

def get_real_avalanche_stats(times, dt_thresh):
    if len(times) == 0: return [], []
    sizes, durations = [], []
    start_time = times[0]; count = 1; last_time = times[0]
    
    for t in times[1:]:
        dt = t - last_time
        if dt > dt_thresh:
            sizes.append(count)
            durations.append(last_time - start_time)
            start_time = t; count = 1
        else:
            count += 1
        last_time = t
    sizes.append(count)
    durations.append(last_time - start_time)
    return sizes, durations

# ==========================================
# 3. LÓGICA DE CEROS (CORREGIDA: Sucesivos)
# ==========================================
def count_zeros_sequence_from_cpp(folder_path, folder_name):
    csv_filename = f"{folder_name}_avalanche_data.csv"
    csv_path = os.path.join(folder_path, csv_filename)
    
    if not os.path.exists(csv_path): return 0
    
    n_particles_list = []
    try:
        with open(csv_path, 'r') as f:
            for line in f:
                if "nparticles" in line or line.startswith("#"): continue
                parts = line.replace(',', ' ').split()
                if len(parts) < 4: continue
                val = int(parts[-1])
                n_particles_list.append(val)
    except: return 0
    
    failed_attempts = 0
    for i in range(len(n_particles_list) - 1):
        current_n = n_particles_list[i]
        next_n = n_particles_list[i+1]
        if current_n == 0 and next_n == 0:
            failed_attempts += 1
    return failed_attempts

# ==========================================
# HELPER: PARSE CHI
# ==========================================
def parse_chi_from_folder(folder_name):
    match = re.search(REGEX_PATTERN, folder_name)
    if match: return float(match.group(1).replace('p', '.'))
    return None

# ==========================================
# MAIN (MODIFICADO PARA ESTRUCTURA ANIDADA)
# ==========================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 analyze_combined.py <RUTA_BASE_CON_TIRADAS>")
        print("Ejemplo: python3 analyze_combined.py ./Datos_Simulacion")
        sys.exit(1)

    base_root = sys.argv[1]

    # Estructura de datos para acumular:
    # data_store[NOMBRE_BARRIDO][VALOR_CHI] = { 'sizes': [], 'durations': [], 'n_big': 0, 'n_small': 0 }
    data_store = defaultdict(lambda: defaultdict(lambda: {'sizes': [], 'durations': [], 'n_big': 0, 'n_small': 0}))

    print(f"--- Iniciando análisis COMBINADO de Tiradas ---")
    
    # 1. Buscar carpetas TIRADA*
    tiradas = [d for d in os.listdir(base_root) if os.path.isdir(os.path.join(base_root, d)) and "TIRADA" in d.upper()]
    
    if not tiradas:
        print("No se encontraron carpetas con nombre 'TIRADA' en la ruta base.")
        # Fallback: Si no hay tiradas, quizás estamos dentro de una tirada. Intentamos procesar como estructura simple.
        tiradas = ["."] 

    tiradas.sort()

    for tirada in tiradas:
        tirada_path = os.path.join(base_root, tirada)
        print(f"--> Procesando: {tirada}")

        # 2. Buscar carpetas de BARRIDO (Geometry Types) dentro de la tirada
        # Asumimos que son carpetas que contienen "BARRIDO"
        barridos = [d for d in os.listdir(tirada_path) if os.path.isdir(os.path.join(tirada_path, d)) and "BARRIDO" in d.upper()]

        for barrido_name in barridos:
            barrido_path = os.path.join(tirada_path, barrido_name)
            
            # 3. Buscar carpetas de CHI dentro del barrido
            chi_folders = [d for d in os.listdir(barrido_path) if os.path.isdir(os.path.join(barrido_path, d))]

            for folder in chi_folders:
                chi = parse_chi_from_folder(folder)
                if chi is None: continue # Saltar si no cumple el patrón de nombre

                full_folder_path = os.path.join(barrido_path, folder)
                flx_path = os.path.join(full_folder_path, "flx.dat")

                # Si no hay flx.dat, pasamos
                if not os.path.exists(flx_path): continue

                # A. Obtener Avalanchas Reales
                times = load_and_filter_data(flx_path, TARGET_TYPE)
                real_sizes, real_durations = get_real_avalanche_stats(times, DT_THRESHOLD)

                # B. Obtener Fallos (Ceros sucesivos)
                zeros_count = count_zeros_sequence_from_cpp(full_folder_path, folder)

                # C. Combinar datos de esta carpeta específica
                current_sizes = real_sizes + [0] * zeros_count
                current_durations = real_durations + [WAIT_TIME_ATASCO] * zeros_count

                # D. Leer metadatos (solo si no los tenemos o para confirmar)
                n_big, n_small = get_particle_counts_from_params(full_folder_path)

                # E. ACUMULAR EN EL DICCIONARIO GLOBAL
                # Usamos extend para agregar a la lista existente de otras tiradas
                data_store[barrido_name][chi]['sizes'].extend(current_sizes)
                data_store[barrido_name][chi]['durations'].extend(current_durations)
                
                # Guardamos n_big/n_small (asumimos que son iguales para el mismo Chi en todas las tiradas)
                if n_big > 0: 
                    data_store[barrido_name][chi]['n_big'] = n_big
                    data_store[barrido_name][chi]['n_small'] = n_small

    # ==========================================
    # 4. PROCESAR ACUMULADOS Y EXPORTAR
    # ==========================================
    print("\n--- Generando archivos de salida por Tipo de Barrido ---")
    
    if not data_store:
        print("No se encontraron datos válidos.")
        sys.exit()

    for barrido_name, chi_data in data_store.items():
        results = []
        
        # Iterar sobre cada Chi encontrado para este barrido
        for chi, stats in chi_data.items():
            combined_sizes = stats['sizes']
            combined_durations = stats['durations']
            total_N = len(combined_sizes)

            if total_N < MIN_AVALANCHES:
                continue

            # Calcular estadísticas sobre TODAS las tiradas juntas
            mean_s = np.mean(combined_sizes)
            # Error estándar = Desv. Estándar / Raíz(N_total)
            std_s = np.std(combined_sizes) / np.sqrt(total_N)
            mean_d = np.mean(combined_durations)

            results.append((chi, mean_s, std_s, mean_d, total_N, stats['n_big'], stats['n_small']))

        if not results:
            print(f"Saltando {barrido_name}: Sin suficientes datos.")
            continue

        # Ordenar por Chi
        results_arr = np.array(results)
        results_arr = results_arr[results_arr[:, 0].argsort()]

        # Escribir archivo CSV específico para este barrido
        output_filename = f"{barrido_name}_results_combined.csv"
        
        with open(output_filename, "w") as f:
            f.write("Chi,Mean_Avalanche_Size,Std_Error_Size,Mean_Duration,Total_Events,N_Big,N_Small\n")
            for row in results_arr:
                f.write(f"{row[0]},{row[1]:.4f},{row[2]:.4f},{row[3]:.4f},{int(row[4])},{int(row[5])},{int(row[6])}\n")
        
        print(f"[OK] Guardado: {output_filename} ({len(results)} puntos Chi)")

if __name__ == "__main__":
    main()