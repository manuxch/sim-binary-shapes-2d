#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
force_arch_v3.py

Análisis de fuerza normal promedio en bulk, arco y ROI, con visualización espacial.

Puntos principales:
- Mantiene la detección de arcos con networkx.
- Procesa por grupos de configuración para evitar saturar RAM.
- Resume fuerza normal por atasco y luego por configuración.
- Calcula un ROI dinámico: toma TODO el rango en X, acotado en Y por el arco.
- Reemplaza de forma inteligente la categoría "General" usando directamente el hash de la simulación.
- Guarda el número de lados de las partículas grandes y chicas extraídas de grain_json.
- **CORREGIDO**: Clasifica automáticamente las partículas dinámicamente por su radio máximo (B: Grande, S: Chica) para dar soporte a sistemas Disco-Disco.
- Discrimina y suma fuerzas para los tipos de contacto BB, BS y SS en todas las regiones.
- Opcionalmente guarda muestras de fuerzas normales para violin plots (--save-force-samples).
- Opcionalmente genera imágenes espaciales clasificando partículas (--save-images).

Salidas:
- resumen_fuerza_normal_por_atasco.csv
- resumen_fuerza_normal_por_configuracion.csv
- errores_procesamiento.csv
- muestras_fuerza_normal.csv  (solo si se usa --save-force-samples)
- imágenes en carpeta 'img_debug' (solo si se usa --save-images)
"""

import os
import re
import glob
import json
import gc
import hashlib
import argparse
import multiprocessing as mp
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

import sys
import numpy as np
import pandas as pd
import networkx as nx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # especies.py vive en analysis/
from especies import especie_por_tipo, area_grano  # noqa: E402

import matplotlib as mpl
mpl.use('Agg') 
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as pltPolygon


# =============================================================================
# UTILIDADES GENERALES
# =============================================================================

def nominalizar_ratio(x, ndigits=3):
    if x is None: return np.nan
    try:
        if pd.isna(x): return np.nan
    except TypeError: pass
    return round(float(x), ndigits)

def shape_name_from_sides(sides):
    try: sides = int(sides)
    except Exception: return "Desconocido"
    return {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}.get(sides, f"Pol{sides}")

def get_geometry_label_from_row(row):
    # Intento 1: Tratar de extraerlo del JSON de granos
    if "grain_json" in row and pd.notnull(row["grain_json"]):
        try:
            grains = json.loads(row["grain_json"])
            if grains:
                # CORREGIDO: ordenar por NUMERO DE LADOS (sides), no por radio.
                # Cerca de area_ratio~0.8 el disco chico puede tener un radio
                # igual o levemente MAYOR al de la especie grande (porque
                # "radius" se define distinto para un poligono que para un
                # disco), lo que invertia el orden ("Disco-Cuad" en vez de
                # "Cuad-Disco"). sides=1 (disco) es siempre la especie
                # aditivo/chica conceptualmente, sin importar su radio actual.
                grains = sorted(grains, key=lambda g: float(g.get("sides", 1)), reverse=True)
                names = [shape_name_from_sides(g.get("sides", -1)) for g in grains]
                return names[0] if len(names) == 1 else "-".join(names)
        except Exception:
            pass
            
    # Intento 2: Usar la columna system_type si existe
    if "system_type" in row and pd.notnull(row["system_type"]):
        return str(row["system_type"]).upper()
        
    return "Desconocido"


def _partir_carpeta_por_chi(carpeta):
    """Separa la carpeta hoja de una simulacion en (prefijo, resto) alrededor
    de 'Chi_<valor>'. Soporta tanto 'Ratio_0p1_Chi_0p0_W_2p0' como
    'Chi_0p0_W_2p0' (sin prefijo Ratio_, usado en algunas barridas
    Disco-Disco donde el ratio=1.0 no se codifica en el nombre)."""
    m = re.search(r'(?:^|_)Chi_[^_]+', carpeta)
    if not m:
        return carpeta, None
    prefijo = carpeta[:m.start()].rstrip("_")
    resto = carpeta[m.end():].lstrip("_")
    return prefijo, resto


def _claves_familia_ratio(row):
    """(clave_estricta, clave_amplia) para emparejar filas 'hermanas' de la
    misma barrida fisica, sin depender de 'category' (puede ser "General",
    sin informacion util) ni de area_ratio_nominal/r_ratio_nominal (quedan
    en un valor centinela 1.0 en filas mono-especie, sin segunda especie).
    clave_estricta: familia + ratio + ancho de salida (W).
    clave_amplia:   familia + ratio solamente (ignora W) - fallback para
                     sub-experimentos que barren W a chi fijo, donde no hay
                     otra fila con el mismo ancho para emparejar."""
    cat = str(row.get("category", "")).strip()
    familia = cat if cat and cat.lower() != "general" else None

    path = str(row.get("path", "")).rstrip("/")
    carpeta_hoja = os.path.basename(path) if path else ""
    if familia is None:
        familia = os.path.basename(os.path.dirname(path)) if path else cat

    prefijo, resto = _partir_carpeta_por_chi(carpeta_hoja)
    if resto is None:
        return f"{familia}::{carpeta_hoja}", f"{familia}::{carpeta_hoja}"
    return f"{familia}::{prefijo}__{resto}", f"{familia}::{prefijo}"


def reparar_geometria_mono_especie(df):
    """Corrige filas mono-especie (chi=0.0 o chi=1.0: grain_json con una sola
    especie declarada, geometry_label sin guion, ej. "Cuad" en vez de
    "Cuad-Disco") copiando geometry_label, sides_large, sides_small,
    area_ratio_nominal y r_ratio_nominal de una fila hermana real de la
    misma barrida fisica (misma familia + mismo ratio, derivados del path).
    area_ratio/r_ratio (los MEDIDOS, no el nominal) se dejan en NaN: no
    tienen sentido fisico en una fila sin segunda especie, y dejarlos en el
    centinela 1.0 ensuciaria area_ratio_real_min/max en
    make_configuration_summary(). Debe llamarse ANTES de reemplazar
    category=="General" por sim_hash (ver select_simulations), porque ese
    reemplazo destruye la pista que esta funcion necesita para encontrar
    hermanas."""
    if "geometry_label" not in df.columns or "path" not in df.columns:
        return df

    df = df.copy()
    claves = df.apply(_claves_familia_ratio, axis=1)
    df["_key_estricta"] = claves.apply(lambda t: t[0])
    df["_key_amplia"] = claves.apply(lambda t: t[1])

    sin_guion = ~df["geometry_label"].astype(str).str.contains("-", na=False)
    if not sin_guion.any():
        return df.drop(columns=["_key_estricta", "_key_amplia"])

    cols_copiar = [c for c in ["geometry_label", "sides_large", "sides_small",
                                 "area_ratio_nominal", "r_ratio_nominal"] if c in df.columns]

    buenas_e = (df[~sin_guion].drop_duplicates(subset=["_key_estricta"])
                .set_index("_key_estricta")[cols_copiar])
    buenas_a = (df[~sin_guion].drop_duplicates(subset=["_key_amplia"])
                .set_index("_key_amplia")[cols_copiar])

    sin_resolver = []
    for idx in df[sin_guion].index:
        ke, ka = df.loc[idx, "_key_estricta"], df.loc[idx, "_key_amplia"]
        if ke in buenas_e.index:
            df.loc[idx, cols_copiar] = buenas_e.loc[ke].values
        elif ka in buenas_a.index:
            df.loc[idx, cols_copiar] = buenas_a.loc[ka].values
        else:
            sin_resolver.append(idx)
        for c in ["area_ratio", "r_ratio"]:
            if c in df.columns:
                df.loc[idx, c] = np.nan

    if sin_resolver:
        print(f"[!] geometry_label mono-especie sin fila hermana encontrada, "
              f"indices: {sin_resolver} (revisar el patron de carpeta a mano)")

    return df.drop(columns=["_key_estricta", "_key_amplia"])

def stable_seed_from_text(text):
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


# =============================================================================
# PARSEADORES
# =============================================================================

def parse_params(filename):
    params = {"Radio_silo": 10.25, "Radio_salida": 2.5}
    if not os.path.exists(filename): return params
    try:
        with open(filename, "r") as f:
            for line in f:
                line_clean = line.split("#")[0].strip()
                if "Radio_silo:" in line_clean:
                    try: params["Radio_silo"] = float(line_clean.split(":")[1].strip())
                    except Exception: pass
                elif "Radio_salida:" in line_clean:
                    try: params["Radio_salida"] = float(line_clean.split(":")[1].strip())
                    except Exception: pass
    except Exception: pass
    return params

def parse_xy(filename):
    particles = {}
    with open(filename, "r") as f:
        for line in f:
            p = line.split()
            if not p: continue
            pid = int(p[0])
            if pid < 0: continue
            
            n_sides = int(p[1]) # Leemos los lados directamente del archivo .xy
            
            if n_sides == 1:
                x, y, r, ptype = float(p[2]), float(p[3]), float(p[4]), int(p[5])
                # Agregamos "sides": 1
                particles[pid] = {"pos": (x, y), "r_eff": r, "type": ptype, "shape": "Disco", "sides": 1}
            else:
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = coords.mean(axis=0)
                ptype = int(p[-1])
                r_eff = float(np.max(np.linalg.norm(coords - center, axis=1)))
                # Agregamos "sides": n_sides
                particles[pid] = {"pos": (float(center[0]), float(center[1])), "r_eff": r_eff, "coords": coords, "type": ptype, "shape": "Poligono", "sides": n_sides}
    return particles

def obtener_radio(p_data):
    return float(p_data["r_eff"])

def read_contacts(filename):
    cols = ["id_a", "id_b", "px", "py", "f_norm", "f_tan"]
    try:
        df = pd.read_csv(filename, sep=r"\s+", comment="#", header=None, usecols=[0, 1, 2, 3, 4, 5], names=cols)
    except (pd.errors.EmptyDataError, ValueError): return pd.DataFrame(columns=cols)
    if df.empty: return df
    df["id_a"] = df["id_a"].astype(np.int64)
    df["id_b"] = df["id_b"].astype(np.int64)
    df = df[(df["id_a"] > 0) & (df["id_b"] > 0)].copy()
    if df.empty: return df
    df["pair_a"] = np.minimum(df["id_a"].values, df["id_b"].values)
    df["pair_b"] = np.maximum(df["id_a"].values, df["id_b"].values)
    return df


# =============================================================================
# DETECCION DE ARCOS
# =============================================================================

def es_cimiento_estable(pid, particles, G, path, idx, r_salida):
    p = particles[pid]
    x, y = p["pos"]
    r = obtener_radio(p)
    if abs(x) < (r_salida - 0.2): return False
    if (y - r) < 0.2: return True
    vecinos_arco = []
    if idx > 0: vecinos_arco.append(path[idx - 1])
    if idx < len(path) - 1: vecinos_arco.append(path[idx + 1])
    apoyos_inferiores = 0
    for vecino in G.neighbors(pid):
        if vecino in vecinos_arco: continue
        y_vecino = particles[vecino]["pos"][1]
        if y_vecino < (y - 0.05): apoyos_inferiores += 1
    return apoyos_inferiores >= 2

def purgar_cimientos(path, particles, G, r_salida):
    if not path: return []
    iL = 0
    while iL < len(path) and es_cimiento_estable(path[iL], particles, G, path, iL, r_salida): iL += 1
    iR = len(path) - 1
    while iR >= iL and es_cimiento_estable(path[iR], particles, G, path, iR, r_salida): iR -= 1
    if iL > iR: return []
    return path[iL:iR + 1]

def detectar_arco_primario(G, particles, params):
    r_salida = params.get("Radio_salida", 2.5)
    nleft, nright = [], []
    for pid, data in particles.items():
        r = obtener_radio(data)
        x, y = data["pos"]
        if (y - r) < 0.2:
            if x < 0.0: nleft.append(pid)
            elif x > 0.0: nright.append(pid)
    mejor_arco = []
    min_costo_total = float("inf")
    for left_id in nleft:
        for right_id in nright:
            if not nx.has_path(G, left_id, right_id): continue
            try:
                path = nx.shortest_path(G, source=left_id, target=right_id, weight="costo_arco")
                costo_path = sum(G[path[i]][path[i + 1]]["costo_arco"] for i in range(len(path) - 1))
                if costo_path < min_costo_total:
                    min_costo_total = costo_path
                    mejor_arco = purgar_cimientos(path, particles, G, r_salida)
            except nx.NetworkXNoPath: continue
    return mejor_arco


# =============================================================================
# CONTACTOS, RESUMEN Y MUESTREO
# =============================================================================

def aggregate_contacts_for_graph(df_contacts, particles):
    if df_contacts.empty: return pd.DataFrame()
    valid_ids = set(particles.keys())
    df = df_contacts[df_contacts["pair_a"].isin(valid_ids) & df_contacts["pair_b"].isin(valid_ids)].copy()
    if df.empty: return pd.DataFrame()
    df["f_tan_abs"] = df["f_tan"].abs()
    grouped = df.groupby(["pair_a", "pair_b"], as_index=False).agg(px=("px", "mean"), py=("py", "mean"), f_norm=("f_norm", "sum"), f_tan=("f_tan_abs", "sum"))
    return grouped

def build_contact_graph(grouped_contacts, particles):
    G = nx.Graph()
    for pid, attr in particles.items(): G.add_node(pid, **attr)
    for _, row in grouped_contacts.iterrows():
        u, v = int(row["pair_a"]), int(row["pair_b"])
        if u not in particles or v not in particles: continue
        y_max = max(particles[u]["pos"][1], particles[v]["pos"][1])
        costo = 10.0 ** min(float(y_max), 100.0)
        G.add_edge(u, v, weight=float(row["f_norm"]), costo_arco=costo)
    return G

def prepare_force_dataset(df_contacts, particles, contact_mode="pair"):
    valid_ids = set(particles.keys())
    df = df_contacts[df_contacts["pair_a"].isin(valid_ids) & df_contacts["pair_b"].isin(valid_ids)].copy()
    if df.empty: return df
    df["f_tan_abs"] = df["f_tan"].abs()
    if contact_mode == "point":
        out = df[["pair_a", "pair_b", "f_norm", "f_tan_abs", "px", "py"]].copy().rename(columns={"pair_a": "id_a", "pair_b": "id_b", "f_tan_abs": "f_tan"})
    elif contact_mode == "pair":
        out = df.groupby(["pair_a", "pair_b"], as_index=False).agg(f_norm=("f_norm", "sum"), f_tan=("f_tan_abs", "sum"), px=("px", "mean"), py=("py", "mean")).rename(columns={"pair_a": "id_a", "pair_b": "id_b"})
    out["id_a"] = out["id_a"].astype(np.int64)
    out["id_b"] = out["id_b"].astype(np.int64)
    out["f_norm"] = out["f_norm"].astype(float)
    out["f_tan"] = out["f_tan"].astype(float)
    return out

def mean_or_nan(values):
    values = np.asarray(values, dtype=float)
    return np.nan if values.size == 0 else float(np.nanmean(values))

def std_or_nan(values):
    values = np.asarray(values, dtype=float)
    return np.nan if values.size <= 1 else float(np.nanstd(values, ddof=1))

def summarize_fn_one_jam(df_forces, arco_path, particles, chi=None):
    ids_arco = set(int(x) for x in arco_path)
    
    # Grande/chico ('B'/'S') por especie: columna 'type' del .xy, sin umbral
    # de radio (ver analysis/especies.py). El umbral anterior, en el punto
    # medio de los circunradios, clasificaba mal mezclas de formas: p. ej. un
    # cuadrado chico de igual area con ratio 0.8 tiene circunradio 1.12 r_grande
    # y quedaba como 'B'. df_forces ya viene sin contactos con paredes.
    ids = list(particles)
    especie = especie_por_tipo([particles[i]["type"] for i in ids],
                               [area_grano(particles[i]) for i in ids], chi)
    tipo_grano = {i: especie[particles[i]["type"]] for i in ids}
    df_forces['tipo_a'] = df_forces['id_a'].map(tipo_grano).fillna('S')
    df_forces['tipo_b'] = df_forces['id_b'].map(tipo_grano).fillna('S')
    df_forces['tipo_contacto'] = df_forces[['tipo_a', 'tipo_b']].apply(lambda x: "".join(sorted(x)), axis=1)

    f_norm = df_forces["f_norm"].to_numpy(dtype=float)
    f_tan = df_forces["f_tan"].to_numpy(dtype=float)
    py = df_forces["py"].to_numpy(dtype=float)
    tipo_contacto = df_forces["tipo_contacto"].to_numpy()
    
    # NUEVO: Extraemos los arreglos de IDs para contar partículas únicas
    id_a_arr = df_forces["id_a"].to_numpy()
    id_b_arr = df_forces["id_b"].to_numpy()
    
    in_a = df_forces["id_a"].isin(ids_arco).to_numpy()
    in_b = df_forces["id_b"].isin(ids_arco).to_numpy()

    mask_arco = in_a & in_b

    y_arco = [particles[pid]["pos"][1] for pid in ids_arco if pid in particles]

    if y_arco:
        ymin, ymax = min(y_arco), max(y_arco)
        mask_roi = (py >= ymin) & (py <= ymax) & ~(in_a | in_b)
    else:
        ymin, ymax = np.nan, np.nan
        mask_roi = np.zeros(len(df_forces), dtype=bool)
        
    mask_bulk = ~mask_arco & ~mask_roi
    
    # Función de ayuda para calcular los estadísticos de cada región
    def calc_stats(mask, prefix):
        fn = f_norm[mask]
        ft = f_tan[mask]
        n = int(fn.size) # n es el número de contactos
        
        # NUEVO: Calculamos cuántas partículas únicas participan en estos contactos
        if n > 0:
            ids_involucrados = np.concatenate([id_a_arr[mask], id_b_arr[mask]])
            n_particulas = len(np.unique(ids_involucrados))
        else:
            n_particulas = 0

        d = {
            f"N_contactos_{prefix}": n,
            f"N_particulas_{prefix}": n_particulas, # NUEVO: Guardamos el número de partículas
            f"mean_Fn_{prefix}": mean_or_nan(fn),
            f"std_Fn_{prefix}": std_or_nan(fn),
            f"mean_Ft_{prefix}": mean_or_nan(ft),
            f"std_Ft_{prefix}": std_or_nan(ft),
        }
        if prefix == 'roi':
            d[f"sem_Fn_roi"] = float(np.nanstd(fn, ddof=1) / np.sqrt(n)) if n > 1 else np.nan
            d[f"sem_Ft_roi"] = float(np.nanstd(ft, ddof=1) / np.sqrt(n)) if n > 1 else np.nan
        
        # Subdivisión Geométrica (BB, BS, SS)
        tc = tipo_contacto[mask]
        id_a_masked = id_a_arr[mask]
        id_b_masked = id_b_arr[mask]
        for tipo in ['BB', 'BS', 'SS']:
            mask_tipo = (tc == tipo)
            fn_tipo = fn[mask_tipo]
            n_tipo = int(fn_tipo.size)

            # NUEVO: partículas distintas detrás de este tipo de contacto en
            # esta región. Un N_contactos alto no implica muchas partículas
            # independientes: puede venir de pocas partículas repitiendo
            # contacto en muchos atascos (pseudo-replicación).
            if n_tipo > 0:
                n_particulas_tipo = len(np.unique(np.concatenate([id_a_masked[mask_tipo], id_b_masked[mask_tipo]])))
            else:
                n_particulas_tipo = 0

            d[f"N_contactos_{prefix}_{tipo}"] = n_tipo
            d[f"N_particulas_{prefix}_{tipo}"] = n_particulas_tipo
            d[f"f_norm_{prefix}_{tipo}"] = float(np.sum(fn_tipo)) if n_tipo > 0 else 0.0
            d[f"mean_Fn_{prefix}_{tipo}"] = mean_or_nan(fn_tipo)
            d[f"std_Fn_{prefix}_{tipo}"] = std_or_nan(fn_tipo)
            d[f"contrib_mean_Fn_{prefix}_{tipo}"] = float(np.sum(fn_tipo)) / n if n > 0 else 0.0

        return d

    res = {
        "roi_xmin": np.nan, "roi_xmax": np.nan, 
        "roi_ymin": float(ymin) if pd.notnull(ymin) else np.nan, 
        "roi_ymax": float(ymax) if pd.notnull(ymax) else np.nan
    }
    
    res.update(calc_stats(mask_bulk, 'bulk'))
    res.update(calc_stats(mask_arco, 'arco'))
    res.update(calc_stats(mask_roi, 'roi'))

    return res

def sample_force_values(df_forces, arco_path, sim_row, jam_id, sample_cfg):
    ids_arco = set(int(x) for x in arco_path)
    f_norm = df_forces["f_norm"].to_numpy(dtype=float)
    f_tan = df_forces["f_tan"].to_numpy(dtype=float) 
    
    # NUEVO: Pasamos el tipo de contacto a los violines
    tipo_contacto = df_forces.get("tipo_contacto", pd.Series(["unknown"]*len(df_forces))).to_numpy()
    
    in_a = df_forces["id_a"].isin(ids_arco).to_numpy()
    in_b = df_forces["id_b"].isin(ids_arco).to_numpy()
    mask_arco = in_a & in_b

    idx_bulk = np.arange(len(df_forces))
    idx_arco = np.where(mask_arco)[0]

    bulk_sample_per_jam = int(sample_cfg.get("bulk_sample_per_jam", 200))
    arco_sample_per_jam = int(sample_cfg.get("arco_sample_per_jam", 0))
    sample_seed = int(sample_cfg.get("sample_seed", 12345))

    seed_text = f"{sim_row.get('sim_hash', '')}_{jam_id}_{sample_seed}"
    rng = np.random.default_rng(stable_seed_from_text(seed_text))

    if bulk_sample_per_jam > 0 and len(idx_bulk) > bulk_sample_per_jam:
        idx_bulk = rng.choice(idx_bulk, size=bulk_sample_per_jam, replace=False)

    if arco_sample_per_jam > 0 and len(idx_arco) > arco_sample_per_jam:
        idx_arco = rng.choice(idx_arco, size=arco_sample_per_jam, replace=False)

    meta = {col: sim_row[col] for col in [
        "sim_hash", "config_hash", "category", "system_type",
        "geometry_label", "chi", "area_ratio", "area_ratio_nominal",
        "r_ratio", "r_ratio_nominal", "r_small", "area_small", "tirada",
        "sides_large", "sides_small"
    ] if col in sim_row}

    rows = []
    for i in idx_bulk:
        row = dict(meta)
        row["Atasco_ID"] = jam_id
        row["grupo"] = "bulk"
        row["f_norm"] = float(f_norm[i])
        row["f_tan"] = float(f_tan[i]) 
        row["tipo_contacto"] = str(tipo_contacto[i])
        rows.append(row)

    for i in idx_arco:
        row = dict(meta)
        row["Atasco_ID"] = jam_id
        row["grupo"] = "arco"
        row["f_norm"] = float(f_norm[i])
        row["f_tan"] = float(f_tan[i]) 
        row["tipo_contacto"] = str(tipo_contacto[i])
        rows.append(row)

    return rows

# =============================================================================
# VISUALIZACIÓN ESPACIAL (MATPLOTLIB)
# =============================================================================

def draw_jam_visualization(particles, arco_path, ymin, ymax, params, save_path):
    r_silo = params.get('Radio_silo', 10.25)
    r_salida = params.get('Radio_salida', 2.5)
    
    y_coords = [p['pos'][1] for p in particles.values()]
    y_max_plot = max(y_coords) + 2 if y_coords else 20
    y_min_plot = -2                 
    
    ratio = (y_max_plot - y_min_plot) / (r_silo * 2)
    fig, ax = plt.subplots(figsize=(8, 8 * ratio))
    
    ids_arco = set(arco_path)
    
    for pid, p in particles.items():
        x, y = p['pos']
        fill_color = '#e0e0e0'  
        edge_color = '#b0b0b0'
        lw = 0.5
        alpha = 1.0
        z = 1
        
        if pid in ids_arco:
            fill_color = 'orange' if p['type'] == 0 else 'lightgreen'
            edge_color = 'blue'
            lw = 2.0
            z = 3
        elif pd.notnull(ymin) and pd.notnull(ymax) and (ymin <= y <= ymax):
            fill_color = '#add8e6'  
            edge_color = '#4682b4'  
            lw = 1.0
            z = 2
            
        if p['shape'] == 'Disco':
            ax.add_patch(Circle((x, y), p['r_eff'], facecolor=fill_color, edgecolor=edge_color, lw=lw, alpha=alpha, zorder=z))
        else:
            if 'coords' in p:
                ax.add_patch(pltPolygon(p['coords'], facecolor=fill_color, edgecolor=edge_color, lw=lw, alpha=alpha, zorder=z))

    if arco_path and len(arco_path) > 1:
        cx = [particles[pid]['pos'][0] for pid in arco_path]
        cy = [particles[pid]['pos'][1] for pid in arco_path]
        ax.plot(cx, cy, color='blue', lw=3, zorder=4, alpha=0.7)

    ax.plot([-r_silo, -r_silo], [0, y_max_plot], color='black', lw=2, zorder=5)
    ax.plot([r_silo, r_silo], [0, y_max_plot], color='black', lw=2, zorder=5)
    ax.plot([-r_silo, -r_salida], [0, 0], color='black', lw=4, zorder=5)
    ax.plot([r_salida, r_silo], [0, 0], color='black', lw=4, zorder=5)

    if pd.notnull(ymin) and pd.notnull(ymax):
        ax.axhline(ymin, color='blue', linestyle='--', alpha=0.3, zorder=0)
        ax.axhline(ymax, color='blue', linestyle='--', alpha=0.3, zorder=0)

    ax.set_xlim(-r_silo - 1, r_silo + 1)
    ax.set_ylim(y_min_plot, y_max_plot)
    ax.set_aspect('equal')
    ax.axis('off')

    fig.savefig(save_path, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)

# =============================================================================
# PROCESAMIENTO DE ATASCOS
# =============================================================================

def extract_jam_id(xy_file):
    m = re.search(r"atasco_(\d+)\.xy$", os.path.basename(xy_file))
    return m.group(1) if m else None

def process_one_jam_task(task):
    xy_file = task["xy_file"]
    sim_row = task["sim_row"]
    contact_mode = task["contact_mode"]
    jam_id = extract_jam_id(xy_file)
    if jam_id is None: return {"ok": False, "xy_file": xy_file, "error": "No se pudo extraer Atasco_ID"}

    sim_path = sim_row["path"]
    params = parse_params(os.path.join(sim_path, "params.in"))
    contacts_file = os.path.join(os.path.dirname(xy_file), f"atasco_contacts_{jam_id}.dat")

    if not os.path.exists(contacts_file): return {"ok": False, "xy_file": xy_file, "error": "No existe archivo de contactos"}

    try:
        particles = parse_xy(xy_file)
        if not particles: return {"ok": False, "xy_file": xy_file, "error": "Sin particulas validas"}
        raw_contacts = read_contacts(contacts_file)
        if raw_contacts.empty: return {"ok": False, "xy_file": xy_file, "error": "Sin contactos"}
        grouped_graph = aggregate_contacts_for_graph(raw_contacts, particles)
        if grouped_graph.empty: return {"ok": False, "xy_file": xy_file, "error": "Sin grafo"}
        G = build_contact_graph(grouped_graph, particles)
        arco_path = detectar_arco_primario(G, particles, params)
        if not arco_path: return {"ok": False, "xy_file": xy_file, "error": "No se detecto arco"}
        df_forces = prepare_force_dataset(raw_contacts, particles, contact_mode=contact_mode)
        
        summary = summarize_fn_one_jam(df_forces, arco_path, particles, chi=sim_row.get("chi"))
        for col, value in sim_row.items():
            if col != "path": summary[col] = value
        summary["Atasco_ID"] = jam_id
        summary["contact_mode"] = contact_mode
        summary["n_particulas_arco"] = int(len(arco_path))
        summary["arco_ids"] = json.dumps([int(x) for x in arco_path])
        summary["xy_file"] = xy_file

        samples = None
        if task.get("save_force_samples", False):
            samples = sample_force_values(df_forces, arco_path, sim_row, jam_id, task.get("sample_cfg", {}))

        if task.get("save_images", False):
            img_dir = os.path.join(os.path.dirname(xy_file), "img_debug")
            os.makedirs(img_dir, exist_ok=True)
            img_path = os.path.join(img_dir, f"espacial_{jam_id}.png")
            draw_jam_visualization(particles, arco_path, summary['roi_ymin'], summary['roi_ymax'], params, img_path)

        return {"ok": True, "summary": summary, "samples": samples, "xy_file": xy_file}
    except Exception as e:
        return {"ok": False, "xy_file": xy_file, "error": str(e)}


# =============================================================================
# RECORRIDO DE SIMULACIONES Y RESUMENES
# =============================================================================

def find_frames_dir(sim_row):
    sim_path = sim_row["path"]
    if "dirID" in sim_row and pd.notnull(sim_row["dirID"]):
        candidate = os.path.join(sim_path, f"frames_{sim_row['dirID']}")
        if os.path.isdir(candidate): return candidate
    candidates = sorted(glob.glob(os.path.join(sim_path, "frames_*")))
    return candidates[0] if candidates else None

def select_simulations(df_idx, args):
    df = df_idx.copy()
    
    if "grain_json" in df.columns:
        def extract_sides(row):
            sl, ss = np.nan, np.nan
            if pd.notnull(row["grain_json"]):
                try:
                    grains = json.loads(row["grain_json"])
                    if grains:
                        # CORREGIDO: ordenar por sides, no por radius (ver
                        # get_geometry_label_from_row para la explicacion).
                        grains = sorted(grains, key=lambda g: float(g.get("sides", 1)), reverse=True)
                        sl = float(grains[0].get("sides", np.nan))
                        ss = float(grains[-1].get("sides", np.nan))
                except Exception:
                    pass
            return pd.Series([sl, ss], index=["sides_large", "sides_small"])
        
        df[["sides_large", "sides_small"]] = df.apply(extract_sides, axis=1)
    
    if "geometry_label" not in df.columns:
        df["geometry_label"] = df.apply(get_geometry_label_from_row, axis=1)
    else:
        mask = df["geometry_label"].isnull() | (df["geometry_label"] == "")
        if mask.any():
            df.loc[mask, "geometry_label"] = df.loc[mask].apply(get_geometry_label_from_row, axis=1)

    # NUEVO: reparar filas mono-especie (chi=0/chi=1) ANTES de tocar
    # 'category' mas abajo, porque el reemplazo de "General" -> sim_hash
    # destruye la pista que reparar_geometria_mono_especie() necesita para
    # encontrar la fila hermana de cada una.
    df = reparar_geometria_mono_especie(df)

    if "category" in df.columns and "sim_hash" in df.columns:
        mask_gen = df["category"].str.strip().str.lower() == "general"
        if mask_gen.any():
            df.loc[mask_gen, "category"] = df.loc[mask_gen, "sim_hash"]
            
    if args.category is not None and "category" in df.columns: 
        df = df[df["category"] == args.category]
    if args.geometry_label is not None: 
        df = df[df["geometry_label"] == args.geometry_label]
    if args.chi_values: 
        df = df[df["chi"].astype(float).isin([float(x) for x in args.chi_values])]
    if args.max_sims is not None: 
        df = df.head(args.max_sims)
        
    return df

def build_tasks(df_idx, args):
    tasks = []
    sample_cfg = {
        "bulk_sample_per_jam": args.bulk_sample_per_jam,
        "arco_sample_per_jam": args.arco_sample_per_jam,
        "sample_seed": args.sample_seed,
    }
    for _, sim_row_pd in df_idx.iterrows():
        sim_row = {col: sim_row_pd[col] for col in df_idx.columns if col in sim_row_pd}
        sim_path = sim_row.get("path", "")
        if not os.path.isdir(sim_path): continue
        frames_dir = find_frames_dir(sim_row)
        if frames_dir is None: continue
        xy_files = sorted(glob.glob(os.path.join(frames_dir, "atasco_*.xy")))
        if args.max_jams_per_sim is not None: xy_files = xy_files[:args.max_jams_per_sim]
        for xy_file in xy_files:
            tasks.append({
                "xy_file": xy_file,
                "sim_row": sim_row,
                "contact_mode": args.contact_mode,
                "save_force_samples": args.save_force_samples,
                "sample_cfg": sample_cfg,
                "save_images": args.save_images,
            })
    return tasks

def iter_task_groups(df_idx, args):
    group_cols = [c for c in ["category", "geometry_label", "area_ratio_nominal", "r_ratio_nominal", "chi", "sides_large", "sides_small"] if c in df_idx.columns]
    if not group_cols or not args.process_by_group:
        yield ("all", build_tasks(df_idx, args))
        return
    for key, df_group in df_idx.groupby(group_cols, dropna=False):
        tasks = build_tasks(df_group, args)
        if tasks: yield (key, tasks)

def append_csv_rows(rows, path):
    if not rows: return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)

def process_task_batch(tasks, workers, args, summary_out, error_log_out, samples_out):
    total_ok, total_fail = 0, 0
    buffer_summary, buffer_errors, buffer_samples = [], [], []

    def flush_buffers():
        nonlocal buffer_summary, buffer_errors, buffer_samples
        if buffer_summary: append_csv_rows(buffer_summary, summary_out); buffer_summary = []
        if buffer_errors: append_csv_rows(buffer_errors, error_log_out); buffer_errors = []
        if args.save_force_samples and buffer_samples: append_csv_rows(buffer_samples, samples_out); buffer_samples = []

    def handle_result(result):
        nonlocal total_ok, total_fail
        if result and result.get("ok"):
            buffer_summary.append(result["summary"])
            if args.save_force_samples and result.get("samples"): buffer_samples.extend(result["samples"])
            total_ok += 1
        else:
            total_fail += 1
            buffer_errors.append({"xy_file": result.get("xy_file", "unknown"), "error": result.get("error", "unknown")})

    if workers == 1:
        for k, task in enumerate(tasks, start=1):
            handle_result(process_one_jam_task(task))
            if k % args.flush_every == 0: flush_buffers(); print(f"    procesados {k}/{len(tasks)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            task_iter = iter(tasks)
            futures = set()
            for _ in range(min(max(1, workers * args.in_flight_factor), len(tasks))):
                try: futures.add(executor.submit(process_one_jam_task, next(task_iter)))
                except StopIteration: break
            k = 0
            while futures:
                done, futures = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    k += 1
                    try: handle_result(future.result())
                    except Exception as e: handle_result({"ok": False, "error": str(e)})
                    try: futures.add(executor.submit(process_one_jam_task, next(task_iter)))
                    except StopIteration: pass
                    if k % args.flush_every == 0: flush_buffers(); print(f"    procesados {k}/{len(tasks)}", flush=True)
    flush_buffers()
    return total_ok, total_fail

def sem_from_series(x):
    x = pd.Series(x).dropna()
    return np.nan if len(x) <= 1 else float(x.std(ddof=1) / np.sqrt(len(x)))

def pool_stats(n, m, s):
    """Combina (n_i, media_i, std_i ddof=1) de varios atascos en un N/media/std/SEM
    exactos para el conjunto de todos los contactos individuales de la configuracion."""
    n = np.asarray(n, dtype=float)
    m = np.asarray(m, dtype=float)
    s = np.asarray(s, dtype=float)
    mask = n > 0
    n, m, s = n[mask], m[mask], s[mask]
    N = float(np.sum(n))
    if N <= 0:
        return 0, np.nan, np.nan, np.nan
    M = float(np.sum(n * m) / N)
    ss_i = np.where(n > 1, (n - 1) * np.nan_to_num(s, nan=0.0) ** 2, 0.0)
    ss_total = float(np.sum(ss_i) + np.sum(n * (m - M) ** 2))
    if N > 1:
        var_pooled = ss_total / (N - 1)
        std_pooled = float(np.sqrt(var_pooled)) if var_pooled >= 0 else np.nan
        sem_pooled = std_pooled / np.sqrt(N)
    else:
        std_pooled, sem_pooled = np.nan, np.nan
    return int(N), M, std_pooled, sem_pooled

def compute_pooled_columns(df, group_cols, regiones=('bulk', 'arco', 'roi'), tipos=('BB', 'BS', 'SS')):
    """sigma/sqrt(N) pedido: pooling exacto sobre TODOS los contactos de la
    configuracion (todos los atascos juntos), no un promedio ingenuo de SEMs
    por atasco. Formula documentada en README.md de esta carpeta, seccion 4."""
    rows = []
    for key, g in df.groupby(group_cols, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_cols, key))
        for reg in regiones:
            n_col, m_col, s_col = f"N_contactos_{reg}", f"mean_Fn_{reg}", f"std_Fn_{reg}"
            if n_col in g.columns and m_col in g.columns and s_col in g.columns:
                N, M, _, sem = pool_stats(g[n_col], g[m_col], g[s_col])
                row[f"N_contactos_total_{reg}"] = N
                row[f"mean_Fn_pooled_{reg}"] = M
                row[f"sem_pooled_Fn_{reg}"] = sem
            for tipo in tipos:
                n_col, m_col, s_col = f"N_contactos_{reg}_{tipo}", f"mean_Fn_{reg}_{tipo}", f"std_Fn_{reg}_{tipo}"
                if n_col in g.columns and m_col in g.columns and s_col in g.columns:
                    N, M, _, sem = pool_stats(g[n_col], g[m_col], g[s_col])
                    row[f"N_contactos_total_{reg}_{tipo}"] = N
                    row[f"mean_Fn_pooled_{reg}_{tipo}"] = M
                    row[f"sem_pooled_Fn_{reg}_{tipo}"] = sem
        rows.append(row)
    return pd.DataFrame(rows)

def apply_min_n_filter(res, min_n_contactos, regiones=('bulk', 'arco', 'roi'), tipos=('BB', 'BS', 'SS')):
    """Descarta (pone NaN) solo las columnas estadisticas de una combinacion
    region[/tipo] especifica cuando su N_contactos_total pooled cae debajo del
    umbral. No descarta la fila completa: otras combinaciones de la misma fila
    pueden seguir siendo validas."""
    if min_n_contactos is None or min_n_contactos <= 0:
        return res
    for reg in regiones:
        combos = [(reg, "")] + [(reg, f"_{tipo}") for tipo in tipos]
        for base, suf in combos:
            n_col = f"N_contactos_total_{base}{suf}"
            if n_col not in res.columns:
                continue
            below = res[n_col] < min_n_contactos
            for stat in ["mean_Fn", "mean_Fn_pooled", "sem_pooled_Fn"]:
                col = f"{stat}_{base}{suf}"
                if col in res.columns:
                    res.loc[below, col] = np.nan
            if suf == "":
                for stat in ["std_between_jams_Fn", "sem_between_jams_Fn"]:
                    col = f"{stat}_{base}"
                    if col in res.columns:
                        res.loc[below, col] = np.nan
    return res

def make_configuration_summary(summary_path, out_path, min_n_contactos=10):
    df = pd.read_csv(summary_path)
    if df.empty: return
    if "area_ratio_nominal" not in df.columns and "area_ratio" in df.columns: df["area_ratio_nominal"] = df["area_ratio"].round(3)
    if "r_ratio_nominal" not in df.columns and "r_ratio" in df.columns: df["r_ratio_nominal"] = df["r_ratio"].round(2)

    # CORREGIDO: se agrega "w_salida" a la clave de agrupamiento. Sin esto,
    # simulaciones con distinto ancho de salida (ej. el sub-experimento
    # COMPARACION-GOLDBERG, que barre w_salida a chi/ratio fijos) se
    # promediaban silenciosamente junto con el barrido principal (siempre
    # w_salida=2.0), aunque sean configuraciones fisicas distintas.
    group_cols = [c for c in ["category", "geometry_label", "area_ratio_nominal", "r_ratio_nominal", "chi", "contact_mode", "sides_large", "sides_small", "w_salida"] if c in df.columns]

    agg_kwargs = {
        "n_atascos": ("Atasco_ID", "count"), 
        "n_simulaciones": ("sim_hash", "nunique"),
        "area_ratio_real_min": ("area_ratio", "min"), 
        "area_ratio_real_max": ("area_ratio", "max"),
        "r_ratio_real_min": ("r_ratio", "min"), 
        "r_ratio_real_max": ("r_ratio", "max"),
        
        "mean_Fn_bulk": ("mean_Fn_bulk", "mean"),
        "std_between_jams_Fn_bulk": ("mean_Fn_bulk", "std"),
        "sem_between_jams_Fn_bulk": ("mean_Fn_bulk", sem_from_series),
        "mean_N_contactos_bulk": ("N_contactos_bulk", "mean"),
        "mean_N_particulas_bulk": ("N_particulas_bulk", "mean"), # NUEVO
        "mean_Ft_bulk": ("mean_Ft_bulk", "mean"),
        "std_between_jams_Ft_bulk": ("mean_Ft_bulk", "std"),
        "sem_between_jams_Ft_bulk": ("mean_Ft_bulk", sem_from_series),

        "mean_Fn_arco": ("mean_Fn_arco", "mean"),
        "std_between_jams_Fn_arco": ("mean_Fn_arco", "std"),
        "sem_between_jams_Fn_arco": ("mean_Fn_arco", sem_from_series),
        "mean_N_contactos_arco": ("N_contactos_arco", "mean"),
        "mean_N_particulas_arco_contactos": ("N_particulas_arco", "mean"), # NUEVO
        "mean_n_particulas_arco_topologico": ("n_particulas_arco", "mean"),
        "mean_Ft_arco": ("mean_Ft_arco", "mean"),
        "std_between_jams_Ft_arco": ("mean_Ft_arco", "std"),
        "sem_between_jams_Ft_arco": ("mean_Ft_arco", sem_from_series),

        "mean_Fn_roi": ("mean_Fn_roi", "mean"),
        "std_between_jams_Fn_roi": ("mean_Fn_roi", "std"),
        "sem_between_jams_Fn_roi": ("mean_Fn_roi", sem_from_series),
        "mean_Ft_roi": ("mean_Ft_roi", "mean"),
        "std_between_jams_Ft_roi": ("mean_Ft_roi", "std"),
        "sem_between_jams_Ft_roi": ("mean_Ft_roi", sem_from_series),
        "mean_N_contactos_roi": ("N_contactos_roi", "mean"),
        "mean_N_particulas_roi": ("N_particulas_roi", "mean") # NUEVO
    }

    # Propagar las sumatorias promediadas de las geometrías al resumen final
    for reg in ['arco', 'roi', 'bulk']:
        for tipo in ['BB', 'BS', 'SS']:
            col_sum = f"f_norm_{reg}_{tipo}"
            if col_sum in df.columns:
                agg_kwargs[f"mean_sum_Fn_{reg}_{tipo}"] = (col_sum, "mean")
            
            col_mean = f"mean_Fn_{reg}_{tipo}"
            if col_mean in df.columns:
                agg_kwargs[f"mean_Fn_{reg}_{tipo}"] = (col_mean, "mean")
                
            col_contrib = f"contrib_mean_Fn_{reg}_{tipo}"
            if col_contrib in df.columns:
                agg_kwargs[f"mean_contrib_Fn_{reg}_{tipo}"] = (col_contrib, "mean")

            # NUEVO: particulas distintas detras de este tipo de contacto,
            # promediadas entre atascos. Un N_contactos_total alto no implica
            # muchas particulas independientes (ver N_particulas_{reg}_{tipo}
            # antes de confiar en un punto LS/LL/SS con pocas particulas).
            col_n_part = f"N_particulas_{reg}_{tipo}"
            if col_n_part in df.columns:
                agg_kwargs[f"mean_N_particulas_{reg}_{tipo}"] = (col_n_part, "mean")


    res = df.groupby(group_cols, dropna=False).agg(**agg_kwargs).reset_index()

    # sigma/sqrt(N_contactos): pooling exacto sobre todos los contactos de la
    # configuracion (no un sem() ingenuo de los means por atasco, que es lo
    # que sem_between_jams_Fn_* mide y es una fuente de variabilidad distinta).
    pooled = compute_pooled_columns(df, group_cols)
    res = res.merge(pooled, on=group_cols, how="left")

    # Umbral de robustez estadistica: por debajo de min_n_contactos, la
    # combinacion region/tipo se anula (NaN) pero la fila se conserva.
    res = apply_min_n_filter(res, min_n_contactos)

    res.to_csv(out_path, index=False)


# =============================================================================
# MAIN
# =============================================================================

def run_analysis(args):
    idx_path = Path(args.idx)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_out = out_dir / "resumen_fuerza_normal_por_atasco.csv"
    config_summary_out = out_dir / "resumen_fuerza_normal_por_configuracion.csv"
    error_log_out = out_dir / "errores_procesamiento.csv"
    samples_out = out_dir / "muestras_fuerza_normal.csv"

    if args.overwrite:
        for p in [summary_out, config_summary_out, error_log_out, samples_out]:
            if p.exists(): p.unlink()

    df_idx = select_simulations(pd.read_csv(idx_path), args)
    workers = max(1, mp.cpu_count() - 1) if args.workers == 0 else args.workers

    print("=" * 72)
    print(" ANÁLISIS DE FUERZA NORMAL PROMEDIO: BULK vs ARCO vs ROI")
    print("=" * 72)
    print(f"[+] Guardar muestras de fuerza:  {args.save_force_samples}")
    print(f"[+] Generar imágenes (Arco/ROI): {args.save_images}")
    print("=" * 72)

    for group_key, tasks in iter_task_groups(df_idx, args):
        print(f"\nProcesando grupo {group_key} ({len(tasks)} atascos)...")
        process_task_batch(tasks, workers, args, summary_out, error_log_out, samples_out)

    if summary_out.exists():
        make_configuration_summary(summary_out, config_summary_out, min_n_contactos=args.min_n_contactos)
        print(f"\n[+] Análisis finalizado. Resumen guardado en: {config_summary_out}")


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--idx", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--flush-every", type=int, default=25)
    parser.add_argument("--in-flight-factor", type=int, default=2)
    parser.add_argument("--overwrite", action="store_true")
    
    # Filtros
    parser.add_argument("--max-sims", type=int, default=None)
    parser.add_argument("--max-jams-per-sim", type=int, default=None)
    parser.add_argument("--category", default=None)
    parser.add_argument("--geometry-label", default=None)
    parser.add_argument("--chi-values", nargs="*", default=None)
    
    parser.add_argument("--contact-mode", choices=["pair", "point"], default="pair")
    parser.add_argument("--process-by-group", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--min-n-contactos", type=int, default=10,
                         help="Umbral minimo de N_contactos pooled por region/tipo; por debajo, esa combinacion se anula a NaN en el resumen de configuracion (fila completa se conserva).")
    
    # Muestreo de Fuerzas para Violines
    parser.add_argument("--save-force-samples", action="store_true")
    parser.add_argument("--bulk-sample-per-jam", type=int, default=200)
    parser.add_argument("--arco-sample-per-jam", type=int, default=0)
    parser.add_argument("--sample-seed", type=int, default=12345)
    
    # Ploteo de Imágenes
    parser.add_argument("--save-images", action="store_true", help="Genera imagenes PNG diferenciando Arco/ROI/Bulk")

    return parser

if __name__ == "__main__":
    mp.freeze_support()
    run_analysis(build_parser().parse_args())