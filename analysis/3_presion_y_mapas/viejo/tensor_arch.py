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

def poly_area(coords):
    x = coords[:, 0]
    y = coords[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def obtener_vector_normal(px, py, particula_ref):
    cx, cy = particula_ref["pos"]
    if particula_ref["shape_type"] == 1: # Disco
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

def detectar_arco_primario(df_contacts, particles):
    G = nx.Graph()
    for _, row in df_contacts.iterrows():
        G.add_edge(int(row['id_a']), int(row['id_b']))
    radios = [p["r_eff"] for p in particles.values()]
    if not radios: return []
    umbral_r = (max(radios) + min(radios)) / 2.0
    big_nodes = [n for n, d in particles.items() if d["r_eff"] >= umbral_r]
    if not big_nodes: return []
    arco_candidates = [n for n in big_nodes if particles[n]["pos"][1] < 15.0]
    subgraph = G.subgraph(arco_candidates)
    if len(subgraph) == 0: return []
    try:
        largest_cc = max(nx.connected_components(subgraph), key=len)
        return list(largest_cc)
    except:
        return []

def nombre_forma(n_sides):
    if n_sides == 1: return "Disco"
    if n_sides == 3: return "Triangulo"
    if n_sides == 4: return "Cuadrado"
    if n_sides == 5: return "Pentagono"
    if n_sides == 6: return "Hexagono"
    return f"Poli{n_sides}"

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
                x, y, r, ptype = float(p[2]), float(p[3]), float(p[4]), int(p[5])
                area = np.pi * (r**2)
                particles[pid] = {"pos": (x, y), "r_eff": r, "type": ptype, "shape": shape_name, "shape_type": 1, "area": area}
            else:
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = coords.mean(axis=0)
                ptype = int(p[-1])
                r_eff = float(np.max(np.linalg.norm(coords - center, axis=1)))
                area = poly_area(coords)
                particles[pid] = {"pos": (float(center[0]), float(center[1])), "r_eff": r_eff, "coords": coords, "type": ptype, "shape": shape_name, "shape_type": n_sides, "area": area}
    return particles

def obtener_dataframe_tensores(particles, df_contacts, arco_path, dt):
    ids_arco = set(int(x) for x in arco_path)
    y_arco = [particles[pid]["pos"][1] for pid in ids_arco] if ids_arco else []
    roi_ymin = min(y_arco) if y_arco else 0
    roi_ymax = max(y_arco) + 10.0 if y_arco else 20.0
    
    for pid in particles:
        particles[pid]["stress_tensor"] = np.zeros((2, 2), dtype=float)
        
    for _, row in df_contacts.iterrows():
        id_a, id_b = int(row["id_a"]), int(row["id_b"])
        if id_a not in particles or id_b not in particles: continue
            
        px, py, fn, ft = row["px"], row["py"], row["f_norm"], row["f_tan"]
        nx_v, ny_v = obtener_vector_normal(px, py, particles[id_a])
        tx_v, ty_v = -ny_v, nx_v
        
        Fx_A = (-fn * nx_v - ft * tx_v) / dt
        Fy_A = (-fn * ny_v - ft * ty_v) / dt
        Fx_B, Fy_B = -Fx_A, -Fy_A
        
        cx_A, cy_A = particles[id_a]["pos"]
        rx_A, ry_A = px - cx_A, py - cy_A
        cx_B, cy_B = particles[id_b]["pos"]
        rx_B, ry_B = px - cx_B, py - cy_B
        
        particles[id_a]["stress_tensor"][0,0] += Fx_A * rx_A
        particles[id_a]["stress_tensor"][0,1] += Fx_A * ry_A
        particles[id_a]["stress_tensor"][1,0] += Fy_A * rx_A
        particles[id_a]["stress_tensor"][1,1] += Fy_A * ry_A
        
        particles[id_b]["stress_tensor"][0,0] += Fx_B * rx_B
        particles[id_b]["stress_tensor"][0,1] += Fx_B * ry_B
        particles[id_b]["stress_tensor"][1,0] += Fy_B * rx_B
        particles[id_b]["stress_tensor"][1,1] += Fy_B * ry_B

    radios = [p["r_eff"] for p in particles.values()]
    umbral_r = (max(radios) + min(radios)) / 2.0 if radios else 0.0
    records = []
    
    for pid, p in particles.items():
        A = p.get("area", 1.0)
        sig = p["stress_tensor"] / A if A > 0 else np.zeros((2,2))
        P = -0.5 * (sig[0,0] + sig[1,1])
        tipo = 'B' if p["r_eff"] >= umbral_r else 'S'
        
        x, y = p["pos"]
        if pid in ids_arco: region = 'arco'
        elif roi_ymin <= y <= roi_ymax: region = 'roi'
        else: region = 'bulk'
            
        records.append({
            "pid": pid,
            "pos_x": x,
            "pos_y": y,
            "r_eff": p["r_eff"],
            "shape": p["shape"],
            "region": region,
            "tipo": tipo,
            "P_presion": P,
            "tensor_xx": sig[0,0],
            "tensor_xy": sig[0,1],
            "tensor_yx": sig[1,0],
            "tensor_yy": sig[1,1],
            "area": A
        })
        
    return pd.DataFrame(records)

def extraer_metadatos_fisicos(particles, config_id):
    radios = [p["r_eff"] for p in particles.values()]
    umbral_r = (max(radios) + min(radios)) / 2.0 if radios else 0.0
    
    # Separar en grandes y chicas
    p_grandes = [p for p in particles.values() if p["r_eff"] >= umbral_r]
    p_chicas = [p for p in particles.values() if p["r_eff"] < umbral_r]
    
    forma_grande = p_grandes[0]["shape"] if p_grandes else "NA"
    forma_chica = p_chicas[0]["shape"] if p_chicas else "NA"
    r_chica = p_chicas[0]["r_eff"] if p_chicas else 0.0
    
    # Extraer Chi del nombre de la carpeta (ej. frames_Chi_0p01_W_2p0 -> 0p01)
    chi_match = re.search(r'Chi_([0-9p]+)', config_id)
    chi_val = chi_match.group(1) if chi_match else "NA"
    
    # Formatear el radio chica a 2 o 3 decimales para evitar nombres muy largos
    r_chica_str = f"{r_chica:.3f}".rstrip('0').rstrip('.')
    
    # Construir el nuevo nombre descriptivo
    # Ejemplo: G_Disco_C_Cuadrado_Chi_0p01_rC_0.5
    nuevo_nombre = f"G_{forma_grande}_C_{forma_chica}_Chi_{chi_val}_rC_{r_chica_str}"
    
    return nuevo_nombre

def process_one_jam_task(xy_file, contact_file, jam_id, config_id, dt, out_dir):
    try:
        particles = parse_xy(xy_file)
        cols = ['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan']
        df_contacts = pd.read_csv(contact_file, sep=r'\s+', names=cols, comment='#')
        arco_path = detectar_arco_primario(df_contacts, particles)
        
        if not arco_path:
            return {"ok": False, "error": f"No arco detectado"}
            
        df_tensores = obtener_dataframe_tensores(particles, df_contacts, arco_path, dt)
        
        # -------------------------------------------------------------
        # AQUI ES LA MAGIA: Nombramos la carpeta con la física real
        # -------------------------------------------------------------
        nombre_fisico_carpeta = extraer_metadatos_fisicos(particles, config_id)
        config_out_dir = os.path.join(out_dir, nombre_fisico_carpeta)
        
        os.makedirs(config_out_dir, exist_ok=True)
        
        # Guardamos el CSV
        out_csv_path = os.path.join(config_out_dir, f"atasco_tensores_{jam_id}.csv")
        df_tensores.to_csv(out_csv_path, index=False)
        
        return {"ok": True, "file_saved": out_csv_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dt", type=float, default=0.001)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    xy_files = sorted(glob.glob(os.path.join(args.dir, "**", "*.xy"), recursive=True))
    
    tasks = []
    for xy_file in xy_files:
        contact_file = xy_file.replace(".xy", ".dat").replace("atasco_", "atasco_contacts_")
        if os.path.exists(contact_file):
            jam_id = os.path.basename(xy_file).split('_')[-1].replace('.xy', '')
            config_id = os.path.basename(os.path.dirname(xy_file))
            tasks.append((xy_file, contact_file, jam_id, config_id, args.dt, args.out))

    LOTE_SIZE = 500
    for i in range(0, len(tasks), LOTE_SIZE):
        lote = tasks[i:i+LOTE_SIZE]
        print(f"--- Extrayendo tensores lote {i} a {i+len(lote)} de {len(tasks)} ---")
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_to_file = {executor.submit(process_one_jam_task, *t): t[0] for t in lote}
            for future in as_completed(future_to_file):
                try:
                    future.result(timeout=30)
                except TimeoutError: pass
                except Exception: pass
        gc.collect()

    print(f"Análisis completado. CSVs individuales guardados en: {args.out}")

if __name__ == "__main__":
    main()