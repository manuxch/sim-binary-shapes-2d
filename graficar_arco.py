import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as pltPolygon
import matplotlib as mpl
import os
import glob

mpl.use('Agg') 
mpl.rcParams['svg.fonttype'] = 'none'

# =============================================================================
# FUNCIONES NECESARIAS (Que faltaban)
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
# GENERACIÓN DE IMAGEN
# =============================================================================
def graficar_arco_especifico(sim_folder, jam_id):
    frames_dir = glob.glob(os.path.join(sim_folder, "frames_*"))
    if not frames_dir: 
        print(f"Error: No se encontró carpeta 'frames_' en {sim_folder}")
        return
    frames_dir = frames_dir[0]

    xy_file = os.path.join(frames_dir, f"atasco_{jam_id}.xy")
    contacts_file = os.path.join(frames_dir, f"atasco_contacts_{jam_id}.dat")
    params_file = os.path.join(sim_folder, "params.in")

    if not os.path.exists(xy_file):
        print(f"Error: Archivo no encontrado: {xy_file}")
        return

    params = parse_params(params_file)
    particles = parse_xy(xy_file)
    r_salida = params.get('Radio_salida', 2.5)
    r_silo = params.get('Radio_silo', 10.25)

    try:
        contacts = pd.read_csv(contacts_file, sep=r'\s+', comment='#', names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'])
    except Exception: 
        print("Error: No se pudo leer el archivo de contactos.")
        return

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

    fig1, ax1 = plt.subplots(figsize=(12, 8))
    for pid, p in particles.items():
        color = 'lightgray' 
        if p['shape'] == 'Disco':
            ax1.add_patch(Circle(p['pos'], p['r'], color=color, alpha=0.4, ec='#CCCCCC', lw=0.5))
        else:
            ax1.add_patch(pltPolygon(p['coords'], color=color, alpha=0.4, ec='#CCCCCC', lw=0.5))
    if arco_path:
        for pid in arco_path:
            p = particles[pid]
            c = 'orange' if p['type'] == 0 else 'lightgreen'
            if p['shape'] == 'Disco':
                ax1.add_patch(Circle(p['pos'], p['r'], color=c, alpha=0.9, ec='blue', lw=2, zorder=5))
            else:
                ax1.add_patch(pltPolygon(p['coords'], color=c, alpha=0.9, ec='blue', lw=2, zorder=5))
        path_coords = [particles[pid]['pos'] for pid in arco_path]
        px, py = zip(*path_coords)
        ax1.plot(px, py, color='blue', lw=3, marker='o', markersize=4, zorder=6)
    ax1.axvline(-r_silo, color='k', lw=2); ax1.axvline(r_silo, color='k', lw=2)
    ax1.plot([-r_silo, -r_salida], [0, 0], 'k-', lw=4); ax1.plot([r_salida, r_silo], [0, 0], 'k-', lw=4)
    ax1.set_xlim(-r_silo - 1, r_silo + 1); ax1.set_ylim(-1, 15); ax1.set_aspect('equal')
    
    output_path = os.path.join(frames_dir, '..', f'arco_detectado_{jam_id}.svg')
    fig1.savefig(output_path, format='svg', bbox_inches='tight')
    plt.close(fig1)
    print(f"✅ Imagen guardada con éxito en:\n   {output_path}")

if __name__ == "__main__":
    # =========================================================================
    # ¡MODIFICA ESTAS VARIABLES PARA ELEGIR QUÉ GRAFICAR!
    # =========================================================================
    CARPETA_SIMULACION = "/home/juli/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0/TIRADA2/BARRIDO_2D_DISK_SQUARE/Chi_0p2_W_2p0" 
    ID_DEL_ATASCO = "00001" 
    
    graficar_arco_especifico(CARPETA_SIMULACION, ID_DEL_ATASCO)