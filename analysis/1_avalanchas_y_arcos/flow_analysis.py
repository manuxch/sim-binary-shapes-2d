import pandas as pd
import numpy as np
import os
import json

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas
IDX_PATH = rutas.MASTER_INDEX
AV_PATH = os.path.join(rutas.AVALANCHE_DIR, "resultados_completos_esqueleto.csv")
OUT_DIR = rutas.AVALANCHE_DIR


def get_detailed_system_name(row):
    try:
        grains = json.loads(row['grain_json'])
        gs = sorted(grains, key=lambda x: float(x['radius']), reverse=True)
        nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}
        n1 = nombres.get(int(gs[0]['sides']), "Pol")
        n2 = nombres.get(int(gs[1]['sides']), "Pol") if len(gs) > 1 else "Puro"
        return f"{n1}(G)-{n2}(C)"
    except Exception:
        return "Otros"


def get_physics_extras(row):
    """Calcula el ratio de orificio y extrae el radio de partícula grande."""
    try:
        grains = json.loads(row['grain_json'])
        gs = sorted(grains, key=lambda x: float(x['radius']), reverse=True)
        r_large = float(gs[0]['radius'])

        radio_salida = row.get('Radio_salida', np.nan)
        if pd.notnull(radio_salida) and r_large > 0:
            D_d_sq = (float(radio_salida) / r_large) ** 2
        else:
            D_d_sq = np.nan

        return pd.Series({'r_large': r_large, 'D_d_sq': D_d_sq})
    except Exception:
        return pd.Series({'r_large': np.nan, 'D_d_sq': np.nan})


def ensure_nominal_columns(df):
    """Garantiza compatibilidad si se usa un índice viejo por accidente."""
    if 'area_ratio_nominal' not in df.columns and 'area_ratio' in df.columns:
        df['area_ratio_nominal'] = df['area_ratio'].round(3)
    if 'r_ratio_nominal' not in df.columns and 'r_ratio' in df.columns:
        df['r_ratio_nominal'] = df['r_ratio'].round(2)
    return df


def main(idx_path=IDX_PATH, av_path=AV_PATH, solo_con_arco=False):
    print("[+] Ejecutando análisis estadístico global de flujo y avalanchas...")

    if not os.path.exists(idx_path):
        return print("Ejecutá indexer.py primero.")
    if not os.path.exists(av_path):
        return print(f"No se encontró {av_path}. Ejecutá processor.py primero.")

    df_idx = pd.read_csv(idx_path)
    df_idx = ensure_nominal_columns(df_idx)
    df_av = pd.read_csv(av_path)
    if solo_con_arco:
        # Solo avalanchas que terminaron en un atasco guardado (atasco_XXXXX.xy),
        # es decir, con un arco asociado (ver processor.py, columna atasco_id).
        if 'atasco_id' not in df_av.columns:
            return print("El esqueleto no tiene atasco_id: volve a correr processor.py (version nueva).")
        n0 = len(df_av)
        df_av = df_av[df_av['atasco_id'].notna()].copy()
        print(f"--solo_con_arco: {len(df_av)} de {n0} avalanchas tienen un atasco (arco) asociado.")

    df_idx['sistema'] = df_idx.apply(get_detailed_system_name, axis=1)
    df_idx['grano_base'] = df_idx['sistema'].apply(lambda x: x.split('-')[0])

    df_extra = df_idx.apply(get_physics_extras, axis=1)
    df_idx = pd.concat([df_idx, df_extra], axis=1)

    cols_idx = [
        'sim_hash',
        'config_hash',
        'category',
        'chi',
        'r_ratio',
        'r_ratio_nominal',
        'area_ratio',
        'area_ratio_nominal',
        'area_ratio_target',
        'sistema',
        'grano_base',
        'r_large',
        'D_d_sq',
    ]
    cols_idx = [c for c in cols_idx if c in df_idx.columns]

    df = pd.merge(df_av, df_idx[cols_idx], on='sim_hash', how='left')
    df = df[df['chi'] <= 0.4].copy()

    for col, default in [
        ('r_ratio', 1.0),
        ('r_ratio_nominal', 1.0),
        ('area_ratio', 1.0),
        ('area_ratio_nominal', 1.0),
    ]:
        if col in df.columns:
            df[col] = df[col].fillna(default)

    group_cols = [
        'sistema',
        'chi',
        'r_ratio_nominal',
        'area_ratio_nominal',
        'D_d_sq',
        'grano_base',
    ]
    group_cols = [c for c in group_cols if c in df.columns]

    # S: granos grandes por avalancha (tamano_big); ST: todos los granos,
    # grandes + chicos (total_mix), si el esqueleto trae esa columna.
    extra = {}
    if 'total_mix' in df.columns:
        extra = dict(ST_mean=('total_mix', 'mean'), ST_sem=('total_mix', 'sem'))
    res = (
        df.groupby(group_cols, dropna=False)
        .agg(
            S_mean=('tamano_big', 'mean'),
            S_sem=('tamano_big', 'sem'),
            **extra,
            n_avalancha=('tamano_big', 'count'),
            n_simulaciones=('sim_hash', 'nunique'),
            area_ratio_real_min=('area_ratio', 'min'),
            area_ratio_real_max=('area_ratio', 'max'),
            r_ratio_real_min=('r_ratio', 'min'),
            r_ratio_real_max=('r_ratio', 'max'),
        )
        .reset_index()
    )

    res['log_S'] = np.log(res['S_mean'] + 1)
    res['log_S_err'] = res['S_sem'] / (res['S_mean'] + 1)
    res = res.dropna(subset=['log_S'])

    os.makedirs(OUT_DIR, exist_ok=True)
    nombre = "estadisticas_flujo_agregadas_solo_con_arco.csv" if solo_con_arco else "estadisticas_flujo_agregadas.csv"
    out_path = os.path.join(OUT_DIR, nombre)
    res.to_csv(out_path, index=False)

    print(f"✅ Estadísticas calculadas y consolidadas ({len(res)} casos únicos).")
    print(f"   -> Guardado en: {out_path}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Estadisticas de avalanchas por configuracion.")
    ap.add_argument('--solo_con_arco', action='store_true',
                    help="usa solo las avalanchas que terminaron en un atasco con snapshot (arco); "
                         "guarda estadisticas_flujo_agregadas_solo_con_arco.csv")
    main(solo_con_arco=ap.parse_args().solo_con_arco)
