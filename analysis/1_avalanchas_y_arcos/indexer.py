import os
import pandas as pd
import hashlib
import json
import re
import numpy as np

# --- CONFIGURACIÓN ---
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas
ROOT_DIR = rutas.SIM_DATA_DIR
OUTPUT_CSV = rutas.MASTER_INDEX


def path_val_to_float(val_str):
    if not val_str:
        return None
    return float(str(val_str).replace('p', '.'))


def calcular_area_geometrica(r, sides=1):
    """
    El simulador normaliza las áreas de los polígonos usando el radio efectivo.
    Por consistencia con el resto del análisis, usamos siempre pi*r^2.
    """
    return np.pi * (float(r) ** 2)


def nominalizar_ratio_real(x, ndigits=3):
    """
    Redondeo nominal de respaldo para valores reales cuando NO hay Ratio_... en el path.
    Ej.: 0.0998 -> 0.1.
    """
    if x is None:
        return np.nan
    try:
        if pd.isna(x):
            return np.nan
    except TypeError:
        pass
    return round(float(x), ndigits)


def extraer_ratio_nominal_del_path(folder_path):
    """
    Extrae el valor objetivo del barrido desde nombres tipo Ratio_0p2.

    Regla central:
      - Si existe Ratio_0pX en el path, ese es el area_ratio_nominal.
      - El area_ratio calculado se conserva aparte como valor real.

    Esto evita que pentágonos/cuadrados pasen de etiquetas 0.2, 0.4, 0.6
    a valores reales como 0.116, 0.231, 0.463.
    """
    matches = re.findall(r"Ratio_([\dp]+)", folder_path)
    if not matches:
        return None
    # Usamos el último Ratio_... del path, que corresponde a la carpeta más específica.
    return path_val_to_float(matches[-1])


def generar_sim_hash_unico(folder_path):
    """
    Identificador único de carpeta/simulación.
    No debe colapsar configuraciones físicas equivalentes de campañas distintas.
    """
    path_norm = os.path.abspath(folder_path)
    return hashlib.md5(path_norm.encode()).hexdigest()[:12]


def generar_config_hash(params):
    """
    Identificador de configuración nominal/física.
    Sirve para trazabilidad; las agrupaciones se hacen explícitamente por columnas nominales.
    """
    keys = [
        'system_type',
        'chi',
        'area_ratio_nominal',
        'r_ratio_nominal',
        'w_salida',
        'Radio_silo',
    ]
    s = "|".join([str(params.get(k, "")) for k in keys])
    return hashlib.md5(s.encode()).hexdigest()[:12]


def parse_params(filepath, folder_path):
    params = {
        'chi': None,
        'w_salida': None,
        'r_ratio': 1.0,
        'r_ratio_nominal': 1.0,
        'area_ratio': 1.0,
        'area_ratio_nominal': 1.0,
        'area_ratio_target': np.nan,
        'system_type': "Puro",
    }

    grain_defs = []
    reading_grains = False
    grains_to_read = 0

    chi_match = re.search(r"Chi_([\dp]+)", folder_path)
    w_match = re.search(r"_W_([\dp]+)", folder_path)
    folder_ratio = extraer_ratio_nominal_del_path(folder_path)

    if chi_match:
        params['chi'] = path_val_to_float(chi_match.group(1))
    if w_match:
        params['w_salida'] = path_val_to_float(w_match.group(1))

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line:
                    continue

                if reading_grains and grains_to_read > 0:
                    parts = line.split()
                    if len(parts) >= 6:
                        grain_defs.append({
                            'radius': float(parts[1]),
                            'sides': int(parts[2]),
                        })
                        grains_to_read -= 1
                    continue

                if ':' in line:
                    parts = line.split(':', 1)
                    key_raw = parts[0].strip()
                    val_str = parts[1].strip()

                    try:
                        val = float(val_str) if ('.' in val_str or 'e' in val_str.lower()) else int(val_str)
                    except Exception:
                        val = val_str

                    key_norm = key_raw.lower().replace(" ", "_")

                    if key_norm in ['concentracion_aditivo', 'chi'] and params['chi'] is None:
                        params['chi'] = val
                    elif key_norm in ['radio_salida', 'w_salida'] and params['w_salida'] is None:
                        params['w_salida'] = val
                    else:
                        params[key_raw] = val

                    if key_norm == 'notipogranos':
                        reading_grains = True
                        grains_to_read = int(val)

        if grain_defs:
            gs = sorted(grain_defs, key=lambda x: float(x['radius']), reverse=True)

            params['r_large'] = float(gs[0]['radius'])
            params['area_large'] = round(
                calcular_area_geometrica(gs[0]['radius'], gs[0]['sides']),
                4,
            )

            nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent", 6: "Hex", 8: "Oct"}
            n1 = nombres.get(gs[0]['sides'], "Pol")

            if len(gs) >= 2:
                params['r_small'] = float(gs[1]['radius'])
                params['r_ratio'] = round(float(gs[1]['radius']) / float(gs[0]['radius']), 4)
                params['r_ratio_nominal'] = nominalizar_ratio_real(params['r_ratio'], ndigits=2)

                params['area_small'] = round(
                    calcular_area_geometrica(gs[1]['radius'], gs[1]['sides']),
                    4,
                )
                params['area_ratio'] = round(params['area_small'] / params['area_large'], 4)

                # Regla correcta: la etiqueta nominal del barrido sale del path si existe.
                if folder_ratio is not None:
                    params['area_ratio_nominal'] = nominalizar_ratio_real(folder_ratio, ndigits=3)
                    params['area_ratio_target'] = nominalizar_ratio_real(folder_ratio, ndigits=3)
                else:
                    params['area_ratio_nominal'] = nominalizar_ratio_real(params['area_ratio'], ndigits=3)
                    params['area_ratio_target'] = np.nan

                n2 = nombres.get(gs[1]['sides'], "Pol")
                params['system_type'] = f"{n1}-{n2}"
            else:
                params['r_small'] = np.nan
                params['area_small'] = np.nan
                params['r_ratio'] = 1.0
                params['r_ratio_nominal'] = 1.0
                params['area_ratio'] = 1.0
                params['area_ratio_nominal'] = 1.0
                params['area_ratio_target'] = np.nan
                params['system_type'] = n1

        elif folder_ratio is not None:
            # Respaldo si no se pudo leer grain_defs.
            params['area_ratio'] = folder_ratio
            params['area_ratio_nominal'] = nominalizar_ratio_real(folder_ratio, ndigits=3)
            params['area_ratio_target'] = nominalizar_ratio_real(folder_ratio, ndigits=3)
            params['r_ratio'] = round(np.sqrt(folder_ratio), 4)
            params['r_ratio_nominal'] = nominalizar_ratio_real(params['r_ratio'], ndigits=2)

        if params['chi'] is None:
            params['chi'] = 0.0
        if params['w_salida'] is None and 'Radio_salida' in params:
            params['w_salida'] = params['Radio_salida']

        params['grain_json'] = json.dumps(grain_defs)
        return params

    except Exception as e:
        print(f"Error leyendo {filepath}: {e}")
        return None


def main(base_dir=ROOT_DIR):
    print(f"--- Indexando en: {base_dir} ---")
    data = []

    for root, dirs, files in os.walk(base_dir):
        if "params.in" not in files:
            continue

        p = parse_params(os.path.join(root, "params.in"), root)
        if not p:
            continue

        t_match = re.search(r'TIRADA(\d+)', root, re.IGNORECASE)
        p['tirada'] = int(t_match.group(1)) if t_match else 1

        cat_match = re.search(r'(BARRIDO_[^/]+|MEZCLA_[^/]+|DISK_DISK_[^/]+)', root)
        p['category'] = cat_match.group(0) if cat_match else "General"

        p['path'] = root
        p['sim_hash'] = generar_sim_hash_unico(root)
        p['config_hash'] = generar_config_hash(p)
        data.append(p)

    if not data:
        print("No hay datos.")
        return

    df = pd.DataFrame(data)

    cols_prioritarias = [
        'sim_hash',
        'config_hash',
        'category',
        'system_type',
        'chi',
        'r_ratio',
        'r_ratio_nominal',
        'area_ratio',
        'area_ratio_nominal',
        'area_ratio_target',
        'w_salida',
        'tirada',
        'path',
    ]

    existentes = [c for c in cols_prioritarias if c in df.columns]
    df = df[existentes + [c for c in df.columns if c not in existentes]]

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"[+] Éxito: {len(df)} simulaciones indexadas.")
    print(f"[+] Guardado en: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
