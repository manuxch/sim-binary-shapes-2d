import pandas as pd
import numpy as np
import os
import glob
import re
import json
from multiprocessing import Pool, cpu_count

DT_THRESHOLD = 0.5       # s sin granos que cortan una avalancha (BLOCKAGE_THRESHOLD del simulador)
T_ESPERA_ATASCO = 5.0    # tEsperaAtasco por defecto: s de detencion antes de guardar atasco_XXXXX.xy y desatascar
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


def parse_t_espera(sim_path, default=T_ESPERA_ATASCO):
    """tEsperaAtasco de params.in (s), o el valor por defecto."""
    try:
        with open(os.path.join(sim_path, "params.in")) as f:
            for line in f:
                if line.strip().startswith('tEsperaAtasco:'):
                    return float(line.split(':')[1].split('#')[0])
    except Exception:
        pass
    return default


def contar_atascos_en_disco(sim_path, dir_id=''):
    """Cantidad de snapshots atasco_XXXXX.xy (sin los de contactos)."""
    carpetas = [os.path.join(sim_path, f"frames_{dir_id}")] if dir_id != '' else []
    carpetas += sorted(glob.glob(os.path.join(sim_path, "frames_*")))
    for d in carpetas:
        if os.path.isdir(d):
            return len([f for f in os.listdir(d)
                        if f.startswith('atasco_') and f.endswith('.xy') and not f.startswith('atasco_contacts_')])
    return 0


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
                        events.append((float(p[2]), int(p[1])))

            if events:
                events.sort()
                # 1) Rachas de descarga: se corta cuando pasan > DT_THRESHOLD sin granos
                #    (con TODOS los granos, chicos incluidos, igual que el simulador).
                rachas = []
                t0, t_ult, big, tot = events[0][0], events[0][0], 0, 0
                for t, tipo in events:
                    if t - t_ult > DT_THRESHOLD:
                        rachas.append((t0, t_ult, big, tot))
                        t0, big, tot = t, 0, 0
                    t_ult = t
                    tot += 1
                    big += (tipo == target_id)
                rachas.append((t0, t_ult, big, tot))

                # 2) Atascos guardados en el hueco despues de cada racha. El simulador
                #    declara atasco a los DT_THRESHOLD s sin granos y, si siguen sin
                #    salir granos, guarda atasco_k.xy y desatasca cada t_espera s:
                #    k = floor((hueco - DT_THRESHOLD) / t_espera). La ultima racha no
                #    tiene hueco (la simulacion termina al llegar a maxAvalanchas).
                t_espera = parse_t_espera(path)
                n_desp = []
                for i, (a0, a1, _, _) in enumerate(rachas):
                    if i + 1 < len(rachas):
                        hueco = rachas[i + 1][0] - a1
                        n_desp.append((hueco, max(0, int(np.floor((hueco - DT_THRESHOLD) / t_espera + 1e-6)))))
                    else:
                        n_desp.append((np.nan, 0))

                # 3) Numeracion de atascos: el primero del hueco es el arco que
                #    detuvo esa avalancha (los siguientes son desatascos fallidos).
                #    Solo se confia si el total coincide con los atasco_*.xy en disco.
                n_pred = sum(n for _, n in n_desp)
                n_disco = contar_atascos_en_disco(path, dir_id)
                coincide = (n_pred == n_disco)
                if not coincide:
                    print(f"[aviso] {s_hash}: {n_pred} atascos predichos desde flx.dat vs {n_disco} "
                          f"atasco_*.xy en disco -> no se emparejan avalanchas con arcos en esta simulacion")
                contador = 0
                for (a0, a1, big, tot), (hueco, n) in zip(rachas, n_desp):
                    atasco_id = contador + 1 if (n > 0 and coincide) else np.nan
                    contador += n
                    if big > 0:
                        avalanchas.append({
                            'sim_hash': s_hash,
                            'config_hash': config_hash,
                            'tirada': sim_row['tirada'],
                            'duracion': a1 - a0,
                            'tamano_big': big,
                            'total_mix': tot,
                            'radio_salida': sim_row.get('Radio_salida', np.nan),
                            't_inicio': a0,
                            't_fin': a1,
                            'hueco_despues': hueco,
                            'n_atascos_despues': n,
                            'atasco_id': atasco_id,
                            'emparejado_ok': coincide,
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
