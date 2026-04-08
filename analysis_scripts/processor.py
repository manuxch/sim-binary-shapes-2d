import pandas as pd
import numpy as np
import os
import glob
import re
import json
from multiprocessing import Pool, cpu_count

# ==========================================
# CONFIGURACIÓN FÍSICA Y DE GRILLA
# ==========================================
# Estos parámetros aseguran que la estadística sea físicamente representativa
DT_THRESHOLD = 0.5      # Tiempo de silencio para definir fin de avalancha
JUMP_THRESHOLD = 15.0   # Filtro para ignorar partículas reinyectadas al techo
X_LIMS, Y_LIMS = [-10.25, 10.25], [0, 120.0] # Límites del silo
# 50x150: La celda (~0.4) es mayor que el aditivo (~0.3), eliminando el ruido
GRID_NX, GRID_NY = 50, 150  
TIME_STEP = 0.001       # Paso de tiempo de integración

# Carpetas de salida según tu estructura
PREPRO_DIR = "0_mapa_prepro"
DATA_DIR = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data"

def get_target_info(sim_row):
    """Identifica el ID del tipo de partícula con el radio máximo (Discos Grandes)"""
    try:
        grains = json.loads(sim_row['grain_json'])
        radios = [float(g['radius']) for g in grains]
        return int(np.argmax(radios))
    except: return 0

def get_frame_data(filepath):
    """
    Lee archivos .xy. Maneja discos (n=1) y polígonos (promediando vértices)
    para obtener el centro de masa de cada partícula.
    """
    particles = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                p = line.split()
                if not p or int(p[0]) < 0: continue
                gid, n_lados, ptype = int(p[0]), int(p[1]), int(p[-1])
                # Lógica original: Discos vs Polígonos
                if n_lados == 1: 
                    x, y = float(p[2]), float(p[3])
                else:
                    coords = [float(val) for val in p[2:-1]]
                    x, y = sum(coords[::2])/n_lados, sum(coords[1::2])/n_lados
                particles.append([gid, x, y, ptype])
        return np.array(particles)
    except: return None

def process_everything(sim_row):
    """
    Procesa una simulación completa: genera estadística de avalanchas 
    y mapas de densidad/velocidad promediados en el tiempo.
    """
    try:
        path, s_hash, dir_id = sim_row['path'], sim_row['sim_hash'], sim_row['dirID']
        target_id = get_target_info(sim_row)
        save_freq = sim_row['saveFrameFreq']
        delta_t_frames = TIME_STEP * save_freq
        
        # --- 1. ESTADÍSTICA DE FLUJO (AVALANCHAS) ---
        # Busca flx.dat en la raíz o en la subcarpeta de frames
        ruta_flux = os.path.join(path, "flx.dat")
        if not os.path.exists(ruta_flux):
            ruta_flux = os.path.join(path, f"frames_{dir_id}", "flx.dat")

        avalanchas = []
        if os.path.exists(ruta_flux):
            events = []
            with open(ruta_flux, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip(): continue
                    p = line.split()
                    if len(p) >= 3: events.append({'t': float(p[2]), 'type': int(p[1])})
            
            if events:
                events.sort(key=lambda x: x['t'])
                start_t, last_any_t = events[0]['t'], events[0]['t']
                count_big, count_total = 0, 0
                for ev in events:
                    # Detecta el fin de una avalancha por silencio prolongado
                    if (ev['t'] - last_any_t) > DT_THRESHOLD:
                        if count_big > 0:
                            avalanchas.append({'sim_hash': s_hash, 'tirada': sim_row['tirada'], 
                                             'duracion': last_any_t - start_t, 'tamano_big': count_big, 
                                             'total_mix': count_total, 'radio_salida': sim_row['Radio_salida']})
                        start_t, count_big, count_total = ev['t'], 0, 0
                    last_any_t, count_total = ev['t'], count_total + 1
                    if ev['type'] == target_id: count_big += 1
                # Captura la última avalancha antes del fin del archivo
                if count_big > 0: 
                    avalanchas.append({'sim_hash': s_hash, 'tirada': sim_row['tirada'], 
                                     'duracion': last_any_t - start_t, 'tamano_big': count_big, 
                                     'total_mix': count_total, 'radio_salida': sim_row['Radio_salida']})

        # --- 2. MAPAS DE DENSIDAD Y VELOCIDAD (NPZ) ---
        frames_dir = os.path.join(path, f"frames_{dir_id}")
        # Ordena archivos numéricamente para un cálculo de velocidad correcto
        files = sorted(glob.glob(os.path.join(frames_dir, "*.xy")), 
                       key=lambda x: int(''.join(filter(str.isdigit, os.path.basename(x)))))
        
        # 6 capas: d0, d1 (densidad), vx0, vy0, vx1, vy1 (velocidades)
        heatmaps = np.zeros((6, GRID_NY, GRID_NX))
        prev_pos = {}
        
        if files:
            for f_path in files:
                data = get_frame_data(f_path)
                if data is None or data.size == 0: continue
                curr_pos = {}
                for p in data:
                    gid, x, y, ptype = int(p[0]), p[1], p[2], int(p[3])
                    curr_pos[gid] = (x, y)
                    # Mapeo a la grilla discreta
                    ix = int((x - X_LIMS[0]) / (X_LIMS[1] - X_LIMS[0]) * (GRID_NX-1))
                    iy = int((y - Y_LIMS[0]) / (Y_LIMS[1] - Y_LIMS[0]) * (GRID_NY-1))
                    
                    if 0 <= ix < GRID_NX and 0 <= iy < GRID_NY:
                        if ptype < 2: heatmaps[ptype, iy, ix] += 1
                        if gid in prev_pos:
                            dx, dy = x - prev_pos[gid][0], y - prev_pos[gid][1]
                            dist = np.sqrt(dx**2 + dy**2)
                            # Solo promedia si el movimiento no es un salto de reinyección
                            if dist < JUMP_THRESHOLD:
                                offset = 2 if ptype == 0 else 4
                                heatmaps[offset, iy, ix] += dx / delta_t_frames
                                heatmaps[offset+1, iy, ix] += dy / delta_t_frames
                prev_pos = curr_pos

            # Promedio temporal sobre todos los frames analizados
            heatmaps /= (len(files) + 1e-6)
            
            # Guardado en carpeta prepro
            npz_name = f"mapas_{s_hash}_T{sim_row['tirada']}.npz"
            npz_path = os.path.join(PREPRO_DIR, npz_name)
            np.savez_compressed(npz_path, 
                                d0=heatmaps[0], d1=heatmaps[1], 
                                vx0=heatmaps[2], vy0=heatmaps[3],
                                vx1=heatmaps[4], vy1=heatmaps[5])
        return avalanchas
    except Exception as e:
        print(f"Error procesando {s_hash}: {e}")
        return []

def main():
    """Ejecución centralizada con Multiprocessing"""
    # Crear carpetas de salida si no existen
    for folder in [PREPRO_DIR, DATA_DIR]:
        if not os.path.exists(folder):
            os.makedirs(folder)

    if not os.path.exists("/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"):
        print("Error: Ejecuta primero indexer.py")
        return

    df_idx = pd.read_csv("/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv")
    print(f"--- PROCESANDO {len(df_idx)} SIMULACIONES (Grilla {GRID_NX}x{GRID_NY}) ---")
    
    # Uso de Pool para paralelizar la carga de trabajo
    with Pool(cpu_count()) as pool:
        results = pool.map(process_everything, df_idx.to_dict('records'))
    
    # Consolidar todas las avalanchas de todas las simulaciones
    all_av = [item for sublist in results if sublist for item in sublist]
    if all_av:
        av_file = os.path.join(DATA_DIR, "resultados_completos_esqueleto.csv")
        pd.DataFrame(all_av).to_csv(av_file, index=False)
        print(f"Éxito: {len(all_av)} avalanchas guardadas en {av_file}")
        print(f"Mapas .npz generados en la carpeta '{PREPRO_DIR}'.")

if __name__ == "__main__":
    main()