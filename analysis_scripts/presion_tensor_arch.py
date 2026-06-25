#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import argparse
import json
import ast
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.csgraph as csgraph
import gc
import multiprocessing as mp

CHI_REGEX = re.compile(r'(?:Chi_|_X)([0-9]+(?:p[0-9]+)?)')

def poly_area(coords):
    x = coords[:, 0]
    y = coords[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def nombre_forma(n_sides):
    if pd.isna(n_sides): return "Ninguna"
    n = int(n_sides)
    if n == 1: return "Disco"
    if n == 3: return "Triangulo"
    if n == 4: return "Cuadrado"
    if n == 5: return "Pentagono"
    if n == 6: return "Hexagono"
    return f"Poli{n}"

def parse_xy(filename):
    particles = {}
    with open(filename, "r") as f:
        for line in f:
            p = line.split()
            if not p: continue
            pid = int(p[0])
            if pid < 0: continue
            n_sides = int(p[1])
            shape_name = nombre_forma(n_sides)
            if n_sides == 1:
                x, y, r, ptype = np.float32(p[2]), np.float32(p[3]), np.float32(p[4]), int(p[5])
                area = np.pi * (r**2)
                particles[pid] = {"pos_x": x, "pos_y": y, "r_eff": r, "type": ptype, "shape": shape_name, "area": area, "coords": None}
            else:
                coords = np.array(p[2:-1], dtype=np.float32).reshape(-1, 2)
                center = coords.mean(axis=0)
                ptype = int(p[-1])
                r_eff = np.float32(np.max(np.linalg.norm(coords - center, axis=1)))
                area = poly_area(coords)
                particles[pid] = {"pos_x": center[0], "pos_y": center[1], "r_eff": r_eff, "type": ptype, "shape": shape_name, "area": area, "coords": coords}
    return particles

def detectar_arco_primario_scipy(df_contacts, df_particles, umbral_r):
    if df_particles.empty or df_contacts.empty: return []
    
    r_col = 'r_nominal' if 'r_nominal' in df_particles.columns else 'r_eff'
    valid_nodes_mask = (df_particles[r_col] >= umbral_r) & (df_particles['pos_y'] < 15.0)
    valid_nodes = df_particles.index[valid_nodes_mask].to_numpy()
    if len(valid_nodes) == 0: return []
    
    valid_mask = df_contacts['id_a'].isin(valid_nodes) & df_contacts['id_b'].isin(valid_nodes)
    valid_contacts = df_contacts[valid_mask]
    if valid_contacts.empty: return []
    
    unique_nodes = np.unique(np.concatenate([valid_contacts['id_a'], valid_contacts['id_b']]))
    node_to_idx = {node: i for i, node in enumerate(unique_nodes)}
    row = valid_contacts['id_a'].map(node_to_idx).values
    col = valid_contacts['id_b'].map(node_to_idx).values
    
    adj_matrix = sp.coo_matrix((np.ones(len(row), dtype=np.int8), (row, col)), shape=(len(unique_nodes), len(unique_nodes)))
    n_comp, labels = csgraph.connected_components(csgraph=adj_matrix, directed=False, return_labels=True)
    largest_cc_indices = np.where(labels == np.unique(labels, return_counts=True)[1].argmax())[0]
    arco_ids = unique_nodes[largest_cc_indices]
    
    arco_set = set(arco_ids)
    es_vecino = df_contacts[
        (df_contacts['id_a'].isin(arco_set) & (~df_contacts['id_b'].isin(arco_set))) |
        (df_contacts['id_b'].isin(arco_set) & (~df_contacts['id_a'].isin(arco_set)))
    ]
    vecinos_ids = np.unique(np.concatenate([
        es_vecino.loc[~es_vecino['id_b'].isin(arco_set), 'id_b'],
        es_vecino.loc[~es_vecino['id_a'].isin(arco_set), 'id_a']
    ]))
    return np.union1d(arco_ids, vecinos_ids).tolist()

def obtener_vector_normal_poly(row):
    px, py = row['px'], row['py']
    cx, cy = row['pos_x_A'], row['pos_y_A']
    coords = row['coords']
    n_vertices = len(coords)
    min_dist = float('inf')
    mejor_normal = (0.0, 0.0)
    for i in range(n_vertices):
        x1, y1 = coords[i]
        x2, y2 = coords[(i+1) % n_vertices]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx*dx + dy*dy
        if l2 == 0: continue
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / l2))
        proy_x, proy_y = x1 + t * dx, y1 + t * dy
        dist2 = (px - proy_x)**2 + (py - proy_y)**2
        if dist2 < min_dist:
            min_dist = dist2
            nx_v, ny_v = -dy, dx
            norma = np.hypot(nx_v, ny_v)
            if norma > 0:
                nx_v, ny_v = nx_v/norma, ny_v/norma
            if (nx_v * (proy_x - cx) + ny_v * (proy_y - cy)) < 0:
                nx_v, ny_v = -nx_v, -ny_v
            mejor_normal = (nx_v, ny_v)
    return mejor_normal

def calcular_tensor_y_presion_vectorizado(df_particles, df_contacts, arco_path, dt, umbral_r):
    df = df_contacts.merge(df_particles[['pos_x', 'pos_y', 'shape', 'coords']], left_on='id_a', right_index=True)
    df = df.merge(df_particles[['pos_x', 'pos_y']], left_on='id_b', right_index=True, suffixes=('_A', '_B'))
    
    df['nx_v'] = np.float32(0.0)
    df['ny_v'] = np.float32(0.0)
    mask_disk = df['shape'] == 'Disco'
    if mask_disk.any():
        nx_disk = df.loc[mask_disk, 'px'] - df.loc[mask_disk, 'pos_x_A']
        ny_disk = df.loc[mask_disk, 'py'] - df.loc[mask_disk, 'pos_y_A']
        norma = np.hypot(nx_disk, ny_disk)
        valid = norma > 0
        df.loc[mask_disk, 'nx_v'] = np.where(valid, nx_disk / norma, 0.0).astype(np.float32)
        df.loc[mask_disk, 'ny_v'] = np.where(valid, ny_disk / norma, 0.0).astype(np.float32)
    
    mask_poly = ~mask_disk
    if mask_poly.any():
        normals = df[mask_poly].apply(obtener_vector_normal_poly, axis=1)
        df.loc[mask_poly, 'nx_v'] = normals.apply(lambda x: x[0]).astype(np.float32)
        df.loc[mask_poly, 'ny_v'] = normals.apply(lambda x: x[1]).astype(np.float32)

    df['tx_v'] = -df['ny_v']
    df['ty_v'] = df['nx_v']
    df['Fx_A'] = ((-df['f_norm'] * df['nx_v'] - df['f_tan'] * df['tx_v']) / dt).astype(np.float32)
    df['Fy_A'] = ((-df['f_norm'] * df['ny_v'] - df['f_tan'] * df['ty_v']) / dt).astype(np.float32)
    
    df['S00_A'] = (df['Fx_A'] * (df['px'] - df['pos_x_A'])).astype(np.float32)
    df['S11_A'] = (df['Fy_A'] * (df['py'] - df['pos_y_A'])).astype(np.float32)
    df['S00_B'] = (-df['Fx_A'] * (df['px'] - df['pos_x_B'])).astype(np.float32)
    df['S11_B'] = (-df['Fy_A'] * (df['py'] - df['pos_y_B'])).astype(np.float32)
    
    tensor_A = df.groupby('id_a')[['S00_A', 'S11_A']].sum().rename(columns={'S00_A':'S00', 'S11_A':'S11'})
    tensor_B = df.groupby('id_b')[['S00_B', 'S11_B']].sum().rename(columns={'S00_B':'S00', 'S11_B':'S11'})
    tensor_total = tensor_A.add(tensor_B, fill_value=0)
    
    del df, tensor_A, tensor_B
    
    p_df = df_particles.join(tensor_total).fillna({'S00': 0, 'S11': 0})
    p_df['P'] = np.where(p_df['area'] > 0, -0.5 * (p_df['S00'] + p_df['S11']) / p_df['area'], 0.0)
    
    y_arco = p_df.loc[p_df.index.isin(arco_path), 'pos_y'] if arco_path else []
    roi_ymin = y_arco.min() if len(y_arco) > 0 else 0
    roi_ymax = y_arco.max() + 10.0 if len(y_arco) > 0 else 20.0
    
    p_df['region'] = np.where(p_df.index.isin(arco_path), 'arco',
                     np.where((p_df['pos_y'] >= roi_ymin) & (p_df['pos_y'] <= roi_ymax), 'roi', 'bulk'))
    
    r_col = 'r_nominal' if 'r_nominal' in p_df.columns else 'r_eff'
    p_df['tipo'] = np.where(p_df[r_col] >= umbral_r, 'B', 'S')
    p_df['P_A'] = p_df['P'] * p_df['area']

    res = {}
    for region in ['arco', 'roi', 'bulk']:
        mask_reg = p_df['region'] == region
        sub_df = p_df[mask_reg]
        A_tot = sub_df['area'].sum()
        res[f"P_{region}"] = sub_df['P_A'].sum() / A_tot if A_tot > 0 else np.nan
        for tipo in ['B', 'S']:
            mask_tipo = sub_df['tipo'] == tipo
            A_tipo = sub_df.loc[mask_tipo, 'area'].sum()
            res[f"P_{region}_{tipo}"] = sub_df.loc[mask_tipo, 'P_A'].sum() / A_tipo if A_tipo > 0 else np.nan

    del p_df
    return res

def worker_wrapper(args):
    return process_one_jam_task(*args)

def process_one_jam_task(xy_file, contact_file, jam_id, config_id, dt, r_large_m, r_small_m, sides_large_m, sides_small_m, master_chi, sim_path):
    try:
        particles = parse_xy(xy_file)
        df_particles = pd.DataFrame.from_dict(particles, orient='index')
        df_particles.index.name = 'id'
        
        # Corrección geométrica intermedia para separar componentes numéricamente
        factors = {
            "Disco": 1.0,
            "Triangulo": float(np.cos(np.pi / 3)),
            "Cuadrado": float(np.cos(np.pi / 4)),
            "Pentagono": float(np.cos(np.pi / 5)),
            "Hexagono": float(np.cos(np.pi / 6))
        }
        df_particles['r_nominal'] = df_particles['r_eff'] * df_particles['shape'].map(factors).fillna(1.0)
        
        r_l = r_large_m
        r_s = r_small_m
        if pd.isna(r_l) or pd.isna(r_s):
            unique_r = np.unique(np.round(df_particles['r_nominal'].to_numpy(), 4))
            if len(unique_r) >= 2:
                r_l = unique_r.max() if pd.isna(r_l) else r_l
                r_s = unique_r.min() if pd.isna(r_s) else r_s
            else:
                r_l = unique_r[0] if pd.isna(r_l) else r_l
                r_s = unique_r[0] if pd.isna(r_s) else r_s

        if master_chi == 0.0 or r_s == r_l or pd.isna(r_s):
            umbral_r = 0.0  
            r_s_val = np.nan
        else:
            umbral_r = (r_l + r_s) / 2.0
            r_s_val = r_s

        cols = ['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan']
        dtypes_dict = {'id_a': np.int32, 'id_b': np.int32, 'px': np.float32, 'py': np.float32, 'f_norm': np.float32, 'f_tan': np.float32}
        df_contacts = pd.read_csv(contact_file, sep=r'\s+', names=cols, comment='#', dtype=dtypes_dict, engine='c')
        
        arco_path = detectar_arco_primario_scipy(df_contacts, df_particles, umbral_r)
        if not arco_path:
            return {"ok": False, "error": "No arco detectado"}
            
        summary = calcular_tensor_y_presion_vectorizado(df_particles, df_contacts, arco_path, dt, umbral_r)
        
        # DETERMINACIÓN DE FORMAS BASADA EN EL MASTER INDEX (Verdad de campo unívoca)
        if pd.notna(sides_large_m):
            forma_grande = nombre_forma(sides_large_m)
        else:
            grandes_mask = df_particles['r_nominal'] >= umbral_r
            grandes_shapes = df_particles.loc[grandes_mask, 'shape']
            forma_grande = grandes_shapes.mode()[0] if not grandes_shapes.empty else "Ninguna"

        if master_chi == 0.0 or pd.isna(r_s_val):
            forma_chica = "Ninguna"
        elif pd.notna(sides_small_m):
            forma_chica = nombre_forma(sides_small_m)
        else:
            chicas_mask = df_particles['r_nominal'] < umbral_r
            chicas_shapes = df_particles.loc[chicas_mask, 'shape']
            forma_chica = chicas_shapes.mode()[0] if not chicas_shapes.empty else "Ninguna"
        
        if pd.notna(master_chi):
            chi_val = float(master_chi)
        else:
            chi_match = CHI_REGEX.search(config_id)
            chi_val = float(chi_match.group(1).replace('p', '.')) if chi_match else np.nan

        summary['jam_id'] = jam_id
        summary['config_id'] = config_id
        summary['sim_path'] = sim_path 
        summary['forma_grande'] = forma_grande
        summary['forma_chica'] = forma_chica
        summary['chi'] = chi_val
        summary['r_chica'] = r_s_val 
        
        del df_particles, df_contacts
        return {"ok": True, "summary": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def write_buffer_to_csv(buffer, atasco_csv_path):
    if not buffer: return
    df_lote = pd.DataFrame(buffer)
    meta_cols = ['forma_grande', 'forma_chica', 'chi', 'r_chica', 'config_id', 'sim_path', 'jam_id']
    other_cols = [c for c in df_lote.columns if c not in meta_cols]
    meta_cols = [c for c in meta_cols if c in df_lote.columns]
    df_lote = df_lote[meta_cols + other_cols]
    escribir_header = not os.path.exists(atasco_csv_path)
    df_lote.to_csv(atasco_csv_path, mode='a', index=False, header=escribir_header)
    del df_lote

def parse_grain_column(val):
    if pd.isna(val):
        return {}
    val_str = str(val).strip()
    if val_str.startswith('"') and val_str.endswith('"'):
        val_str = val_str[1:-1]
    val_str = val_str.replace('""', '"')
    try:
        return json.loads(val_str)
    except:
        try:
            return ast.literal_eval(val_str)
        except:
            return {}

def generar_tareas(xy_files, master_dict, dt):
    for xy_file in xy_files:
        contact_file = xy_file.replace(".xy", ".dat").replace("atasco_", "atasco_contacts_")
        if os.path.exists(contact_file):
            jam_id = os.path.basename(xy_file).split('_')[-1].replace('.xy', '')
            config_id = os.path.basename(os.path.dirname(xy_file))
            
            # Normalizar la ruta del archivo actual para buscarlo en el master_dict de forma unívoca
            abs_xy = os.path.abspath(os.path.normpath(xy_file))
            sim_path = os.path.dirname(os.path.dirname(abs_xy)) # Sube 2 niveles para llegar a la raíz de la simulación
            
            # Intento de matcheo robusto: 
            # 1. Por ruta absoluta exacta
            config_info = master_dict.get(sim_path)
            
            # 2. Si no coincide la raíz (ej. si corrés el script desde otra ruta), matchea por el sufijo único "Categoría/Carpeta"
            if not config_info:
                parts = sim_path.split(os.sep)
                if len(parts) >= 2:
                    suffix_key = os.path.join(parts[-2], parts[-1])
                    config_info = master_dict.get(suffix_key, {})
                else:
                    config_info = {}
            
            r_large = config_info.get('r_large', np.nan)
            r_small = config_info.get('r_small', np.nan)
            sides_large = config_info.get('sides_large', np.nan)
            sides_small = config_info.get('sides_small', np.nan)
            chi_val = config_info.get('chi', np.nan)
            
            yield (xy_file, contact_file, jam_id, config_id, dt, r_large, r_small, sides_large, sides_small, chi_val, sim_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--master", required=True)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--dt", type=float, default=0.001)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    atasco_csv_path = os.path.join(args.out, "resumen_presion_por_atasco.csv")
    config_csv_path = os.path.join(args.out, "resumen_presion_por_configuracion.csv")

    if os.path.exists(atasco_csv_path):
        os.remove(atasco_csv_path)

    print("Cargando master index y parseando JSON de granos...")
    df_master = pd.read_csv(args.master)
    df_master = df_master.drop_duplicates(subset=['path'])
    
    master_dict = {}
    for _, row in df_master.iterrows():
        path_val = row.get('path')
        if pd.isna(path_val):
            continue
            
        grain_data = parse_grain_column(row.get('grain_json'))
        large_radius = np.nan
        large_sides = np.nan
        small_radius = np.nan
        small_sides = np.nan

        if isinstance(grain_data, list) and len(grain_data) > 0:
            large_radius = grain_data[0].get('radius', np.nan)
            large_sides = grain_data[0].get('sides', np.nan)
            if len(grain_data) > 1:
                small_radius = grain_data[1].get('radius', np.nan)
                small_sides = grain_data[1].get('sides', np.nan)
        
        if pd.isna(large_radius) and pd.notna(row.get('r_large')):
            large_radius = row.get('r_large')
        if pd.isna(small_radius) and pd.notna(row.get('r_small')):
            small_radius = row.get('r_small')

        info = {
            'r_large': large_radius,
            'r_small': small_radius,
            'sides_large': large_sides,
            'sides_small': small_sides,
            'chi': row.get('chi')
        }
        
        # Guardamos en el diccionario con la ruta absoluta normalizada
        path_abs = os.path.abspath(os.path.normpath(str(path_val)))
        master_dict[path_abs] = info
        
        # También guardamos usando la combinación "Categoría/Carpeta_Simulación" para evitar colisiones entre familias
        parts = path_abs.split(os.sep)
        if len(parts) >= 2:
            suffix_key = os.path.join(parts[-2], parts[-1])
            master_dict[suffix_key] = info
            
    del df_master

    print("Buscando archivos atasco_*.xy...")
    xy_files = sorted(glob.glob(os.path.join(args.dir, "**", "atasco_*.xy"), recursive=True))
    total_estimado = len(xy_files)
    print(f"Archivos encontrados (aprox a procesar): {total_estimado}")

    FLUSH_SIZE = 250 
    results_buffer = []
    processed_count = 0

    tareas_gen = generar_tareas(xy_files, master_dict, args.dt)

    with mp.Pool(processes=args.workers, maxtasksperchild=50) as pool:
        for res in pool.imap_unordered(worker_wrapper, tareas_gen, chunksize=10):
            processed_count += 1
            if res["ok"]:
                results_buffer.append(res["summary"])
            
            if len(results_buffer) >= FLUSH_SIZE:
                write_buffer_to_csv(results_buffer, atasco_csv_path)
                results_buffer.clear()
                gc.collect() 
            
            if processed_count % 1000 == 0:
                print(f"Procesados {processed_count} de {total_estimado}...")

    if results_buffer:
        write_buffer_to_csv(results_buffer, atasco_csv_path)
        results_buffer.clear()

    print("\n--- Procesamiento finalizado. Calculando promedios... ---")

    if os.path.exists(atasco_csv_path):
        df_all = pd.read_csv(atasco_csv_path)
        group_cols = ['forma_grande', 'forma_chica', 'chi', 'r_chica', 'config_id', 'sim_path']
        grouped = df_all.groupby(group_cols, dropna=False)
        df_config = grouped.size().reset_index(name='n_atascos')
        
        variables_presion = ['P_bulk', 'P_bulk_B', 'P_bulk_S', 'P_arco', 'P_arco_B', 'P_arco_S', 'P_roi', 'P_roi_B', 'P_roi_S']
        cols_to_agg = [var for var in variables_presion if var in df_all.columns]
        
        if cols_to_agg:
            df_means = grouped[cols_to_agg].mean().rename(columns=lambda x: f'mean_{x}').reset_index(drop=True)
            df_stds = grouped[cols_to_agg].std().rename(columns=lambda x: f'std_{x}').reset_index(drop=True)
            df_config = pd.concat([df_config, df_means, df_stds], axis=1)
            
            df_config.to_csv(config_csv_path, index=False)
            print(f"Finalizado - Archivo definitivo guardado en: {config_csv_path}")

if __name__ == "__main__":
    mp.freeze_support() 
    main()