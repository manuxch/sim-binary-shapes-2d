import pandas as pd
import numpy as np
import os
import json

def get_detailed_system_name(row):
    try:
        grains = json.loads(row['grain_json'])
        gs = sorted(grains, key=lambda x: x['radius'], reverse=True)
        nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}
        n1 = nombres.get(gs[0]['sides'], "Pol")
        n2 = nombres.get(gs[1]['sides'], "Pol") if len(gs)>1 else "Puro"
        return f"{n1}(G)-{n2}(C)"
    except: return "Otros"

def get_physics_extras(row):
    """Calcula el ratio de orificio (D/d)^2 y extrae el radio de la partícula grande."""
    try:
        grains = json.loads(row['grain_json'])
        gs = sorted(grains, key=lambda x: x['radius'], reverse=True)
        r_large = gs[0]['radius']
        
        radio_salida = row.get('Radio_salida', np.nan)
        if pd.notnull(radio_salida) and r_large > 0:
            D_d_sq = (radio_salida / r_large)**2
        else:
            D_d_sq = np.nan
            
        return pd.Series({'r_large': r_large, 'D_d_sq': D_d_sq})
    except:
        return pd.Series({'r_large': np.nan, 'D_d_sq': np.nan})

def main(idx_path="../master_sim_index.csv", 
         av_path="../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"):
    
    print("[+] Ejecutando análisis estadístico global de flujo y avalanchas...")
    if not os.path.exists(idx_path): 
        return print("Ejecutá indexer.py primero.")
    
    df_idx = pd.read_csv(idx_path)
    df_av = pd.read_csv(av_path)
    
    # 1. Expandir Metadatos y Física
    df_idx['sistema'] = df_idx.apply(get_detailed_system_name, axis=1)
    df_idx['grano_base'] = df_idx['sistema'].apply(lambda x: x.split('-')[0])
    
    df_extra = df_idx.apply(get_physics_extras, axis=1)
    df_idx = pd.concat([df_idx, df_extra], axis=1)
    
    # 2. Unir con Avalanchas
    cols_idx = ['sim_hash', 'chi', 'r_ratio', 'area_ratio', 'sistema', 'grano_base', 'r_large', 'D_d_sq']
    df = pd.merge(df_av, df_idx[cols_idx], on='sim_hash')

    # Filtro general de concentración
    df = df[df['chi'] <= 0.2]

    # --- NUEVO: Evitamos que Pandas borre los sistemas puros ---
    # Si no hay segunda partícula, los ratios de tamaño valen 1.0
    df['r_ratio'] = df['r_ratio'].fillna(1.0)
    df['area_ratio'] = df['area_ratio'].fillna(1.0)

    # 3. Agrupación y Estadística Base (Media y SEM)
    # Agrupamos por todas las variables físicas que definen un estado único
    group_cols = ['sistema', 'chi', 'r_ratio', 'area_ratio', 'D_d_sq', 'grano_base']
    res = df.groupby(group_cols).agg(
        S_mean=('tamano_big', 'mean'),
        S_sem=('tamano_big', 'sem')
    ).reset_index()

    # 4. Transformaciones Logarítmicas y Propagación de Errores
    # ln(S + 1)
    res['log_S'] = np.log(res['S_mean'] + 1)
    # Error propagado: \Delta S / (S + 1)
    res['log_S_err'] = res['S_sem'] / (res['S_mean'] + 1)

    # Limpieza de valores nulos o infinitos
    res = res.dropna(subset=['log_S'])

    # 5. Guardado del Dataset Agregado
    out_dir = "../processed_data/1_avalanche_data"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "estadisticas_flujo_agregadas.csv")
    
    res.to_csv(out_path, index=False)
    print(f"✅ Estadísticas calculadas y consolidadas ({len(res)} casos únicos).")
    print(f"   -> Guardado en: {out_path}")

if __name__ == "__main__":
    main()