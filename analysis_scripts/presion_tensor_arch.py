#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import argparse
import numpy as np
import pandas as pd
import networkx as nx
import gc
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError

# =============================================================================
# FUNCIONES GEOMÉTRICAS Y TENSORIALES (IMPLEMENTACIÓN COMPLETA)
# =============================================================================

def poly_area(coords):
    x = coords[:, 0]
    y = coords[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def obtener_vector_normal(px, py, particula_ref):
    cx, cy = particula_ref["pos"]
    
    if particula_ref["shape"] == "Disco":
        nx_v, ny_v = px - cx, py - cy
        norma = np.hypot(nx_v, ny_v)
        return (nx_v/norma, ny_v/norma) if norma > 0 else (0.0, 0.0)

    coords = particula_ref["coords"]
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

def detectar_arco_primario(df_contacts, particles, params=None):
    G = nx.Graph()
    for _, row in df_contacts.iterrows():
        G.add_edge(int(row['id_a']), int(row['id_b']))
    
    radios = [p["r_eff"] for p in particles.values()]
    if not radios: return []
    
    umbral_r = (max(radios) + min(radios)) / 2.0
    big_nodes = [n for n, d in particles.items() if d["r_eff"] >= umbral_r]
    
    if not big_nodes: return []
    
    # Rango en Y para buscar arcos en la salida
    arco_candidates = [n for n in big_nodes if particles[n]["pos"][1] < 15.0]
    subgraph = G.subgraph(arco_candidates)
    
    if len(subgraph) == 0: return []
    
    try:
        largest_cc = max(nx.connected_components(subgraph), key=len)
        return list(largest_cc)
    except:
        return []

def parse_xy(filename):
    particles = {}
    with open(filename, "r") as f:
        for line in f:
            p = line.split()
            if not p: continue
            pid = int(p[0])
            if pid < 0: continue
            n_sides = int(p[1])
            
            if n_sides == 1:
                x, y, r, ptype = float(p[2]), float(p[3]), float(p[4]), int(p[5])
                area = np.pi * (r**2)
                particles[pid] = {"pos": (x, y), "r_eff": r, "type": ptype, "shape": "Disco", "area": area}
            else:
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = coords.mean(axis=0)
                ptype = int(p[-1])
                r_eff = float(np.max(np.linalg.norm(coords - center, axis=1)))
                area = poly_area(coords)
                particles[pid] = {"pos": (float(center[0]), float(center[1])), "r_eff": r_eff, "coords": coords, "type": ptype, "shape": "Poligono", "area": area}
    return particles

def calcular_tensor_y_presion(particles, df_contacts, arco_path):
    ids_arco = set(int(x) for x in arco_path)
    y_arco = [particles[pid]["pos"][1] for pid in ids_arco] if ids_arco else []
    roi_ymin = min(y_arco) if y_arco else 0
    roi_ymax = max(y_arco) + 10.0 if y_arco else 20.0
    
    for pid in particles:
        particles[pid]["stress_tensor"] = np.zeros((2, 2), dtype=float)
        
    for _, row in df_contacts.iterrows():
        id_a, id_b = int(row["id_a"]), int(row["id_b"])
        if id_a not in particles or id_b not in particles: continue
            
        px, py, fn = row["px"], row["py"], row["f_norm"]
        nx_v, ny_v = obtener_vector_normal(px, py, particles[id_a])
        
        Fx_A, Fy_A = fn * nx_v, fn * ny_v
        Fx_B, Fy_B = -Fx_A, -Fy_A
        
        cx_A, cy_A = particles[id_a]["pos"]
        rx_A, ry_A = px - cx_A, py - cy_A
        cx_B, cy_B = particles[id_b]["pos"]
        rx_B, ry_B = px - cx_B, py - cy_B
        
        particles[id_a]["stress_tensor"][0,0] += Fx_A * rx_A
        particles[id_a]["stress_tensor"][1,1] += Fy_A * ry_A
        particles[id_b]["stress_tensor"][0,0] += Fx_B * rx_B
        particles[id_b]["stress_tensor"][1,1] += Fy_B * ry_B

    radios = [p["r_eff"] for p in particles.values()]
    umbral_r = (max(radios) + min(radios)) / 2.0 if radios else 0.0
    records = []
    
    # Asignar región a cada partícula
    for pid, p in particles.items():
        A = p.get("area", 1.0)
        sig = p["stress_tensor"] / A if A > 0 else np.zeros((2,2))
        P = 0.5 * (sig[0,0] + sig[1,1])
        tipo = 'B' if p["r_eff"] >= umbral_r else 'S'
        
        x, y = p["pos"]
        if pid in ids_arco:
            region = 'arco'
        elif roi_ymin <= y <= roi_ymax:
            region = 'roi'
        else:
            region = 'bulk'
            
        records.append({"pid": pid, "region": region, "tipo": tipo, "P": P, "area": A})
        
    df_p = pd.DataFrame(records)
    res = {}
    
    # Calcular promedios por región y especie
    for reg in ['arco', 'roi', 'bulk']:
        df_reg = df_p[df_p["region"] == reg]
        A_tot = df_reg["area"].sum()
        res[f"P_{reg}"] = np.sum(df_reg["P"] * df_reg["area"]) / A_tot if A_tot > 0 else np.nan
        
        for tipo in ['B', 'S']:
            df_tipo = df_reg[df_reg["tipo"] == tipo]
            A_tipo = df_tipo["area"].sum()
            res[f"P_{reg}_{tipo}"] = np.sum(df_tipo["P"] * df_tipo["area"]) / A_tipo if A_tipo > 0 else np.nan
            
    return res

def process_one_jam_task(xy_file, contact_file, jam_id, config_id):
    try:
        particles = parse_xy(xy_file)
        cols = ['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan']
        df_contacts = pd.read_csv(contact_file, sep=r'\s+', names=cols, comment='#')
        
        params = {} 
        arco_path = detectar_arco_primario(df_contacts, particles, params=params)
        
        if not arco_path:
            return {"ok": False, "error": f"No arco detectado"}
            
        summary = calcular_tensor_y_presion(particles, df_contacts, arco_path)
        summary['jam_id'] = jam_id
        summary['config_id'] = config_id
        return {"ok": True, "summary": summary}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# =============================================================================
# MAIN: AGREGACIÓN ESTADÍSTICA (ESTILO FORCE_ARCH_V3)
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    xy_files = sorted(glob.glob(os.path.join(args.dir, "**", "*.xy"), recursive=True))
    
    tasks = []
    for xy_file in xy_files:
        contact_file = xy_file.replace(".xy", ".dat").replace("atasco_", "atasco_contacts_")
        if os.path.exists(contact_file):
            jam_id = os.path.basename(xy_file).split('_')[-1].replace('.xy', '')
            config_id = os.path.basename(os.path.dirname(xy_file))
            tasks.append((xy_file, contact_file, jam_id, config_id))

    resultados = []
    LOTE_SIZE = 500
    
    for i in range(0, len(tasks), LOTE_SIZE):
        lote = tasks[i:i+LOTE_SIZE]
        print(f"--- Procesando lote {i} a {i+len(lote)} de {len(tasks)} ---")
        
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_file = {executor.submit(process_one_jam_task, *t): t[0] for t in lote}
            for future in as_completed(future_to_file):
                try:
                    res = future.result(timeout=30)
                    if res["ok"]: 
                        resultados.append(res["summary"])
                except TimeoutError:
                    pass
                except Exception:
                    pass
        gc.collect()

    # --- ENSAMBLAJE DE LA TABLA FINAL (FORMATO ANCHO) ---
    if resultados:
        df_all = pd.DataFrame(resultados)
        df_all.to_csv(os.path.join(args.out, "resumen_presion_por_atasco.csv"), index=False)
        
        # Agrupamos por configuración
        grouped = df_all.groupby('config_id')
        df_config = pd.DataFrame()
        
        # 1. Metadatos básicos
        df_config['config_id'] = grouped.groups.keys()
        df_config['n_atascos'] = grouped.size().values
        
        # Intentar extraer metadatos del nombre de la carpeta (ej: R_2.0)
        # Si tu formato es distinto, puedes ajustar estas expresiones regulares
        def extract_meta(config_str):
            r_match = re.search(r'R_([\d\.]+)', config_str)
            return r_match.group(1) if r_match else 'NA'
            
        df_config['r_ratio_nominal'] = df_config['config_id'].apply(extract_meta)
        
        # 2. Variables de Presión (Arco, ROI, Bulk)
        variables_presion = [
            'P_bulk', 'P_bulk_B', 'P_bulk_S',
            'P_arco', 'P_arco_B', 'P_arco_S',
            'P_roi',  'P_roi_B',  'P_roi_S'
        ]
        
        # 3. Calcular Mean, Std y Sem para cada variable
        for var in variables_presion:
            # Media
            df_config[f'mean_{var}'] = grouped[var].mean().values
            # Desviación estándar entre atascos
            df_config[f'std_between_jams_{var}'] = grouped[var].std().values
            # Error estándar de la media (SEM)
            df_config[f'sem_{var}'] = grouped[var].sem().values

        # Guardar archivo final
        out_path = os.path.join(args.out, "resumen_presion_por_configuracion.csv")
        df_config.to_csv(out_path, index=False)
        print(f"Análisis completado. Archivo estructurado guardado en:\n{out_path}")

if __name__ == "__main__":
    main()