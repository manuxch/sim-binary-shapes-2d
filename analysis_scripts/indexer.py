import os
import pandas as pd
import hashlib
import json
import re
import numpy as np

# --- CONFIGURACIÓN ---
ROOT_DIR = "../datos_simulaciones/simulation_data/R_2.0"

def calcular_area_geometrica(r, sides):
    """Calcula el área real según la forma de la partícula."""
    if sides == 1:   # DISCO
        return np.pi * (r ** 2)
    if sides == 4:   # CUADRADO
        return 4.0 * (r ** 2) 
    if sides > 1:    # POLÍGONOS REGULARES
        return (sides * (r ** 2) * np.sin(2 * np.pi / sides)) / 2
    return np.pi * (r ** 2)

def parse_params(filepath, folder_path):
    params = {'chi': None}
    grain_defs = []
    reading_grains = False
    grains_to_read = 0

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line: continue

                if reading_grains and grains_to_read > 0:
                    parts = line.split()
                    if len(parts) >= 6:
                        grain_defs.append({
                            'radius': float(parts[1]),
                            'sides': int(parts[2])
                        })
                        grains_to_read -= 1
                    continue

                if ':' in line:
                    parts = line.split(':')
                    key_raw, val_str = parts[0].strip(), parts[1].strip()
                    if '@' in val_str: return None 

                    try:
                        val = float(val_str) if ('.' in val_str or 'e' in val_str.lower()) else int(val_str)
                    except: val = val_str
                    
                    key_norm = key_raw.lower().replace(" ", "_")
                    if key_norm in ['concentracion_aditivo', 'chi']:
                        params['chi'] = val
                    else:
                        params[key_raw] = val

                    if key_norm == 'notipogranos':
                        reading_grains, grains_to_read = True, int(val)

        # Fallback de Chi
        if params['chi'] is None:
            match = re.search(r"Chi_(\d+[p\.]\d+)", folder_path)
            params['chi'] = float(match.group(1).replace('p', '.')) if match else 0.0

        if not grain_defs: return None

        # --- Lógica de Radios y Áreas ---
        gs = sorted(grain_defs, key=lambda x: x['radius'], reverse=True)
        params['r_large'] = gs[0]['radius']
        params['area_large'] = round(calcular_area_geometrica(gs[0]['radius'], gs[0]['sides']), 4)
        
        if len(gs) >= 2:
            params['r_small'] = gs[1]['radius']
            params['r_ratio'] = round(gs[1]['radius'] / gs[0]['radius'], 2)
            
            # Cálculo de Áreas
            params['area_small'] = round(calcular_area_geometrica(gs[1]['radius'], gs[1]['sides']), 4)
            params['area_ratio'] = round(params['area_small'] / params['area_large'], 4)
            
            nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}
            n1 = nombres.get(gs[0]['sides'], "Pol") # Si el numero de lados es mayor a 5, se usa "Pol"
            n2 = nombres.get(gs[1]['sides'], "Pol")
            params['system_type'] = f"{n1}-{n2}"
        else:
            params['r_ratio'] = 1.0
            params['system_type'] = "Puro"

        params['grain_json'] = json.dumps(grain_defs)
        return params
    except Exception as e:
        # Imprime el error para debuguear si alguna carpeta falla
        print(f"Error en {folder_path}: {e}")
        return None

def generate_hash(params):
    keys = ['grain_json', 'Radio_salida', 'chi', 'Radio_silo']
    s = "|".join([str(params.get(k, "")) for k in keys])
    return hashlib.md5(s.encode()).hexdigest()[:12]

def main(base_dir=ROOT_DIR):
    print(f"Indexando en: {base_dir}")
    data = []
    for root, dirs, files in os.walk(base_dir):
        if "params.in" in files:
            p = parse_params(os.path.join(root, "params.in"), root)
            if p:
                t_match = re.search(r'TIRADA(\d+)', root, re.IGNORECASE)
                p['tirada'] = int(t_match.group(1)) if t_match else 0
                p['path'] = root
                p['sim_hash'] = generate_hash(p)
                data.append(p)

    if not data: return print("No se encontraron datos.")
    df = pd.DataFrame(data)
    cols_prioritarias = ['sim_hash', 'system_type', 'chi', 'r_ratio', 'area_ratio', 'tirada', 'path']
    existentes = [c for c in cols_prioritarias if c in df.columns]
    df = df[existentes + [c for c in df.columns if c not in existentes]]
    df.to_csv("../master_sim_index.csv", index=False)
    print(f"Éxito: {len(df)} simulaciones indexadas.")

if __name__ == "__main__":
    main()