import os
import pandas as pd
import hashlib
import json
import re
import numpy as np

# --- CONFIGURACIÓN ---
ROOT_DIR = "../datos_simulaciones/simulation_data/R_2.0"
OUTPUT_CSV = "../master_sim_index.csv"

def path_val_to_float(val_str):
    if not val_str: return None
    return float(val_str.replace('p', '.'))

def calcular_area_geometrica(r, sides):
    if sides == 1: return np.pi * (r ** 2)
    if sides == 4: return 4.0 * (r ** 2) 
    if sides > 1: return (sides * (r ** 2) * np.sin(2 * np.pi / sides)) / 2
    return np.pi * (r ** 2)

def parse_params(filepath, folder_path):
    params = {
        'chi': None, 
        'w_salida': None, 
        'r_ratio': 1.0,      # Agregado por defecto
        'area_ratio': 0.1, 
        'system_type': "Puro"
    }
    grain_defs = []
    reading_grains, grains_to_read = False, 0

    # 1. Regex del Path
    chi_match = re.search(r"Chi_([\dp]+)", folder_path)
    w_match = re.search(r"_W_([\dp]+)", folder_path)
    ratio_match = re.search(r"Ratio_([\dp]+)", folder_path)

    if chi_match: params['chi'] = path_val_to_float(chi_match.group(1))
    if w_match:   params['w_salida'] = path_val_to_float(w_match.group(1))
    folder_ratio = path_val_to_float(ratio_match.group(1)) if ratio_match else None

    # 2. Leer params.in
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line: continue
                if reading_grains and grains_to_read > 0:
                    parts = line.split()
                    if len(parts) >= 6:
                        grain_defs.append({'radius': float(parts[1]), 'sides': int(parts[2])})
                        grains_to_read -= 1
                    continue
                if ':' in line:
                    parts = line.split(':')
                    key_raw, val_str = parts[0].strip(), parts[1].strip()
                    try:
                        val = float(val_str) if ('.' in val_str or 'e' in val_str.lower()) else int(val_str)
                    except: val = val_str
                    key_norm = key_raw.lower().replace(" ", "_")
                    if key_norm in ['concentracion_aditivo', 'chi'] and params['chi'] is None:
                        params['chi'] = val
                    elif key_norm in ['radio_salida', 'w_salida'] and params['w_salida'] is None:
                        params['w_salida'] = val
                    else:
                        params[key_raw] = val
                    if key_norm == 'notipogranos':
                        reading_grains, grains_to_read = True, int(val)

        # 3. Cálculos de Ratios (Crucial para tus otros scripts)
        if grain_defs:
            gs = sorted(grain_defs, key=lambda x: x['radius'], reverse=True)
            params['r_large'] = gs[0]['radius']
            params['area_large'] = round(calcular_area_geometrica(gs[0]['radius'], gs[0]['sides']), 4)
            
            if len(gs) >= 2:
                params['r_small'] = gs[1]['radius']
                # AQUÍ SE GENERA EL r_ratio QUE PIDE EL ERROR
                params['r_ratio'] = round(gs[1]['radius'] / gs[0]['radius'], 2)
                params['area_small'] = round(calcular_area_geometrica(gs[1]['radius'], gs[1]['sides']), 4)
                params['area_ratio'] = round(params['area_small'] / params['area_large'], 4)
                
                nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}
                n1, n2 = nombres.get(gs[0]['sides'], "Pol"), nombres.get(gs[1]['sides'], "Pol")
                params['system_type'] = f"{n1}-{n2}"
        elif folder_ratio is not None:
            # Si no hay granos pero hay Ratio en carpeta, asumimos que es el de área
            params['area_ratio'] = folder_ratio
            # Aproximamos r_ratio como la raíz cuadrada del area_ratio (suponiendo discos)
            params['r_ratio'] = round(np.sqrt(folder_ratio), 2)

        if params['chi'] is None: params['chi'] = 0.0
        params['grain_json'] = json.dumps(grain_defs)
        return params
    except Exception as e:
        print(f"Error: {e}"); return None

def generate_hash(params):
    keys = ['grain_json', 'w_salida', 'chi', 'Radio_silo']
    s = "|".join([str(params.get(k, "")) for k in keys])
    return hashlib.md5(s.encode()).hexdigest()[:12]

def main(base_dir=ROOT_DIR):
    print(f"--- Indexando en: {base_dir} ---")
    data = []
    for root, dirs, files in os.walk(base_dir):
        if "params.in" in files:
            p = parse_params(os.path.join(root, "params.in"), root)
            if p:
                t_match = re.search(r'TIRADA(\d+)', root, re.IGNORECASE)
                p['tirada'] = int(t_match.group(1)) if t_match else 1
                cat_match = re.search(r'(BARRIDO_[^/]+|DISK_DISK_[^/]+)', root)
                p['category'] = cat_match.group(0) if cat_match else "General"
                p['path'] = root
                p['sim_hash'] = generate_hash(p)
                data.append(p)

    if not data: return print("No hay datos.")
    df = pd.DataFrame(data)
    
    # LISTA DE COLUMNAS QUE TUS OTROS SCRIPTS ESPERAN
    cols_prioritarias = [
        'sim_hash', 'category', 'system_type', 'chi', 
        'r_ratio', 'area_ratio', 'w_salida', 'tirada', 'path'
    ]
    
    existentes = [c for c in cols_prioritarias if c in df.columns]
    df = df[existentes + [c for c in df.columns if c not in existentes]]
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"[+] Éxito: {len(df)} simulaciones indexadas.")

if __name__ == "__main__":
    main()