import os
import glob
import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib

# Evita errores visuales si se corre en el clúster sin entorno gráfico
matplotlib.use('Agg')

# =============================================================================
# 1. IMPORTACIÓN DE TU LÓGICA TOPOLÓGICA
# =============================================================================
from generar_csv_arcos import parse_params, parse_xy, detectar_arco_primario

def aislar_nodos_del_arco_exacto(archivo_xy, archivo_dat, archivo_params):
    params = parse_params(archivo_params)
    particles = parse_xy(archivo_xy)
    
    try:
        contacts = pd.read_csv(archivo_dat, sep=r'\s+', comment='#', 
                               names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'])
    except Exception:
        return []

    G = nx.Graph()
    for pid, attr in particles.items(): 
        G.add_node(pid, **attr)
    
    valid_c = contacts[(contacts['id_a'] >= 0) & (contacts['id_b'] >= 0)]
    for _, row in valid_c.iterrows():
        u, v = int(row['id_a']), int(row['id_b'])
        if u in particles and v in particles:
            y_max = max(particles[u]['pos'][1], particles[v]['pos'][1])
            costo = 10.0 ** y_max 
            if G.has_edge(u, v):
                G[u][v]['weight'] += row['f_norm']
                G[u][v]['costo_arco'] = min(costo, G[u][v].get('costo_arco', float('inf')))
            else:
                G.add_edge(u, v, weight=row['f_norm'], costo_arco=costo)

    arco_path = detectar_arco_primario(G, particles, params)
    return arco_path

# =============================================================================
# 2. PROCESAMIENTO TENSIONAL (Love-Weber)
# =============================================================================
def calcular_estado_tensional(archivo_xy, archivo_sxy, archivo_dat, archivo_params, y_max_roi=15.0):
    ids_arco = aislar_nodos_del_arco_exacto(archivo_xy, archivo_dat, archivo_params)
    if not ids_arco: return None
        
    df_xy = pd.read_csv(archivo_xy, sep=r'\s+', header=None, 
                        names=['gID', 'type', 'x', 'y', 'r', 'active'])
    
    with open(archivo_sxy, 'r') as f:
        lineas = f.readlines()
        header_sxy = lineas[1].replace('#', '').split()
        t_sim = float(lineas[0].split(':')[1].strip())
        
    df_sxy = pd.read_csv(archivo_sxy, sep=r'\s+', skiprows=2, names=header_sxy)
    
    df = pd.merge(df_xy, df_sxy, on='gID', how='inner')
    df['Presion'] = -0.5 * (df['stres.xx'] + df['stres.yy'])
    df['Corte_Max'] = np.sqrt(((df['stres.xx'] - df['stres.yy'])/2)**2 + df['stres.xy']**2)
    
    df['Zona'] = 'Bulk'
    df.loc[df['y'] <= y_max_roi, 'Zona'] = 'ROI'
    df.loc[df['gID'].isin(ids_arco), 'Zona'] = 'Arco'
    
    resumen = df.groupby('Zona')[['Presion', 'Corte_Max']].mean().to_dict('index')
    
    salida = {
        'tSim': t_sim,
        'N_Nodos_Arco': len(ids_arco)
    }
    for zona in ['Bulk', 'ROI', 'Arco']:
        salida[f'Presion_{zona}'] = resumen.get(zona, {}).get('Presion', np.nan)
        salida[f'Corte_{zona}'] = resumen.get(zona, {}).get('Corte_Max', np.nan)
        
    return salida

# =============================================================================
# 3. INTEGRACIÓN CON EL ECOSISTEMA (Lectura del Indexer)
# =============================================================================
def procesar_desde_indice(index_file, y_max_roi=15.0):
    print(f"[+] Cargando índice maestro: {index_file}")
    if not os.path.exists(index_file):
        print(" [!] Error: No se encontró el master_sim_index.csv")
        return pd.DataFrame()

    df_idx = pd.read_csv(index_file)
    print(f"  -> {len(df_idx)} simulaciones encontradas para procesar.")
    
    resultados_crudos = []
    
    for idx, row in df_idx.iterrows():
        sim_path = row['path']
        sim_hash = row['sim_hash']
        chi = row.get('chi', 0.0)
        r_ratio = row.get('r_ratio', 1.0)
        sistema = row.get('system_type', 'Desconocido')
        
        archivo_params = os.path.join(sim_path, "params.in")
        
        frames_dirs = glob.glob(os.path.join(sim_path, "frames_*"))
        if not frames_dirs or not os.path.exists(archivo_params):
            continue
            
        frames_dir = frames_dirs[0]
        
        archivos_xy = sorted(glob.glob(os.path.join(frames_dir, "atasco_*.xy")))
        archivos_dat = sorted(glob.glob(os.path.join(frames_dir, "atasco_contacts_*.dat")))
        archivos_sxy = sorted(glob.glob(os.path.join(frames_dir, "atasco_frm_*.sxy")))
        
        # --- EXCEPCIÓN: VERIFICACIÓN DE ARCHIVOS SXY ---
        if not archivos_sxy:
            print(f"[{idx+1}/{len(df_idx)}] OMITIENDO {sim_hash} | Chi: {chi} -> No existen archivos .sxy en la carpeta")
            continue
            
        if not archivos_xy or not archivos_dat:
            print(f"[{idx+1}/{len(df_idx)}] OMITIENDO {sim_hash} | Chi: {chi} -> Faltan archivos .xy o .dat")
            continue
        # -----------------------------------------------
        
        print(f"[{idx+1}/{len(df_idx)}] Procesando {sim_hash} | Chi: {chi} | Ratio: {r_ratio} | Atascos: {len(archivos_xy)}")
        
        for f_xy, f_dat, f_sxy in zip(archivos_xy, archivos_dat, archivos_sxy):
            try:
                met = calcular_estado_tensional(f_xy, f_sxy, f_dat, archivo_params, y_max_roi)
                if met:
                    met['sim_hash'] = sim_hash
                    met['system_type'] = sistema
                    met['chi'] = chi
                    met['r_ratio'] = r_ratio
                    met['Archivo_ID'] = os.path.basename(f_xy)
                    resultados_crudos.append(met)
            except Exception as e:
                pass 
                
    df_crudo = pd.DataFrame(resultados_crudos)
    return df_crudo

# =============================================================================
# EJECUCIÓN PRINCIPAL
# =============================================================================
if __name__ == "__main__":
    INDEX_FILE = "/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
    OUT_DIR = "/work/lab/project/sim-binary-shapes-2d/processed_data/5_tensional_analysis"
    
    os.makedirs(OUT_DIR, exist_ok=True)
    
    df_crudo = procesar_desde_indice(INDEX_FILE, y_max_roi=15.0)
    
    if not df_crudo.empty:
        cols = ['sim_hash', 'system_type', 'chi', 'r_ratio', 'Archivo_ID', 'tSim', 'N_Nodos_Arco', 
                'Presion_Arco', 'Corte_Arco', 'Presion_ROI', 'Corte_ROI', 'Presion_Bulk', 'Corte_Bulk']
        df_crudo = df_crudo[[c for c in cols if c in df_crudo.columns]]
        
        path_crudo = os.path.join(OUT_DIR, "dataset_tensional_crudo.csv")
        df_crudo.to_csv(path_crudo, index=False)
        print(f"\n[+] Datos guardados en: {path_crudo}")
        
        group_cols = ['system_type', 'r_ratio', 'chi']
        df_mean = df_crudo.groupby(group_cols).mean(numeric_only=True).reset_index()
        
        path_promedio = os.path.join(OUT_DIR, "dataset_tensional_promediado.csv")
        df_mean.to_csv(path_promedio, index=False)
        print(f"[+] Resumen estadístico guardado en: {path_promedio}")
        
    else:
        print("[-] No se generaron datos para procesar.")
