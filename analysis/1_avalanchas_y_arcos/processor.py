import pandas as pd
import numpy as np
import os
import glob
import re
import json
from multiprocessing import Pool, cpu_count

DT_THRESHOLD = 0.5
JUMP_THRESHOLD = 15.0
X_LIMS, Y_LIMS = [-10.25, 10.25], [0, 120.0]
GRID_NX, GRID_NY = 50, 150
TIME_STEP = 0.001

PREPRO_DIR = "0_mapa_prepro"
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas
DATA_DIR = rutas.AVALANCHE_DIR
IDX_PATH = rutas.MASTER_INDEX


def get_target_info(sim_row):
    """Identifica el tipo de partícula grande, usando el radio máximo."""
    try:
        grains = json.loads(sim_row['grain_json'])
        radios = [float(g['radius']) for g in grains]
        return int(np.argmax(radios))
    except Exception:
        return 0


def get_frame_data(filepath):
    particles = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                p = line.split()
                if not p or int(p[0]) < 0:
                    continue
                gid, n_lados, ptype = int(p[0]), int(p[1]), int(p[-1])
                if n_lados == 1:
                    x, y = float(p[2]), float(p[3])
                else:
                    coords = [float(val) for val in p[2:-1]]
                    x, y = sum(coords[::2]) / n_lados, sum(coords[1::2]) / n_lados
                particles.append([gid, x, y, ptype])
        return np.array(particles)
    except Exception:
        return None


def process_everything(sim_row):
    """Procesa una simulación: avalanchas y, opcionalmente, mapas."""
    try:
        path = sim_row['path']
        s_hash = sim_row['sim_hash']
        config_hash = sim_row.get('config_hash', '')
        dir_id = sim_row.get('dirID', '')
        target_id = get_target_info(sim_row)

        ruta_flux = os.path.join(path, "flx.dat")
        if not os.path.exists(ruta_flux) and dir_id != '':
            ruta_flux = os.path.join(path, f"frames_{dir_id}", "flx.dat")

        avalanchas = []
        if os.path.exists(ruta_flux):
            events = []
            with open(ruta_flux, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    p = line.split()
                    if len(p) >= 3:
                        events.append({'t': float(p[2]), 'type': int(p[1])})

            if events:
                events.sort(key=lambda x: x['t'])
                start_t, last_any_t = events[0]['t'], events[0]['t']
                count_big, count_total = 0, 0

                for ev in events:
                    if (ev['t'] - last_any_t) > DT_THRESHOLD:
                        if count_big > 0:
                            avalanchas.append({
                                'sim_hash': s_hash,
                                'config_hash': config_hash,
                                'tirada': sim_row['tirada'],
                                'duracion': last_any_t - start_t,
                                'tamano_big': count_big,
                                'total_mix': count_total,
                                'radio_salida': sim_row.get('Radio_salida', np.nan),
                            })
                        start_t, count_big, count_total = ev['t'], 0, 0

                    last_any_t = ev['t']
                    count_total += 1
                    if ev['type'] == target_id:
                        count_big += 1

                if count_big > 0:
                    avalanchas.append({
                        'sim_hash': s_hash,
                        'config_hash': config_hash,
                        'tirada': sim_row['tirada'],
                        'duracion': last_any_t - start_t,
                        'tamano_big': count_big,
                        'total_mix': count_total,
                        'radio_salida': sim_row.get('Radio_salida', np.nan),
                    })

        return avalanchas

    except Exception as e:
        print(f"Error procesando {sim_row.get('sim_hash', 'sin_hash')}: {e}")
        return []


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(IDX_PATH):
        print("Error: Ejecutá primero indexer.py")
        return

    df_idx = pd.read_csv(IDX_PATH)
    print(f"--- PROCESANDO {len(df_idx)} SIMULACIONES ---")

    with Pool(cpu_count()) as pool:
        results = pool.map(process_everything, df_idx.to_dict('records'))

    all_av = [item for sublist in results if sublist for item in sublist]

    if all_av:
        av_file = os.path.join(DATA_DIR, "resultados_completos_esqueleto.csv")
        pd.DataFrame(all_av).to_csv(av_file, index=False)
        print(f"Éxito: {len(all_av)} avalanchas guardadas en {av_file}")
    else:
        print("No se encontraron avalanchas para guardar.")


if __name__ == "__main__":
    main()
