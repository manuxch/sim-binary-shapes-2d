import pandas as pd
import numpy as np
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

def graficar_fuerza_especifica(sim_folder, jam_id):
    frames_dir = glob.glob(os.path.join(sim_folder, "frames_*"))
    if not frames_dir: 
        print("No se encontró carpeta frames_")
        return
    frames_dir = frames_dir[0]

    xy_file = os.path.join(frames_dir, f"atasco_{jam_id}.xy")
    contacts_file = os.path.join(frames_dir, f"atasco_contacts_{jam_id}.dat")
    params_file = os.path.join(sim_folder, "params.in")

    if not os.path.exists(xy_file):
        print(f"Archivo no encontrado: {xy_file}")
        return

    params = parse_params(params_file)
    particles = parse_xy(xy_file)
    if not particles: return

    r_salida = params.get('Radio_salida', 2.5)
    r_silo = params.get('Radio_silo', 10.25)

    y_coords = [p['pos'][1] for p in particles.values()]
    y_max = max(y_coords) + 2  
    y_min = -2                 
    
    ancho_silo = r_silo * 2
    alto_silo = y_max - y_min
    ratio = alto_silo / ancho_silo
    fig_width = 8
    fig_height = fig_width * ratio

    try:
        contacts = pd.read_csv(contacts_file, sep=r'\s+', comment='#', 
                               names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'])
    except Exception: 
        print("Error leyendo contactos.")
        return

    valid_contacts = contacts[(contacts['id_a'] >= 0) & (contacts['id_b'] >= 0)].copy()
    
    f_max_scale = valid_contacts['f_norm'].quantile(0.95) if not valid_contacts.empty else 1.0
    norm = mpl.colors.Normalize(vmin=0, vmax=f_max_scale)
    cmap = mpl.colormaps[NOMBRE_COLORMAP]

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    for pid, p in particles.items():
        if p['shape'] == 'Disco':
            ax.add_patch(Circle(p['pos'], p['r'], color='none', ec='#EAEAEA', lw=0.2, zorder=1))
        else:
            ax.add_patch(pltPolygon(p['coords'], color='none', ec='#EAEAEA', lw=0.2, zorder=1))

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

    ax.plot([-r_silo, -r_silo], [0, y_max], color='black', lw=2, zorder=3)
    ax.plot([r_silo, r_silo], [0, y_max], color='black', lw=2, zorder=3)
    ax.plot([-r_silo, -r_salida], [0, 0], color='black', lw=4, zorder=3)
    ax.plot([r_salida, r_silo], [0, 0], color='black', lw=4, zorder=3)

    ax.set_xlim(-r_silo - 1, r_silo + 1)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect('equal')
    ax.axis('off')

    output_path = os.path.join(frames_dir, '..', f'red_fuerzas_completa_{jam_id}.svg')
    fig.savefig(output_path, format='svg', bbox_inches='tight', transparent=True)
    plt.close(fig)
    print(f"Imagen de fuerzas guardada con éxito en: {output_path}")

if __name__ == "__main__":
    # =========================================================================
    # ¡MODIFICA ESTAS VARIABLES PARA ELEGIR QUÉ GRAFICAR!
    # =========================================================================
    CARPETA_SIMULACION = "/home/juli/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0/TIRADA2/BARRIDO_2D_DISK_TRIANGLE/Chi_0p2_W_2p0" 
    ID_DEL_ATASCO = "00028" 
    
    graficar_fuerza_especifica(CARPETA_SIMULACION, ID_DEL_ATASCO)
