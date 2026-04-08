import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as pltPolygon
import matplotlib as mpl
import os
import glob
import re
import multiprocessing
import concurrent.futures

# =============================================================================
# CONFIGURACIÓN VISUAL
# =============================================================================
mpl.use('Agg') 
mpl.rcParams['svg.fonttype'] = 'none'

ESCALA_GROSOR_FUERZA = 0.8  
NOMBRE_COLORMAP = 'inferno' 

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

# =============================================================================
# GENERACIÓN DE RED DE FUERZAS COMPLETA
# =============================================================================

def procesar_red_fuerzas(xy_file, params, output_dir):
    basename = os.path.basename(xy_file)
    match = re.search(r'atasco_(\d+)\.xy', basename)
    jam_id = match.group(1) if match else "unk"
    
    contacts_file = os.path.join(os.path.dirname(xy_file), f"atasco_contacts_{jam_id}.dat")
    if not os.path.exists(contacts_file): return None

    particles = parse_xy(xy_file)
    if not particles: return None

    r_salida = params.get('Radio_salida', 2.5)
    r_silo = params.get('Radio_silo', 10.25)

    # --- Cálculo de límites dinámicos ---
    y_coords = [p['pos'][1] for p in particles.values()]
    y_max = max(y_coords) + 2  # Le damos un margen de 2 unidades arriba
    y_min = -2                 # Margen debajo de la salida
    
    # Ajustamos el tamaño de la figura según la altura real
    ancho_silo = r_silo * 2
    alto_silo = y_max - y_min
    ratio = alto_silo / ancho_silo
    fig_width = 8
    fig_height = fig_width * ratio

    try:
        contacts = pd.read_csv(contacts_file, sep=r'\s+', comment='#', 
                               names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'])
    except Exception: return None

    valid_contacts = contacts[(contacts['id_a'] >= 0) & (contacts['id_b'] >= 0)].copy()
    
    # Normalización de color (percentil para evitar que un outlier arruine la escala)
    f_max_scale = valid_contacts['f_norm'].quantile(0.95) if not valid_contacts.empty else 1.0
    norm = mpl.colors.Normalize(vmin=0, vmax=f_max_scale)
    cmap = mpl.colormaps[NOMBRE_COLORMAP]

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # 1. Partículas (Fondo tenue)
    for pid, p in particles.items():
        if p['shape'] == 'Disco':
            ax.add_patch(Circle(p['pos'], p['r'], color='none', ec='#EAEAEA', lw=0.2, zorder=1))
        else:
            ax.add_patch(pltPolygon(p['coords'], color='none', ec='#EAEAEA', lw=0.2, zorder=1))

    # 2. Red de Fuerzas (Cadenas)
    for _, row in valid_contacts.iterrows():
        id_a, id_b = int(row['id_a']), int(row['id_b'])
        if id_a in particles and id_b in particles:
            pos_a = particles[id_a]['pos']
            pos_b = particles[id_b]['pos']
            f_val = row['f_norm']
            
            ax.plot([pos_a[0], pos_b[0]], [pos_a[1], pos_b[1]], 
                    color=cmap(norm(f_val)), 
                    lw=f_val * ESCALA_GROSOR_FUERZA, 
                    solid_capstyle='round', alpha=0.8, zorder=2)

    # 3. Dibujo de la estructura del Silo (Paredes y Fondo)
    # Paredes laterales hasta la altura máxima
    ax.plot([-r_silo, -r_silo], [0, y_max], color='black', lw=2, zorder=3)
    ax.plot([r_silo, r_silo], [0, y_max], color='black', lw=2, zorder=3)
    # Suelo (Hopper/Base)
    ax.plot([-r_silo, -r_salida], [0, 0], color='black', lw=4, zorder=3)
    ax.plot([r_salida, r_silo], [0, 0], color='black', lw=4, zorder=3)

    # Ajustes finales de cámara
    ax.set_xlim(-r_silo - 1, r_silo + 1)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect('equal')
    ax.axis('off')

    # Guardado
    output_path = os.path.join(output_dir, f'red_fuerzas_completa_{jam_id}.svg')
    fig.savefig(output_path, format='svg', bbox_inches='tight', transparent=True)
    plt.close(fig)
    return jam_id




# =============================================================================
# BUCLE PRINCIPAL
# =============================================================================

def main():
    # CAMBIA ESTA RUTA A TU RUTA REAL
    base_folder = "/home/juli/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0/TIRADA2/BARRIDO_2D_DISK_PENTAGON"
    
    if not os.path.exists(base_folder):
        print(f"Error: No se encuentra la carpeta {base_folder}")
        return

    sims = sorted([d for d in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, d))])
    max_workers = max(1, multiprocessing.cpu_count() - 2)

    for sim_name in sims:
        print(f"Procesando red de fuerzas en: {sim_name}")
        sim_path = os.path.join(base_folder, sim_name)
        params = parse_params(os.path.join(sim_path, "params.in"))
        
        frames_dir = glob.glob(os.path.join(sim_path, "frames_*"))
        if not frames_dir: continue
        frames_dir = frames_dir[0]
        
        xy_files = sorted(glob.glob(os.path.join(frames_dir, "atasco_*.xy")))
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(procesar_red_fuerzas, xy_f, params, frames_dir) for xy_f in xy_files]
            for _ in concurrent.futures.as_completed(futures):
                pass 

if __name__ == "__main__":
    main()