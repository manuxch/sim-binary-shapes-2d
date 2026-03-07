import pandas as pd
import numpy as np
import os

# =============================================================================
# CONSOLIDADOR PRINCIPAL (Enfoque: Source of Truth)
# =============================================================================
def consolidate_arcs(idx_path="../master_sim_index.csv", output_dir="../processed_data/1_avalanche_data"):
    """
    Consolida todos los archivos de arcos y los enriquece mediante un merge 
    con el índice maestro, asegurando precisión en radios y concentraciones.
    """
    print("\n[+] Iniciando consolidación robusta del Mega Dataset de Arcos...")
    
    if not os.path.exists(idx_path):
        print(f" [!] Error: No se encontró el índice maestro en {idx_path}. Ejecuta indexer.py primero.")
        return False

    # 1. Cargamos el índice maestro (la fuente de verdad técnica)
    df_idx = pd.read_csv(idx_path)
    all_arcs = []
    archivos_encontrados = 0
    
    # 2. Recolección de datos brutos
    for _, row in df_idx.iterrows():
        sim_path = row.get('path', '')
        stats_file = os.path.join(sim_path, 'estadisticas_arcos.csv')
        
        if os.path.exists(stats_file):
            try:
                df_temp = pd.read_csv(stats_file)
                if df_temp.empty: continue
                
                # Solo necesitamos el hash para vincularlo luego con toda la física
                df_temp['sim_hash'] = row.get('sim_hash')
                all_arcs.append(df_temp)
                archivos_encontrados += 1
                
            except Exception as e:
                print(f" [!] Error leyendo {stats_file}: {e}")
    
    # 3. Fusión y Enriquecimiento
    if all_arcs:
        # Combinamos todos los arcos detectados
        mega_df = pd.concat(all_arcs, ignore_index=True)
        
        # --- EL PASO CLAVE: MERGE ---
        # Traemos las columnas físicas reales del indexador. 
        # Esto garantiza que si variaste el tamaño (r_small) para un mismo chi, se mantenga la distinción.
        cols_fisicas = ['sim_hash', 'system_type', 'chi', 'r_small', 'r_ratio', 'tirada']
        # Filtramos solo las columnas que existan en el indexador para evitar errores
        cols_to_merge = [c for c in cols_fisicas if c in df_idx.columns]
        
        mega_df = pd.merge(mega_df, df_idx[cols_to_merge], on='sim_hash', how='left')
        
        # 4. Organización y Guardado
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "resultados_completos_arcos.csv")
        
        # Ordenamos columnas: Metadatos primero, luego datos de arcos
        meta_order = ['sim_hash', 'system_type', 'chi', 'r_ratio', 'r_small', 'tirada']
        actual_meta = [c for c in meta_order if c in mega_df.columns]
        resto_cols = [c for c in mega_df.columns if c not in actual_meta]
        
        mega_df = mega_df[actual_meta + resto_cols]
        
        # Guardar
        mega_df.to_csv(output_path, index=False)
        
        print(f"  -> Se consolidaron {archivos_encontrados} archivos.")
        print(f"  -> Total de arcos: {len(mega_df)}")
        print(f"  -> Variables detectadas: {actual_meta}")
        print(f"  -> Mega Dataset guardado en: {output_path}")
        return True
    else:
        print("  -> [!] No se encontraron datos para consolidar.")
        return False

if __name__ == "__main__":
    consolidate_arcs()