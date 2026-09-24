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
import networkx as nx
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

def parse_radio_salida(sim_path, default=2.5):
    """Lee Radio_salida desde params.in en la carpeta de la simulacion
    (mismo archivo/campo que usa graficar_arco_y_fuerzas.py). Si no se
    encuentra el archivo o el campo, devuelve el valor por defecto."""
    params_file = os.path.join(sim_path, "params.in")
    r_salida = default
    try:
        with open(params_file, 'r') as f:
            for line in f:
                if 'Radio_salida:' in line:
                    r_salida = float(line.split(':')[1].split('#')[0].strip())
                    break
    except Exception:
        pass
    return r_salida


def parse_g(sim_path, default=9.8):
    """Lee 'g' desde params.in en la carpeta de la simulacion, para poder
    expresar la presion en unidades reducidas (P/g). params.in trae g con
    signo negativo (ej. 'g: -9.8', convencion de gravedad hacia abajo) ->
    devolvemos el valor absoluto."""
    params_file = os.path.join(sim_path, "params.in")
    g = default
    try:
        with open(params_file, 'r') as f:
            for line in f:
                if line.strip().startswith('g:'):
                    g = float(line.split(':')[1].split('#')[0].strip())
                    break
    except Exception:
        pass
    return abs(g) if g != 0 else default


def detectar_arco_primario(df_particles, df_contacts, r_salida):
    """Detecta el arco de atasco como el camino de costo minimo entre un
    grano apoyado en el borde izquierdo del orificio y uno apoyado en el
    borde derecho, con el costo de cada arista = 10**y_max (favorece
    fuertisimo los caminos bajos), y despues recorta de los dos extremos
    los tramos que son solo cimientos estables apoyados en el piso (no
    parte real del puente que sostiene la carga).

    Puerto 1:1 de detectar_arco_primario() en graficar_arco_y_fuerzas.py,
    para que la region 'arco' de este script coincida exactamente con lo
    que dibuja ese script de referencia. A diferencia del criterio anterior
    (componente conexa mas grande entre granos grandes con pos_y<15), este
    no distingue grano grande/chico ni usa un corte fijo de altura: el
    resultado es un puente delgado real, no todo el bloque congestionado
    cerca de la salida.
    """
    if df_particles.empty or df_contacts.empty:
        return []

    # Igual que el script de referencia: agrupamos por par de particulas,
    # sumando f_norm de los (hasta 2) puntos de contacto de un mismo par,
    # para tener UNA arista por par tocandose (no una por punto de contacto).
    valid_c = df_contacts[(df_contacts['id_a'] >= 0) & (df_contacts['id_b'] >= 0)].copy()
    if valid_c.empty:
        return []
    valid_c['pair_a'] = np.minimum(valid_c['id_a'], valid_c['id_b'])
    valid_c['pair_b'] = np.maximum(valid_c['id_a'], valid_c['id_b'])
    grouped = valid_c.groupby(['pair_a', 'pair_b'], as_index=False).agg({'f_norm': 'sum'})

    idx = df_particles.index
    G = nx.Graph()
    G.add_nodes_from(idx)
    for u, v in zip(grouped['pair_a'].to_numpy(), grouped['pair_b'].to_numpy()):
        u, v = int(u), int(v)
        if u in df_particles.index and v in df_particles.index:
            # float() explicito: pos_y viene en float32, y 10**y_max con
            # y_max~90 desborda en float32 (silencioso, da inf) pero no en
            # float64/python float.
            y_max = float(max(df_particles.at[u, 'pos_y'], df_particles.at[v, 'pos_y']))
            G.add_edge(u, v, costo_arco=10.0 ** y_max)

    r_col = 'r_eff'  # radio geometrico real, no el nominal ajustado por forma

    def es_cimiento_estable(pid, path, i):
        x = df_particles.at[pid, 'pos_x']
        y = df_particles.at[pid, 'pos_y']
        r = df_particles.at[pid, r_col]
        if abs(x) < (r_salida - 0.2):
            return False
        if (y - r) < 0.2:
            return True
        vecinos_arco = []
        if i > 0: vecinos_arco.append(path[i - 1])
        if i < len(path) - 1: vecinos_arco.append(path[i + 1])
        apoyos_inferiores = 0
        for vecino in G.neighbors(pid):
            if vecino not in vecinos_arco and df_particles.at[vecino, 'pos_y'] < (y - 0.05):
                apoyos_inferiores += 1
        return apoyos_inferiores >= 2

    def purgar_cimientos(path):
        if not path:
            return []
        iL = 0
        while iL < len(path) and es_cimiento_estable(path[iL], path, iL):
            iL += 1
        iR = len(path) - 1
        while iR >= iL and es_cimiento_estable(path[iR], path, iR):
            iR -= 1
        if iL > iR:
            return []
        return path[iL:iR + 1]

    nleft, nright = [], []
    for pid in df_particles.index:
        x = df_particles.at[pid, 'pos_x']
        y = df_particles.at[pid, 'pos_y']
        r = df_particles.at[pid, r_col]
        if (y - r) < 0.2:
            if x < 0.0:
                nleft.append(pid)
            elif x > 0.0:
                nright.append(pid)

    mejor_arco = []
    min_costo_total = float('inf')
    for l in nleft:
        for rr in nright:
            if nx.has_path(G, l, rr):
                try:
                    path = nx.shortest_path(G, source=l, target=rr, weight='costo_arco')
                    costo_path = sum(G[path[i]][path[i + 1]]['costo_arco'] for i in range(len(path) - 1))
                    if costo_path < min_costo_total:
                        min_costo_total = costo_path
                        mejor_arco = purgar_cimientos(path)
                except nx.NetworkXNoPath:
                    continue

    return mejor_arco

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

def obtener_vector_normal_poly_lado(row, lado):
    """Igual que obtener_vector_normal_poly, pero puede leer el lado A o B
    de una fila ya mergeada con sufijos (_A/_B), para poder usar el lado
    que corresponda cuando el otro lado es la pared (sin datos de geometria)."""
    px, py = row['px'], row['py']
    cx, cy = row[f'pos_x_{lado}'], row[f'pos_y_{lado}']
    coords = row[f'coords_{lado}']
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


def calcular_tensor_y_presion_vectorizado(df_particles, df_contacts, arco_path, dt, umbral_r, g=9.8):
    part_cols = df_particles[['pos_x', 'pos_y', 'shape', 'coords']]
    # how='left' en vez del inner-join por defecto: un contacto contra la
    # pared (id<0, sin fila en df_particles) ya NO se descarta entero.
    df = df_contacts.merge(part_cols, left_on='id_a', right_index=True, how='left')
    df = df.merge(part_cols, left_on='id_b', right_index=True, how='left', suffixes=('_A', '_B'))

    a_valida = df['shape_A'].notna()
    b_valida = df['shape_B'].notna()
    # Preferimos el lado A para la normal (igual que el codigo original)
    # si A es un grano real; si A es la pared, usamos B en su lugar.
    usar_A = a_valida
    usar_B = (~a_valida) & b_valida

    df['nx_v'] = np.float32(0.0)
    df['ny_v'] = np.float32(0.0)

    mask_disk_A = usar_A & (df['shape_A'] == 'Disco')
    if mask_disk_A.any():
        nx = df.loc[mask_disk_A, 'px'] - df.loc[mask_disk_A, 'pos_x_A']
        ny = df.loc[mask_disk_A, 'py'] - df.loc[mask_disk_A, 'pos_y_A']
        norma = np.hypot(nx, ny)
        valid = norma > 0
        df.loc[mask_disk_A, 'nx_v'] = np.where(valid, nx / norma, 0.0).astype(np.float32)
        df.loc[mask_disk_A, 'ny_v'] = np.where(valid, ny / norma, 0.0).astype(np.float32)

    mask_disk_B = usar_B & (df['shape_B'] == 'Disco')
    if mask_disk_B.any():
        nx = df.loc[mask_disk_B, 'px'] - df.loc[mask_disk_B, 'pos_x_B']
        ny = df.loc[mask_disk_B, 'py'] - df.loc[mask_disk_B, 'pos_y_B']
        norma = np.hypot(nx, ny)
        valid = norma > 0
        df.loc[mask_disk_B, 'nx_v'] = np.where(valid, nx / norma, 0.0).astype(np.float32)
        df.loc[mask_disk_B, 'ny_v'] = np.where(valid, ny / norma, 0.0).astype(np.float32)

    mask_poly_A = usar_A & (df['shape_A'] != 'Disco')
    if mask_poly_A.any():
        normals = df[mask_poly_A].apply(lambda r: obtener_vector_normal_poly_lado(r, 'A'), axis=1)
        df.loc[mask_poly_A, 'nx_v'] = normals.apply(lambda x: x[0]).astype(np.float32)
        df.loc[mask_poly_A, 'ny_v'] = normals.apply(lambda x: x[1]).astype(np.float32)

    mask_poly_B = usar_B & (df['shape_B'] != 'Disco')
    if mask_poly_B.any():
        normals = df[mask_poly_B].apply(lambda r: obtener_vector_normal_poly_lado(r, 'B'), axis=1)
        df.loc[mask_poly_B, 'nx_v'] = normals.apply(lambda x: x[0]).astype(np.float32)
        df.loc[mask_poly_B, 'ny_v'] = normals.apply(lambda x: x[1]).astype(np.float32)

    df['tx_v'] = -df['ny_v']
    df['ty_v'] = df['nx_v']
    df['Fx_A'] = ((-df['f_norm'] * df['nx_v'] - df['f_tan'] * df['tx_v']) / dt).astype(np.float32)
    df['Fy_A'] = ((-df['f_norm'] * df['ny_v'] - df['f_tan'] * df['ty_v']) / dt).astype(np.float32)

    # Solo sumamos S00/S11 del lado que efectivamente es un grano real
    # (si es la pared, esa contribucion queda en 0 y no se le "inventa" area).
    #
    # Cuidado con el signo: cuando la normal se calculo desde el lado A
    # (usar_A, el caso normal grano-grano), Fx_A/Fy_A es la fuerza sobre A,
    # y la reaccion de B es -Fx_A (3ra ley de Newton) -> signo -1.
    # Pero cuando A es la pared y se uso la geometria de B en su lugar
    # (usar_B), Fx_A/Fy_A calculado con esa misma formula YA ES
    # directamente la fuerza real sobre B -> no hay que invertir el signo.
    # Antes se invertia siempre, lo que daba presion con signo mal (a veces
    # negativa) en particulas tocando el piso o las paredes.
    signo_B = np.where(usar_B, 1.0, -1.0).astype(np.float32)
    df['S00_A'] = np.where(a_valida, (df['Fx_A'] * (df['px'] - df['pos_x_A'])).astype(np.float32), 0.0)
    df['S11_A'] = np.where(a_valida, (df['Fy_A'] * (df['py'] - df['pos_y_A'])).astype(np.float32), 0.0)
    df['S00_B'] = np.where(b_valida, (signo_B * df['Fx_A'] * (df['px'] - df['pos_x_B'])).astype(np.float32), 0.0)
    df['S11_B'] = np.where(b_valida, (signo_B * df['Fy_A'] * (df['py'] - df['pos_y_B'])).astype(np.float32), 0.0)

    tensor_A = df.groupby('id_a')[['S00_A', 'S11_A']].sum().rename(columns={'S00_A':'S00', 'S11_A':'S11'})
    tensor_B = df.groupby('id_b')[['S00_B', 'S11_B']].sum().rename(columns={'S00_B':'S00', 'S11_B':'S11'})
    tensor_total = tensor_A.add(tensor_B, fill_value=0)
    
    del df, tensor_A, tensor_B
    
    p_df = df_particles.join(tensor_total).fillna({'S00': 0, 'S11': 0})
    p_df['P'] = np.where(p_df['area'] > 0, -0.5 * (p_df['S00'] + p_df['S11']) / p_df['area'], 0.0)
    # Presion en unidades reducidas (P/g), para comparar directamente entre
    # configuraciones sin que la escala dependa de la aceleracion de la
    # gravedad usada en cada corrida.
    p_df['P_reducida'] = p_df['P'] / g
    
    y_arco = p_df.loc[p_df.index.isin(arco_path), 'pos_y'] if arco_path else []
    roi_ymin = y_arco.min() if len(y_arco) > 0 else 0
    roi_ymax = y_arco.max() + 10.0 if len(y_arco) > 0 else 20.0
    
    p_df['region'] = np.where(p_df.index.isin(arco_path), 'arco',
                     np.where((p_df['pos_y'] >= roi_ymin) & (p_df['pos_y'] <= roi_ymax), 'roi', 'bulk'))
    
    r_col = 'r_nominal' if 'r_nominal' in p_df.columns else 'r_eff'
    p_df['tipo'] = np.where(p_df[r_col] >= umbral_r, 'B', 'S')
    p_df['P_A'] = p_df['P'] * p_df['area']
    p_df['P_A_reducida'] = p_df['P_reducida'] * p_df['area']

    res = {}
    for region in ['arco', 'roi', 'bulk']:
        mask_reg = p_df['region'] == region
        sub_df = p_df[mask_reg]
        
        # Guardamos numeradores y denominadores totales de la región
        res[f"SumP_{region}"] = sub_df['P_A'].sum()
        res[f"SumP_reducida_{region}"] = sub_df['P_A_reducida'].sum()
        res[f"Area_{region}"] = sub_df['area'].sum()
        
        for tipo in ['B', 'S']:
            mask_tipo = sub_df['tipo'] == tipo
            # Guardamos numeradores y denominadores por componente
            res[f"SumP_{region}_{tipo}"] = sub_df.loc[mask_tipo, 'P_A'].sum()
            res[f"SumP_reducida_{region}_{tipo}"] = sub_df.loc[mask_tipo, 'P_A_reducida'].sum()
            res[f"Area_{region}_{tipo}"] = sub_df.loc[mask_tipo, 'area'].sum()

    # Detalle por particula (para poder guardar la presion individual de
    # cada grano, ademas del resumen agregado por region de arriba).
    particulas = p_df[['pos_x', 'pos_y', 'shape', 'tipo', 'region', 'area', 'P', 'P_reducida', 'coords']].reset_index()
    # 'coords' es None para discos, o un array (N,2) de vertices absolutos
    # para poligonos -> lo serializamos a JSON para que sobreviva el CSV.
    # Sin esto, graficar_presion_atasco.py no tiene forma de distinguir un
    # cuadrado/pentagono/triangulo de un circulo equivalente al dibujar.
    particulas['coords'] = particulas['coords'].apply(
        lambda c: json.dumps(np.asarray(c, dtype=float).round(5).tolist()) if c is not None else ''
    )

    del p_df
    return res, particulas

def worker_wrapper(args):
    return process_one_jam_task(*args)

def process_one_jam_task(xy_file, contact_file, jam_id, config_id, dt, r_large_m, r_small_m, sides_large_m, sides_small_m, master_chi, sim_path):
    try:
        particles = parse_xy(xy_file)
        df_particles = pd.DataFrame.from_dict(particles, orient='index')
        df_particles.index.name = 'id'
        
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
        
        r_salida = parse_radio_salida(sim_path)
        g_abs = parse_g(sim_path)
        arco_path = detectar_arco_primario(df_particles, df_contacts, r_salida)
        if not arco_path:
            return {"ok": False, "error": "No arco detectado"}
            
        summary, particulas = calcular_tensor_y_presion_vectorizado(df_particles, df_contacts, arco_path, dt, umbral_r, g=g_abs)
        
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

        particulas['jam_id'] = jam_id
        particulas['config_id'] = config_id
        particulas['sim_path'] = sim_path
        particulas['chi'] = chi_val
        
        del df_particles, df_contacts
        return {"ok": True, "summary": summary, "particulas": particulas}
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

def write_particulas_buffer(buffer, particulas_csv_path):
    if not buffer: return
    df_lote = pd.concat(buffer, ignore_index=True)
    meta_cols = ['config_id', 'sim_path', 'jam_id', 'chi', 'id']
    other_cols = [c for c in df_lote.columns if c not in meta_cols]
    meta_cols = [c for c in meta_cols if c in df_lote.columns]
    df_lote = df_lote[meta_cols + other_cols]
    escribir_header = not os.path.exists(particulas_csv_path)
    df_lote.to_csv(particulas_csv_path, mode='a', index=False, header=escribir_header)
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
            
            abs_xy = os.path.abspath(os.path.normpath(xy_file))
            sim_path = os.path.dirname(os.path.dirname(abs_xy)) # Sube 2 niveles para llegar a la raíz de la simulación
            
            config_info = master_dict.get(sim_path)
            
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
    particulas_csv_path = os.path.join(args.out, "presion_por_particula.csv")

    if os.path.exists(atasco_csv_path):
        os.remove(atasco_csv_path)
    if os.path.exists(particulas_csv_path):
        os.remove(particulas_csv_path)

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
        
        path_abs = os.path.abspath(os.path.normpath(str(path_val)))
        master_dict[path_abs] = info
        
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
    FLUSH_SIZE_PART = 200_000  # filas de particulas, no cantidad de atascos
    results_buffer = []
    particulas_buffer = []
    particulas_buffer_len = 0
    processed_count = 0

    tareas_gen = generar_tareas(xy_files, master_dict, args.dt)

    with mp.Pool(processes=args.workers, maxtasksperchild=50) as pool:
        for res in pool.imap_unordered(worker_wrapper, tareas_gen, chunksize=10):
            processed_count += 1
            if res["ok"]:
                results_buffer.append(res["summary"])
                particulas_buffer.append(res["particulas"])
                particulas_buffer_len += len(res["particulas"])
            
            if len(results_buffer) >= FLUSH_SIZE:
                write_buffer_to_csv(results_buffer, atasco_csv_path)
                results_buffer.clear()
                gc.collect() 

            if particulas_buffer_len >= FLUSH_SIZE_PART:
                write_particulas_buffer(particulas_buffer, particulas_csv_path)
                particulas_buffer.clear()
                particulas_buffer_len = 0
                gc.collect()
            
            if processed_count % 1000 == 0:
                print(f"Procesados {processed_count} de {total_estimado}...")

    if results_buffer:
        write_buffer_to_csv(results_buffer, atasco_csv_path)
        results_buffer.clear()

    if particulas_buffer:
        write_particulas_buffer(particulas_buffer, particulas_csv_path)
        particulas_buffer.clear()

    print("\n--- Procesamiento finalizado. Calculando promedios... ---")

    if os.path.exists(atasco_csv_path):
        df_all = pd.read_csv(atasco_csv_path)
        group_cols = ['forma_grande', 'forma_chica', 'chi', 'r_chica', 'config_id', 'sim_path']
        grouped = df_all.groupby(group_cols, dropna=False)
        df_config = grouped.size().reset_index(name='n_atascos')
        
        variables_sumar = [
            'SumP_bulk', 'Area_bulk', 'SumP_bulk_B', 'Area_bulk_B', 'SumP_bulk_S', 'Area_bulk_S',
            'SumP_arco', 'Area_arco', 'SumP_arco_B', 'Area_arco_B', 'SumP_arco_S', 'Area_arco_S',
            'SumP_roi', 'Area_roi', 'SumP_roi_B', 'Area_roi_B', 'SumP_roi_S', 'Area_roi_S',
            'SumP_reducida_bulk', 'SumP_reducida_bulk_B', 'SumP_reducida_bulk_S',
            'SumP_reducida_arco', 'SumP_reducida_arco_B', 'SumP_reducida_arco_S',
            'SumP_reducida_roi', 'SumP_reducida_roi_B', 'SumP_reducida_roi_S'
        ]
        cols_to_agg = [var for var in variables_sumar if var in df_all.columns]
        
        if cols_to_agg:
            df_sums = grouped[cols_to_agg].sum().reset_index(drop=True)
            df_config = pd.concat([df_config, df_sums], axis=1)
            
            # Calculamos las presiones macroscópicas dividiendo la fuerza total entre el área total del grupo
            for reg in ['bulk', 'arco', 'roi']:
                df_config[f'mean_P_{reg}'] = df_config[f'SumP_{reg}'] / df_config[f'Area_{reg}']
                df_config[f'mean_P_reducida_{reg}'] = df_config[f'SumP_reducida_{reg}'] / df_config[f'Area_{reg}']
                for t in ['B', 'S']:
                    # Si el área acumulada es 0, devolverá NaN
                    df_config[f'mean_P_{reg}_{t}'] = df_config[f'SumP_{reg}_{t}'] / df_config[f'Area_{reg}_{t}']
                    df_config[f'mean_P_reducida_{reg}_{t}'] = df_config[f'SumP_reducida_{reg}_{t}'] / df_config[f'Area_{reg}_{t}']
            
            df_config = df_config.drop(columns=variables_sumar)
            
            df_config.to_csv(config_csv_path, index=False)
            print(f"Finalizado - Archivo definitivo guardado en: {config_csv_path}")

if __name__ == "__main__":
    mp.freeze_support() 
    main()