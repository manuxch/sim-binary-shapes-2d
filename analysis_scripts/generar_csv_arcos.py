import pandas as pd
import numpy as np
import networkx as nx
import os
import glob
import re
import multiprocessing
import concurrent.futures
import argparse

# =============================================================================
# 1. PARSEADORES
# =============================================================================
def parse_params(filename):
    params = {'Radio_silo': 10.25, 'Radio_salida': 2.5}
    try:
        with open(filename, 'r') as f:
            for line in f:
                if 'Radio_silo:' in line:
                    params['Radio_silo'] = float(line.split(':')[1].split('#')[0].strip())
                if 'Radio_salida:' in line:
                    params['Radio_salida'] = float(line.split(':')[1].split('#')[0].strip())
    except Exception: pass
    return params

def parse_xy(filename):
    particles = {}
    with open(filename, 'r') as f:
        for line in f:
            p = line.split()
            if not p: continue
            pid = int(p[0])
            n_sides = int(p[1])
            if n_sides == 1: # DISCO
                x, y, r, ptype = float(p[2]), float(p[3]), float(p[4]), int(p[5])
                particles[pid] = {'pos': (x, y), 'r': r, 'type': ptype, 'shape': 'Disco'}
            else: # CUADRADO
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = np.mean(coords, axis=0)
                particles[pid] = {'pos': tuple(center), 'coords': coords, 'type': int(p[-1]), 'shape': 'Cuadrado'}
    return particles

def obtener_radio(p_data):
    if p_data['shape'] == 'Disco': return p_data['r']
    return np.max(np.linalg.norm(p_data['coords'] - p_data['pos'], axis=1))

# =============================================================================
# 2. ALGORITMO NETWORKX (INTACTO)
# =============================================================================
def es_cimiento_estable(pid, particles, G, path, idx, r_salida):
    p = particles[pid]
    x, y = p['pos']
    r = obtener_radio(p)
    if abs(x) < (r_salida - 0.2): return False
    if (y - r) < 0.2: return True
    vecinos_arco = []
    if idx > 0: vecinos_arco.append(path[idx-1])
    if idx < len(path) - 1: vecinos_arco.append(path[idx+1])
    apoyos_inferiores = 0
    for vecino in G.neighbors(pid):
        if vecino not in vecinos_arco:
            y_vecino = particles[vecino]['pos'][1]
            if y_vecino < (y - 0.05):
                apoyos_inferiores += 1
    return apoyos_inferiores >= 2

def purgar_cimientos(path, particles, G, r_salida):
    if not path: return []
    iL = 0
    while iL < len(path) and es_cimiento_estable(path[iL], particles, G, path, iL, r_salida):
        iL += 1
    iR = len(path) - 1
    while iR >= iL and es_cimiento_estable(path[iR], particles, G, path, iR, r_salida):
        iR -= 1
    if iL > iR: return []
    return path[iL:iR+1]

def detectar_arco_primario(G, particles, params):
    r_salida = params.get('Radio_salida', 2.5)
    nleft, nright = [], []
    for pid, data in particles.items():
        r = obtener_radio(data)
        x, y = data['pos']
        if (y - r) < 0.2:
            if x < 0.0: nleft.append(pid)
            elif x > 0.0: nright.append(pid)
    mejor_arco = []
    min_costo_total = float('inf')
    for l in nleft:
        for r in nright:
            if nx.has_path(G, l, r):
                try:
                    path = nx.shortest_path(G, source=l, target=r, weight='costo_arco')
                    costo_path = sum(G[path[i]][path[i+1]]['costo_arco'] for i in range(len(path)-1))
                    if costo_path < min_costo_total:
                        min_costo_total = costo_path
                        mejor_arco = purgar_cimientos(path, particles, G, r_salida)
                except nx.NetworkXNoPath: continue
    return mejor_arco

# =============================================================================
# 3. PROCESAMIENTO (Worker)
# =============================================================================
def procesar_atasco(xy_file, params):
    basename = os.path.basename(xy_file)
    match = re.search(r'atasco_(\d+)\.xy', basename)
    jam_id = match.group(1) if match else "unk"
    
    contacts_file = os.path.join(os.path.dirname(xy_file), f"atasco_contacts_{jam_id}.dat")
    if not os.path.exists(contacts_file): return None

    particles = parse_xy(xy_file)
    r_salida = params.get('Radio_salida', 2.5)

    try:
        contacts = pd.read_csv(contacts_file, sep=r'\s+', comment='#', names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'])
    except Exception: return None

    G = nx.Graph()
    for pid, attr in particles.items(): G.add_node(pid, **attr)
    
    valid_c = contacts[(contacts['id_a'] >= 0) & (contacts['id_b'] >= 0)]
    for _, row in valid_c.iterrows():
        u, v = int(row['id_a']), int(row['id_b'])
        if u in particles and v in particles:
            y_max = max(particles[u]['pos'][1], particles[v]['pos'][1])
            costo = 10.0 ** y_max 
            if G.has_edge(u, v):
                G[u][v]['weight'] += row['f_norm']
                G[u][v]['costo_arco'] = min(costo, G[u][v].get('costo_arco', float('inf')))
            else:
                G.add_edge(u, v, weight=row['f_norm'], costo_arco=costo)

    arco_path = detectar_arco_primario(G, particles, params)
    
    n_tipo_0, n_tipo_1, altura, cm_x, cm_y = 0, 0, 0.0, 0.0, 0.0
    longitud, tortuosidad, span, aspect_ratio = 0.0, 0.0, 0.0, 0.0

    if arco_path:
        xc = np.array([particles[pid]['pos'][0] for pid in arco_path])
        yc = np.array([particles[pid]['pos'][1] for pid in arco_path])

        for pid in arco_path:
            p_type = particles[pid].get('type', -1)
            if p_type == 0: n_tipo_0 += 1
            elif p_type == 1: n_tipo_1 += 1

        if len(xc) > 1:
            altura = yc.max() - yc.min()
            cm_x, cm_y = xc.mean(), yc.mean()
            
            dx, dy = np.diff(xc), np.diff(yc)
            dist_consecutivas = np.sqrt(dx**2 + dy**2)
            longitud = np.sum(dist_consecutivas)
            
            span = abs(xc[-1] - xc[0])
            
            lextr = np.sqrt((xc[-1] - xc[0])**2 + (yc[-1] - yc[0])**2)
            if lextr > 0: tortuosidad = longitud / lextr
            
            if altura > 0: aspect_ratio = 0.5 * span / altura

    return {
        'Atasco_ID': jam_id, 
        'Total_Particulas_Arco': len(arco_path) if arco_path else 0,
        'Particulas_Tipo_0': n_tipo_0,
        'Particulas_Tipo_1': n_tipo_1,
        'Altura': round(altura, 4),
        'CM_X': round(cm_x, 4),
        'CM_Y': round(cm_y, 4),
        'Longitud': round(longitud, 4),
        'Tortuosidad': round(tortuosidad, 4),
        'Span': round(span, 4),
        'Relacion_Aspecto': round(aspect_ratio, 4),
        'Radio_Salida': r_salida
    }

# =============================================================================
# 4. INTEGRACIÓN PIPELINE (NUEVA FUNCIÓN)
# =============================================================================
def procesar_directorio(sim_path, max_workers=None):
    """
    Función diseñada para ser llamada desde main_pipeline.py.
    Procesa una única carpeta de simulación.
    """
    params_file = os.path.join(sim_path, "params.in")
    if not os.path.exists(params_file):
        return False
        
    params = parse_params(params_file)
    
    frames_dir = glob.glob(os.path.join(sim_path, "frames_*"))
    if not frames_dir: return False
    frames_dir = frames_dir[0]
    
    xy_files = sorted(glob.glob(os.path.join(frames_dir, "atasco_*.xy")))
    if not xy_files: return False

    sim_stats = []
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count() - 2)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(procesar_atasco, xy_f, params): xy_f for xy_f in xy_files}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: sim_stats.append(res)
    
    if sim_stats:
        sim_stats.sort(key=lambda x: int(x['Atasco_ID']) if str(x['Atasco_ID']).isdigit() else x['Atasco_ID'])
        # Guardamos en la carpeta de la simulación
        salida_csv = os.path.join(sim_path, "estadisticas_arcos.csv")
        pd.DataFrame(sim_stats).to_csv(salida_csv, index=False)
        return True
    return False

# =============================================================================
# MAIN LOOP (Para ejecución standalone)
# =============================================================================
def main_loop(base_folder):
    """Mantiene la funcionalidad original por si se usa desde consola"""
    if not os.path.exists(base_folder): 
        print(f"Error: La ruta {base_folder} no existe.")
        return

    sims = sorted([d for d in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, d))])
    for i, sim_name in enumerate(sims):
        print(f"[{i+1}/{len(sims)}] Procesando arcos en: {sim_name}")
        sim_path = os.path.join(base_folder, sim_name)
        procesar_directorio(sim_path)

if __name__ == "__main__":
    multiprocessing.freeze_support() 
    parser = argparse.ArgumentParser(description="Generar CSV con estadísticas de arcos.")
    parser.add_argument("-d", "--directorio", required=True, help="Ruta de la carpeta base (ej. BARRIDO_2D_DISK_SQUARE)")
    args = parser.parse_args()
    
    main_loop(args.directorio)