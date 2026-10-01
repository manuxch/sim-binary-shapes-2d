import pandas as pd
import os

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas
IDX_PATH = rutas.MASTER_INDEX
OUT_DIR = rutas.AVALANCHE_DIR


def ensure_nominal_columns(df):
    if 'area_ratio_nominal' not in df.columns and 'area_ratio' in df.columns:
        df['area_ratio_nominal'] = df['area_ratio'].round(3)
    if 'r_ratio_nominal' not in df.columns and 'r_ratio' in df.columns:
        df['r_ratio_nominal'] = df['r_ratio'].round(2)
    return df


def consolidate_arcs(idx_path=IDX_PATH, output_dir=OUT_DIR):
    """
    Consolida estadisticas_arcos.csv de cada simulación y agrega metadatos
    desde master_sim_index.csv.

    Conserva simultáneamente:
      - area_ratio/r_ratio reales, para trazabilidad.
      - area_ratio_nominal/r_ratio_nominal, para agrupar y graficar.
    """
    print("\n[+] Iniciando consolidación robusta del Mega Dataset de Arcos...")

    if not os.path.exists(idx_path):
        print(f" [!] Error: No se encontró el índice maestro en {idx_path}. Ejecutá indexer.py primero.")
        return False

    df_idx = pd.read_csv(idx_path)
    df_idx = ensure_nominal_columns(df_idx)

    all_arcs = []
    archivos_encontrados = 0

    for _, row in df_idx.iterrows():
        sim_path = row.get('path', '')
        stats_file = os.path.join(sim_path, 'estadisticas_arcos.csv')

        if not os.path.exists(stats_file):
            continue

        try:
            df_temp = pd.read_csv(stats_file)
            if df_temp.empty:
                continue
            df_temp['sim_hash'] = row.get('sim_hash')
            all_arcs.append(df_temp)
            archivos_encontrados += 1
        except Exception as e:
            print(f" [!] Error leyendo {stats_file}: {e}")

    if not all_arcs:
        print("  -> [!] No se encontraron datos para consolidar.")
        return False

    mega_df = pd.concat(all_arcs, ignore_index=True)

    cols_fisicas = [
        'sim_hash',
        'config_hash',
        'category',
        'system_type',
        'chi',
        'r_small',
        'r_ratio',
        'r_ratio_nominal',
        'area_small',
        'area_ratio',
        'area_ratio_nominal',
        'area_ratio_target',
        'tirada',
        'path',
    ]
    cols_to_merge = [c for c in cols_fisicas if c in df_idx.columns]

    # sim_hash ya es único por carpeta en el indexer corregido.
    df_meta = df_idx[cols_to_merge].drop_duplicates(subset=['sim_hash'])
    mega_df = pd.merge(mega_df, df_meta, on='sim_hash', how='left')

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "resultados_completos_arcos.csv")

    meta_order = [
        'sim_hash',
        'config_hash',
        'category',
        'system_type',
        'chi',
        'area_ratio_nominal',
        'area_ratio',
        'area_ratio_target',
        'r_ratio_nominal',
        'r_ratio',
        'r_small',
        'area_small',
        'tirada',
        'path',
    ]
    actual_meta = [c for c in meta_order if c in mega_df.columns]
    resto_cols = [c for c in mega_df.columns if c not in actual_meta]
    mega_df = mega_df[actual_meta + resto_cols]

    mega_df.to_csv(output_path, index=False)

    print(f"  -> Se consolidaron {archivos_encontrados} archivos.")
    print(f"  -> Total de arcos: {len(mega_df)}")
    print(f"  -> Variables detectadas: {actual_meta}")
    print(f"  -> Mega Dataset guardado en: {output_path}")
    return True


if __name__ == "__main__":
    consolidate_arcs()
