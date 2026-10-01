import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as pltPolygon
import matplotlib as mpl
import os
import glob

# =============================================================================
# CONFIGURACIÓN VISUAL
# =============================================================================
mpl.use('Agg') 
mpl.rcParams['svg.fonttype'] = 'none'

ESCALA_GROSOR_FUERZA = 0.8  
NOMBRE_COLORMAP = 'inferno' 

# =============================================================================
# FUNCIONES DE PARSEO Y DETECCIÓN
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
            else: # POLÍGONO / CUADRADO
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = np.mean(coords, axis=0)
                particles[pid] = {'pos': tuple(center), 'coords': coords, 'type': int(p[-1]), 'shape': 'Poligono'}
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
def graficar_arco_y_fuerzas(sim_folder, jam_id):
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

    valid_c = contacts[(contacts['id_a'] >= 0) & (contacts['id_b'] >= 0)].copy()
    valid_c['pair_a'] = np.minimum(valid_c['id_a'], valid_c['id_b'])
    valid_c['pair_b'] = np.maximum(valid_c['id_a'], valid_c['id_b'])
    
    grouped_contacts = valid_c.groupby(['pair_a', 'pair_b']).agg({
        'px': 'mean',
        'py': 'mean',
        'f_norm': 'sum'
    }).reset_index()

    # NUEVO: Crear diccionario de puntos de contacto para trazar el arco después
    dict_contactos = {}
    for _, row in grouped_contacts.iterrows():
        dict_contactos[(int(row['pair_a']), int(row['pair_b']))] = (row['px'], row['py'])

    # Construir Grafo
    G = nx.Graph()
    for pid, attr in particles.items(): G.add_node(pid, **attr)
    
    for _, row in grouped_contacts.iterrows():
        u, v = int(row['pair_a']), int(row['pair_b'])
        if u in particles and v in particles:
            y_max = max(particles[u]['pos'][1], particles[v]['pos'][1])
            costo = 10.0 ** y_max 
            G.add_edge(u, v, weight=row['f_norm'], costo_arco=costo)

    arco_path = detectar_arco_primario(G, particles, params)

    y_coords = [p['pos'][1] for p in particles.values()]
    y_max_plot = max(y_coords) + 2  
    y_min_plot = -2                 
    
    ancho_silo = r_silo * 2
    alto_silo = y_max_plot - y_min_plot
    ratio = alto_silo / ancho_silo
    fig, ax = plt.subplots(figsize=(10, 10 * ratio))

    # 1. Dibujar Partículas (Fondo)
    for pid, p in particles.items():
        if p['shape'] == 'Disco':
            ax.add_patch(Circle(p['pos'], p['r'], color='none', ec='#CCCCCC', lw=0.3, zorder=1))
        else:
            ax.add_patch(pltPolygon(p['coords'], color='none', ec='#CCCCCC', lw=0.3, zorder=1))

    # 2. Dibujar Arco Detectado (Resaltado)
    if arco_path:
        for pid in arco_path:
            p = particles[pid]
            c = 'orange' if p['type'] == 0 else 'lightgreen'
            if p['shape'] == 'Disco':
                ax.add_patch(Circle(p['pos'], p['r'], color=c, alpha=0.5, ec='blue', lw=2, zorder=2))
            else:
                ax.add_patch(pltPolygon(p['coords'], color=c, alpha=0.5, ec='blue', lw=2, zorder=2))
        
        # -------------------------------------------------------------
        # NUEVO: Trazar la línea del arco cruzando por los puntos de contacto
        # -------------------------------------------------------------
        arch_x, arch_y = [], []
        # Agregamos el primer centro
        arch_x.append(particles[arco_path[0]]['pos'][0])
        arch_y.append(particles[arco_path[0]]['pos'][1])
        
        for i in range(len(arco_path) - 1):
            u, v = arco_path[i], arco_path[i+1]
            pair = (min(u, v), max(u, v))
            
            # Buscamos dónde fue el punto de contacto entre estas dos
            if pair in dict_contactos:
                px, py = dict_contactos[pair]
                arch_x.append(px)
                arch_y.append(py)
                
            # Agregamos el centro de la siguiente partícula
            arch_x.append(particles[v]['pos'][0])
            arch_y.append(particles[v]['pos'][1])
            
        # Dibujamos la línea azul principal quebrada
        ax.plot(arch_x, arch_y, color='blue', lw=3.5, zorder=5, alpha=0.6, solid_capstyle='round')
        
        # Agregamos un marcador redondo SOLO en los centros (queda más prolijo)
        cx = [particles[pid]['pos'][0] for pid in arco_path]
        cy = [particles[pid]['pos'][1] for pid in arco_path]
        ax.scatter(cx, cy, color='blue', s=40, zorder=6)

    # 3. Dibujar Fuerzas (también pasando por el punto de contacto promediado)
    f_max_scale = grouped_contacts['f_norm'].quantile(0.95) if not grouped_contacts.empty else 1.0
    norm = mpl.colors.Normalize(vmin=0, vmax=f_max_scale)
    cmap = mpl.colormaps[NOMBRE_COLORMAP]

    for _, row in grouped_contacts.iterrows():
        id_a, id_b = int(row['pair_a']), int(row['pair_b'])
        if id_a in particles and id_b in particles:
            pos_a = particles[id_a]['pos']
            pos_b = particles[id_b]['pos']
            
            px, py = row['px'], row['py']
            f_val = row['f_norm']
            
            ax.plot([pos_a[0], px, pos_b[0]], [pos_a[1], py, pos_b[1]], 
                    color=cmap(norm(f_val)), 
                    lw=f_val * ESCALA_GROSOR_FUERZA, 
                    solid_capstyle='round', alpha=0.85, zorder=4)

    # 4. Dibujar Silo
    ax.plot([-r_silo, -r_silo], [0, y_max_plot], color='black', lw=2, zorder=7)
    ax.plot([r_silo, r_silo], [0, y_max_plot], color='black', lw=2, zorder=7)
    ax.plot([-r_silo, -r_salida], [0, 0], color='black', lw=4, zorder=7)
    ax.plot([r_salida, r_silo], [0, 0], color='black', lw=4, zorder=7)

    ax.set_xlim(-r_silo - 1, r_silo + 1)
    ax.set_ylim(y_min_plot, y_max_plot)
    ax.set_aspect('equal')
    ax.axis('off')

    output_path = os.path.join(frames_dir, '..', f'arco_y_fuerzas_contacto_{jam_id}.svg')
    fig.savefig(output_path, format='svg', bbox_inches='tight', transparent=False)
    plt.close(fig)
    print(f"✅ Imagen guardada con éxito en:\n   {output_path}")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
    import rutas
    CARPETA_SIMULACION = os.path.join(rutas.SIM_DATA_DIR, "BARRIDO_WIDTHS_DISK_DISK", "Chi_0p0_W_2p0")
    ID_DEL_ATASCO = "00095" 
    
    graficar_arco_y_fuerzas(CARPETA_SIMULACION, ID_DEL_ATASCO)