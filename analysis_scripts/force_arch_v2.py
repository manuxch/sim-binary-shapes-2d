#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
force_arch_v2.py

Analisis de fuerza normal promedio en bulk y arco.

Puntos principales:
- Mantiene la deteccion de arcos con networkx.
- Procesa por grupos de configuracion para evitar saturar RAM.
- Escribe resultados incrementalmente.
- Resume fuerza normal por atasco y luego por configuracion.
- Opcionalmente guarda muestras de fuerzas normales para violin plots.
- Calcula un ROI dinámico basado en las coordenadas extremas del arco, 
  excluyendo las partículas que forman parte de este.

Definiciones:
- bulk: todos los contactos grano-grano del atasco.
- arco: contactos arco-arco, es decir, ambos granos pertenecen al arco detectado.
- roi: región espacial delimitada por el arco, excluyendo las partículas del arco mismo.

Salidas:
- resumen_fuerza_normal_por_atasco.csv
- resumen_fuerza_normal_por_configuracion.csv
- errores_procesamiento.csv
- muestras_fuerza_normal.csv  (solo si se usa --save-force-samples)
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

import numpy as np
import pandas as pd
import networkx as nx


# =============================================================================
# UTILIDADES GENERALES
# =============================================================================

def nominalizar_ratio(x, ndigits=3):
    if x is None:
        return np.nan
    try:
        if pd.isna(x):
            return np.nan
    except TypeError:
        pass
    return round(float(x), ndigits)


def shape_name_from_sides(sides):
    try:
        sides = int(sides)
    except Exception:
        return "Desconocido"

    return {
        1: "Disco",
        3: "Tri",
        4: "Cuad",
        5: "Pent",
    }.get(sides, f"Pol{sides}")


def get_geometry_label_from_row(row):
    try:
        grains = json.loads(row["grain_json"])
        if not grains:
            return row.get("system_type", "Desconocido")

        grains = sorted(
            grains,
            key=lambda g: float(g.get("radius", 0.0)),
            reverse=True,
        )

        names = [shape_name_from_sides(g.get("sides", -1)) for g in grains]
        return names[0] if len(names) == 1 else "-".join(names)

    except Exception:
        return row.get("system_type", "Desconocido")


def stable_seed_from_text(text):
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return int(digest, 16)


# =============================================================================
# PARSEADORES
# =============================================================================

def parse_params(filename):
    params = {
        "Radio_silo": 10.25,
        "Radio_salida": 2.5,
    }

    if not os.path.exists(filename):
        return params

    try:
        with open(filename, "r") as f:
            for line in f:
                line_clean = line.split("#")[0].strip()

                if "Radio_silo:" in line_clean:
                    try:
                        params["Radio_silo"] = float(line_clean.split(":")[1].strip())
                    except Exception:
                        pass

                elif "Radio_salida:" in line_clean:
                    try:
                        params["Radio_salida"] = float(line_clean.split(":")[1].strip())
                    except Exception:
                        pass
    except Exception:
        pass

    return params


def parse_xy(filename):
    particles = {}

    with open(filename, "r") as f:
        for line in f:
            p = line.split()
            if not p:
                continue

            pid = int(p[0])
            if pid < 0:
                continue

            n_sides = int(p[1])

            if n_sides == 1:
                x = float(p[2])
                y = float(p[3])
                r = float(p[4])
                ptype = int(p[5])

                particles[pid] = {
                    "pos": (x, y),
                    "r_eff": r,
                    "type": ptype,
                    "shape": "Disco",
                }
            else:
                coords = np.array(p[2:-1], dtype=float).reshape(-1, 2)
                center = coords.mean(axis=0)
                ptype = int(p[-1])
                r_eff = float(np.max(np.linalg.norm(coords - center, axis=1)))

                particles[pid] = {
                    "pos": (float(center[0]), float(center[1])),
                    "r_eff": r_eff,
                    "type": ptype,
                    "shape": "Poligono",
                }

    return particles


def obtener_radio(p_data):
    return float(p_data["r_eff"])


def read_contacts(filename):
    cols = ["id_a", "id_b", "px", "py", "f_norm", "f_tan"]

    try:
        df = pd.read_csv(
            filename,
            sep=r"\s+",
            comment="#",
            header=None,
            usecols=[0, 1, 2, 3, 4, 5],
            names=cols,
        )
    except (pd.errors.EmptyDataError, ValueError):
        return pd.DataFrame(columns=cols)

    if df.empty:
        return df

    df["id_a"] = df["id_a"].astype(np.int64)
    df["id_b"] = df["id_b"].astype(np.int64)

    # Solo contactos grano-grano. Excluye paredes/silo/tapa.
    df = df[(df["id_a"] > 0) & (df["id_b"] > 0)].copy()

    if df.empty:
        return df

    df["pair_a"] = np.minimum(df["id_a"].values, df["id_b"].values)
    df["pair_b"] = np.maximum(df["id_a"].values, df["id_b"].values)

    return df


# =============================================================================
# DETECCION DE ARCOS CON NETWORKX
# =============================================================================

def es_cimiento_estable(pid, particles, G, path, idx, r_salida):
    p = particles[pid]
    x, y = p["pos"]
    r = obtener_radio(p)

    if abs(x) < (r_salida - 0.2):
        return False

    if (y - r) < 0.2:
        return True

    vecinos_arco = []
    if idx > 0:
        vecinos_arco.append(path[idx - 1])
    if idx < len(path) - 1:
        vecinos_arco.append(path[idx + 1])

    apoyos_inferiores = 0
    for vecino in G.neighbors(pid):
        if vecino in vecinos_arco:
            continue

        y_vecino = particles[vecino]["pos"][1]
        if y_vecino < (y - 0.05):
            apoyos_inferiores += 1

    return apoyos_inferiores >= 2


def purgar_cimientos(path, particles, G, r_salida):
    if not path:
        return []

    iL = 0
    while iL < len(path) and es_cimiento_estable(path[iL], particles, G, path, iL, r_salida):
        iL += 1

    iR = len(path) - 1
    while iR >= iL and es_cimiento_estable(path[iR], particles, G, path, iR, r_salida):
        iR -= 1

    if iL > iR:
        return []

    return path[iL:iR + 1]


def detectar_arco_primario(G, particles, params):
    r_salida = params.get("Radio_salida", 2.5)

    nleft = []
    nright = []

    for pid, data in particles.items():
        r = obtener_radio(data)
        x, y = data["pos"]

        if (y - r) < 0.2:
            if x < 0.0:
                nleft.append(pid)
            elif x > 0.0:
                nright.append(pid)

    mejor_arco = []
    min_costo_total = float("inf")

    for left_id in nleft:
        for right_id in nright:
            if not nx.has_path(G, left_id, right_id):
                continue

            try:
                path = nx.shortest_path(
                    G,
                    source=left_id,
                    target=right_id,
                    weight="costo_arco",
                )

                costo_path = sum(
                    G[path[i]][path[i + 1]]["costo_arco"]
                    for i in range(len(path) - 1)
                )

                if costo_path < min_costo_total:
                    min_costo_total = costo_path
                    mejor_arco = purgar_cimientos(path, particles, G, r_salida)

            except nx.NetworkXNoPath:
                continue

    return mejor_arco


# =============================================================================
# CONTACTOS Y GRAFO
# =============================================================================

def aggregate_contacts_for_graph(df_contacts, particles):
    if df_contacts.empty:
        return pd.DataFrame()

    valid_ids = set(particles.keys())
    df = df_contacts[
        df_contacts["pair_a"].isin(valid_ids) &
        df_contacts["pair_b"].isin(valid_ids)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # Tomamos valor absoluto de la tangencial para no cancelar vectores opuestos
    df["f_tan_abs"] = df["f_tan"].abs()

    grouped = (
        df
        .groupby(["pair_a", "pair_b"], as_index=False)
        .agg(
            px=("px", "mean"),
            py=("py", "mean"),
            f_norm=("f_norm", "sum"),
            f_tan=("f_tan_abs", "sum") # Guardamos como f_tan para simplificar
        )
    )

    return grouped


def build_contact_graph(grouped_contacts, particles):
    G = nx.Graph()

    for pid, attr in particles.items():
        G.add_node(pid, **attr)

    for _, row in grouped_contacts.iterrows():
        u = int(row["pair_a"])
        v = int(row["pair_b"])

        if u not in particles or v not in particles:
            continue

        y_max = max(particles[u]["pos"][1], particles[v]["pos"][1])
        costo = 10.0 ** min(float(y_max), 100.0)

        G.add_edge(
            u,
            v,
            weight=float(row["f_norm"]),
            costo_arco=costo,
        )

    return G


def prepare_force_dataset(df_contacts, particles, contact_mode="pair"):
    valid_ids = set(particles.keys())

    df = df_contacts[
        df_contacts["pair_a"].isin(valid_ids) &
        df_contacts["pair_b"].isin(valid_ids)
    ].copy()

    if df.empty:
        return df

    df["f_tan_abs"] = df["f_tan"].abs()

    if contact_mode == "point":
        out = (
            df[["pair_a", "pair_b", "f_norm", "f_tan_abs", "px", "py"]]
            .copy()
            .rename(columns={"pair_a": "id_a", "pair_b": "id_b", "f_tan_abs": "f_tan"})
        )

    elif contact_mode == "pair":
        out = (
            df
            .groupby(["pair_a", "pair_b"], as_index=False)
            .agg(
                f_norm=("f_norm", "sum"), 
                f_tan=("f_tan_abs", "sum"),
                px=("px", "mean"), # Centroide del contacto
                py=("py", "mean")  # Centroide del contacto
            )
            .rename(columns={"pair_a": "id_a", "pair_b": "id_b"})
        )
    else:
        raise ValueError("contact_mode debe ser 'pair' o 'point'.")

    out["id_a"] = out["id_a"].astype(np.int64)
    out["id_b"] = out["id_b"].astype(np.int64)
    out["f_norm"] = out["f_norm"].astype(float)
    out["f_tan"] = out["f_tan"].astype(float)

    return out


# =============================================================================
# RESUMEN Y MUESTREO POR ATASCO
# =============================================================================

def mean_or_nan(values):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.nan
    return float(np.nanmean(values))


def std_or_nan(values):
    values = np.asarray(values, dtype=float)
    if values.size <= 1:
        return np.nan
    return float(np.nanstd(values, ddof=1))


def summarize_fn_one_jam(df_forces, arco_path, particles):
    ids_arco = set(int(x) for x in arco_path)

    f_norm = df_forces["f_norm"].to_numpy(dtype=float)
    f_tan = df_forces["f_tan"].to_numpy(dtype=float)
    px = df_forces["px"].to_numpy(dtype=float)
    py = df_forces["py"].to_numpy(dtype=float)
    
    in_a = df_forces["id_a"].isin(ids_arco).to_numpy()
    in_b = df_forces["id_b"].isin(ids_arco).to_numpy()

    mask_arco = in_a & in_b
    f_arco = f_norm[mask_arco]
    ft_arco = f_tan[mask_arco]

    res = {
        "N_contactos_bulk": int(f_norm.size),
        "mean_Fn_bulk": mean_or_nan(f_norm),
        "std_Fn_bulk": std_or_nan(f_norm),
        "mean_Ft_bulk": mean_or_nan(f_tan),
        "std_Ft_bulk": std_or_nan(f_tan),

        "N_contactos_arco": int(f_arco.size),
        "mean_Fn_arco": mean_or_nan(f_arco),
        "std_Fn_arco": std_or_nan(f_arco),
        "mean_Ft_arco": mean_or_nan(ft_arco),
        "std_Ft_arco": std_or_nan(ft_arco),
    }

    # --- NUEVO: ROI Dinámico basado en el arco ---
    # Extraemos coordenadas X e Y de las partículas que conforman el arco
    y_arco = [particles[pid]["pos"][1] for pid in ids_arco if pid in particles]
    x_arco = [particles[pid]["pos"][0] for pid in ids_arco if pid in particles]

    if y_arco and x_arco:
        # La región queda definida por los extremos (más baja/alta y anchos) del arco
        ymin, ymax = min(y_arco), max(y_arco)
        xmin, xmax = min(x_arco), max(x_arco)

        # Máscara espacial (rectángulo)
        mask_roi_spatial = (px >= xmin) & (px <= xmax) & (py >= ymin) & (py <= ymax)

        # Máscara para excluir contactos de partículas del arco. 
        # (in_a | in_b) es True si alguna de las dos partículas del contacto pertenece al arco.
        # ~ invierte la condición: solo True cuando NINGUNA de las dos pertenece al arco.
        mask_exclude_arco = ~(in_a | in_b)
        
        mask_roi = mask_roi_spatial & mask_exclude_arco
        
        f_norm_roi = f_norm[mask_roi]
        f_tan_roi = f_tan[mask_roi]
        n_roi = int(f_norm_roi.size)

        sem_fn_roi = float(np.nanstd(f_norm_roi, ddof=1) / np.sqrt(n_roi)) if n_roi > 1 else np.nan
        sem_ft_roi = float(np.nanstd(f_tan_roi, ddof=1) / np.sqrt(n_roi)) if n_roi > 1 else np.nan

        res.update({
            "N_contactos_roi": n_roi,
            "mean_Fn_roi": mean_or_nan(f_norm_roi),
            "std_Fn_roi": std_or_nan(f_norm_roi),
            "sem_Fn_roi": sem_fn_roi,
            "mean_Ft_roi": mean_or_nan(f_tan_roi),
            "std_Ft_roi": std_or_nan(f_tan_roi),
            "sem_Ft_roi": sem_ft_roi,
        })
    else:
        # Relleno de seguridad con NaN en caso de datos anómalos
        res.update({
            "N_contactos_roi": np.nan, "mean_Fn_roi": np.nan, "std_Fn_roi": np.nan, "sem_Fn_roi": np.nan,
            "mean_Ft_roi": np.nan, "std_Ft_roi": np.nan, "sem_Ft_roi": np.nan,
        })

    return res


def sample_force_values(df_forces, arco_path, sim_row, jam_id, sample_cfg):
    ids_arco = set(int(x) for x in arco_path)

    f_norm = df_forces["f_norm"].to_numpy(dtype=float)
    f_tan = df_forces["f_tan"].to_numpy(dtype=float) 
    
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

    meta = {}
    for col in [
        "sim_hash", "config_hash", "category", "system_type",
        "geometry_label", "chi", "area_ratio", "area_ratio_nominal",
        "r_ratio", "r_ratio_nominal", "r_small", "area_small", "tirada",
    ]:
        if col in sim_row:
            meta[col] = sim_row[col]

    rows = []

    for i in idx_bulk:
        row = dict(meta)
        row["Atasco_ID"] = jam_id
        row["grupo"] = "bulk"
        row["f_norm"] = float(f_norm[i])
        row["f_tan"] = float(f_tan[i]) 
        rows.append(row)

    for i in idx_arco:
        row = dict(meta)
        row["Atasco_ID"] = jam_id
        row["grupo"] = "arco"
        row["f_norm"] = float(f_norm[i])
        row["f_tan"] = float(f_tan[i]) 
        rows.append(row)

    return rows


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
    if jam_id is None:
        return {
            "ok": False,
            "xy_file": xy_file,
            "error": "No se pudo extraer Atasco_ID",
        }

    sim_path = sim_row["path"]
    params = parse_params(os.path.join(sim_path, "params.in"))
    contacts_file = os.path.join(os.path.dirname(xy_file), f"atasco_contacts_{jam_id}.dat")

    if not os.path.exists(contacts_file):
        return {
            "ok": False,
            "xy_file": xy_file,
            "error": "No existe archivo de contactos",
        }

    try:
        particles = parse_xy(xy_file)
        if not particles:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "Sin particulas validas",
            }

        raw_contacts = read_contacts(contacts_file)
        if raw_contacts.empty:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "Sin contactos grano-grano",
            }

        grouped_graph = aggregate_contacts_for_graph(raw_contacts, particles)
        if grouped_graph.empty:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "Sin contactos validos para grafo",
            }

        G = build_contact_graph(grouped_graph, particles)
        arco_path = detectar_arco_primario(G, particles, params)
        if not arco_path:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "No se detecto arco valido",
            }

        df_forces = prepare_force_dataset(raw_contacts, particles, contact_mode=contact_mode)
        if df_forces.empty:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "Sin contactos validos para fuerzas",
            }

        # Enviamos 'particles' para el cálculo dinámico del ROI
        summary = summarize_fn_one_jam(df_forces, arco_path, particles)

        for col, value in sim_row.items():
            if col != "path":
                summary[col] = value

        summary["Atasco_ID"] = jam_id
        summary["contact_mode"] = contact_mode
        summary["n_particulas_arco"] = int(len(arco_path))
        summary["arco_ids"] = json.dumps([int(x) for x in arco_path])
        summary["xy_file"] = xy_file

        samples = None
        if task.get("save_force_samples", False):
            samples = sample_force_values(
                df_forces=df_forces,
                arco_path=arco_path,
                sim_row=sim_row,
                jam_id=jam_id,
                sample_cfg=task.get("sample_cfg", {}),
            )

        return {
            "ok": True,
            "summary": summary,
            "samples": samples,
            "xy_file": xy_file,
        }

    except Exception as e:
        return {
            "ok": False,
            "xy_file": xy_file,
            "error": str(e),
        }


# =============================================================================
# RECORRIDO DE SIMULACIONES
# =============================================================================

def find_frames_dir(sim_row):
    sim_path = sim_row["path"]

    if "dirID" in sim_row and pd.notnull(sim_row["dirID"]):
        candidate = os.path.join(sim_path, f"frames_{sim_row['dirID']}")
        if os.path.isdir(candidate):
            return candidate

    candidates = sorted(glob.glob(os.path.join(sim_path, "frames_*")))
    return candidates[0] if candidates else None


def select_simulations(df_idx, args):
    df = df_idx.copy()

    if args.verbose_filters:
        print(f"[filtro] Inicial: {len(df)} simulaciones")

    if args.category is not None and "category" in df.columns:
        df = df[df["category"] == args.category]
        if args.verbose_filters:
            print(f"[filtro] category={args.category}: {len(df)}")

    if args.geometry_label is not None:
        df = df[df["geometry_label"] == args.geometry_label]
        if args.verbose_filters:
            print(f"[filtro] geometry_label={args.geometry_label}: {len(df)}")

    if args.chi_values:
        chi_vals = [float(x) for x in args.chi_values]
        df = df[df["chi"].astype(float).isin(chi_vals)]
        if args.verbose_filters:
            print(f"[filtro] chi_values={chi_vals}: {len(df)}")

    if args.area_ratio is not None and "area_ratio_nominal" in df.columns:
        target = float(args.area_ratio)
        tol = float(args.ratio_tol)
        df = df[np.isclose(df["area_ratio_nominal"].astype(float), target, rtol=0, atol=tol)]
        if args.verbose_filters:
            print(f"[filtro] area_ratio_nominal={target} +/- {tol}: {len(df)}")

    elif args.area_ratio is not None and "area_ratio" in df.columns:
        target = float(args.area_ratio)
        tol = float(args.ratio_tol)
        df = df[np.isclose(df["area_ratio"].astype(float), target, rtol=0, atol=tol)]
        if args.verbose_filters:
            print(f"[filtro] area_ratio={target} +/- {tol}: {len(df)}")

    if args.r_ratio is not None and "r_ratio_nominal" in df.columns:
        target = float(args.r_ratio)
        tol = float(args.ratio_tol)
        df = df[np.isclose(df["r_ratio_nominal"].astype(float), target, rtol=0, atol=tol)]
        if args.verbose_filters:
            print(f"[filtro] r_ratio_nominal={target} +/- {tol}: {len(df)}")

    elif args.r_ratio is not None and "r_ratio" in df.columns:
        target = float(args.r_ratio)
        tol = float(args.ratio_tol)
        df = df[np.isclose(df["r_ratio"].astype(float), target, rtol=0, atol=tol)]
        if args.verbose_filters:
            print(f"[filtro] r_ratio={target} +/- {tol}: {len(df)}")

    if args.max_sims is not None:
        df = df.head(args.max_sims)
        if args.verbose_filters:
            print(f"[filtro] max_sims={args.max_sims}: {len(df)}")

    return df


def make_minimal_sim_row(sim_row_pd):
    wanted_cols = [
        "path",
        "sim_hash",
        "config_hash",
        "category",
        "system_type",
        "geometry_label",
        "chi",
        "area_ratio",
        "area_ratio_nominal",
        "r_ratio",
        "r_ratio_nominal",
        "r_small",
        "area_small",
        "tirada",
        "dirID",
    ]

    out = {}
    for col in wanted_cols:
        if col in sim_row_pd.index:
            value = sim_row_pd[col]
            out[col] = np.nan if pd.isna(value) else value

    return out


def build_tasks(df_idx, args):
    tasks = []
    sims_with_frames = 0
    sims_without_frames = 0

    sample_cfg = {
        "bulk_sample_per_jam": args.bulk_sample_per_jam,
        "arco_sample_per_jam": args.arco_sample_per_jam,
        "sample_seed": args.sample_seed,
    }

    for _, sim_row_pd in df_idx.iterrows():
        sim_row = make_minimal_sim_row(sim_row_pd)
        sim_path = sim_row.get("path", "")

        if not os.path.isdir(sim_path):
            sims_without_frames += 1
            continue

        frames_dir = find_frames_dir(sim_row)
        if frames_dir is None:
            sims_without_frames += 1
            continue

        xy_files = sorted(glob.glob(os.path.join(frames_dir, "atasco_*.xy")))

        if args.max_jams_per_sim is not None:
            xy_files = xy_files[:args.max_jams_per_sim]

        if not xy_files:
            sims_without_frames += 1
            continue

        sims_with_frames += 1

        for xy_file in xy_files:
            tasks.append({
                "xy_file": xy_file,
                "sim_row": sim_row,
                "contact_mode": args.contact_mode,
                "save_force_samples": args.save_force_samples,
                "sample_cfg": sample_cfg,
            })

    return tasks, sims_with_frames, sims_without_frames


def iter_task_groups(df_idx, args):
    """
    Genera grupos por configuracion. Esto limita la memoria y fuerza
    liberacion entre bloques.
    """
    group_cols = [
        "category",
        "geometry_label",
        "area_ratio_nominal",
        "r_ratio_nominal",
        "chi",
    ]

    group_cols = [c for c in group_cols if c in df_idx.columns]

    if not args.process_by_group or not group_cols:
        tasks, sims_with_frames, sims_without_frames = build_tasks(df_idx, args)
        yield ("all", tasks, sims_with_frames, sims_without_frames)
        return

    for key, df_group in df_idx.groupby(group_cols, dropna=False):
        tasks, sims_with_frames, sims_without_frames = build_tasks(df_group, args)
        if not tasks:
            continue
        yield (key, tasks, sims_with_frames, sims_without_frames)


def choose_workers(requested_workers):
    ncpu = mp.cpu_count()

    if requested_workers is None or requested_workers == 0:
        return max(1, ncpu - 1)

    return max(1, min(int(requested_workers), ncpu))


def append_csv_rows(rows, path):
    if not rows:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


# =============================================================================
# PROCESAMIENTO DE BATCHES
# =============================================================================

def process_task_batch(tasks, workers, args, summary_out, error_log_out, samples_out):
    total_ok = 0
    total_fail = 0

    buffer_summary = []
    buffer_errors = []
    buffer_samples = []

    flush_every = max(1, int(args.flush_every))

    def flush_buffers():
        nonlocal buffer_summary, buffer_errors, buffer_samples

        if buffer_summary:
            append_csv_rows(buffer_summary, summary_out)
            buffer_summary = []

        if buffer_errors:
            append_csv_rows(buffer_errors, error_log_out)
            buffer_errors = []

        if args.save_force_samples and buffer_samples:
            append_csv_rows(buffer_samples, samples_out)
            buffer_samples = []

    def handle_result(result):
        nonlocal total_ok, total_fail, buffer_summary, buffer_errors, buffer_samples

        if result and result.get("ok"):
            buffer_summary.append(result["summary"])
            total_ok += 1

            if args.save_force_samples and result.get("samples"):
                buffer_samples.extend(result["samples"])
        else:
            total_fail += 1
            buffer_errors.append({
                "xy_file": result.get("xy_file") if result else "unknown",
                "error": result.get("error") if result else "unknown",
            })

    if workers == 1:
        for k, task in enumerate(tasks, start=1):
            result = process_one_jam_task(task)
            handle_result(result)

            if k % flush_every == 0:
                flush_buffers()
                print(f"    procesados {k}/{len(tasks)} | ok={total_ok} | fail={total_fail}", flush=True)

    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            task_iter = iter(tasks)
            futures = set()
            max_in_flight = max(1, workers * args.in_flight_factor)

            for _ in range(min(max_in_flight, len(tasks))):
                try:
                    futures.add(executor.submit(process_one_jam_task, next(task_iter)))
                except StopIteration:
                    break

            k = 0

            while futures:
                done, futures = wait(futures, return_when=FIRST_COMPLETED)

                for future in done:
                    k += 1

                    try:
                        result = future.result()
                    except Exception as e:
                        result = {
                            "ok": False,
                            "xy_file": "future_exception",
                            "error": str(e),
                        }

                    handle_result(result)

                    try:
                        futures.add(executor.submit(process_one_jam_task, next(task_iter)))
                    except StopIteration:
                        pass

                    if k % flush_every == 0:
                        flush_buffers()
                        print(f"    procesados {k}/{len(tasks)} | ok={total_ok} | fail={total_fail}", flush=True)

    flush_buffers()
    return total_ok, total_fail


# =============================================================================
# RESUMEN POR CONFIGURACION
# =============================================================================

def sem_from_series(x):
    x = pd.Series(x).dropna()
    if len(x) <= 1:
        return np.nan
    return float(x.std(ddof=1) / np.sqrt(len(x)))


def make_configuration_summary(summary_path, out_path):
    df = pd.read_csv(summary_path)
    if df.empty:
        return

    if "area_ratio_nominal" not in df.columns and "area_ratio" in df.columns:
        df["area_ratio_nominal"] = df["area_ratio"].round(3)

    if "r_ratio_nominal" not in df.columns and "r_ratio" in df.columns:
        df["r_ratio_nominal"] = df["r_ratio"].round(2)

    group_cols = [
        "category",
        "geometry_label",
        "area_ratio_nominal",
        "r_ratio_nominal",
        "chi",
        "contact_mode",
    ]

    group_cols = [c for c in group_cols if c in df.columns]

    res = (
        df
        .groupby(group_cols, dropna=False)
        .agg(
            n_atascos=("Atasco_ID", "count"),
            n_simulaciones=("sim_hash", "nunique"),

            area_ratio_real_min=("area_ratio", "min"),
            area_ratio_real_max=("area_ratio", "max"),
            r_ratio_real_min=("r_ratio", "min"),
            r_ratio_real_max=("r_ratio", "max"),

            # --- BULK: Normal ---
            mean_Fn_bulk=("mean_Fn_bulk", "mean"),
            std_between_jams_Fn_bulk=("mean_Fn_bulk", "std"),
            sem_Fn_bulk=("mean_Fn_bulk", sem_from_series),
            mean_N_contactos_bulk=("N_contactos_bulk", "mean"),

            # --- BULK: Tangencial ---
            mean_Ft_bulk=("mean_Ft_bulk", "mean"),
            std_between_jams_Ft_bulk=("mean_Ft_bulk", "std"),
            sem_Ft_bulk=("mean_Ft_bulk", sem_from_series),

            # --- ARCO: Normal ---
            mean_Fn_arco=("mean_Fn_arco", "mean"),
            std_between_jams_Fn_arco=("mean_Fn_arco", "std"),
            sem_Fn_arco=("mean_Fn_arco", sem_from_series),
            mean_N_contactos_arco=("N_contactos_arco", "mean"),
            mean_n_particulas_arco=("n_particulas_arco", "mean"),

            # --- ARCO: Tangencial ---
            mean_Ft_arco=("mean_Ft_arco", "mean"),
            std_between_jams_Ft_arco=("mean_Ft_arco", "std"),
            sem_Ft_arco=("mean_Ft_arco", sem_from_series),

            # --- ROI: Normal ---
            mean_Fn_roi=("mean_Fn_roi", "mean"),
            std_between_jams_Fn_roi=("mean_Fn_roi", "std"),
            sem_Fn_roi=("mean_Fn_roi", sem_from_series),

            # --- ROI: Tangencial ---
            mean_Ft_roi=("mean_Ft_roi", "mean"),
            std_between_jams_Ft_roi=("mean_Ft_roi", "std"),
            sem_Ft_roi=("mean_Ft_roi", sem_from_series),
            
            mean_N_contactos_roi=("N_contactos_roi", "mean"),
        )
        .reset_index()
    )

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
            if p.exists():
                p.unlink()

    if not idx_path.exists():
        raise FileNotFoundError(f"No se encontro el indice maestro: {idx_path}")

    df_idx = pd.read_csv(idx_path)

    if "area_ratio_nominal" not in df_idx.columns and "area_ratio" in df_idx.columns:
        df_idx["area_ratio_nominal"] = df_idx["area_ratio"].round(3)

    if "r_ratio_nominal" not in df_idx.columns and "r_ratio" in df_idx.columns:
        df_idx["r_ratio_nominal"] = df_idx["r_ratio"].round(2)

    if "geometry_label" not in df_idx.columns:
        df_idx["geometry_label"] = df_idx.apply(get_geometry_label_from_row, axis=1)

    df_idx = select_simulations(df_idx, args)

    if df_idx.empty:
        print("[!] No quedaron simulaciones despues de aplicar filtros.")
        return

    workers = choose_workers(args.workers)

    print("=" * 72)
    print(" ANALISIS DE FUERZA NORMAL PROMEDIO: BULK vs ARCO (ROI DINAMICO)")
    print("=" * 72)
    print(f"[+] Simulaciones seleccionadas: {len(df_idx)}")
    print(f"[+] Workers:                    {workers}")
    print(f"[+] Flush every:                {args.flush_every}")
    print(f"[+] In-flight factor:           {args.in_flight_factor}")
    print(f"[+] Procesar por grupos:        {args.process_by_group}")
    print(f"[+] Guardar muestras:           {args.save_force_samples}")
    if args.save_force_samples:
        print(f"[+] Muestra bulk/atasco:        {args.bulk_sample_per_jam}")
        print(f"[+] Muestra arco/atasco:        {args.arco_sample_per_jam}")
    print(f"[+] Salida:                     {out_dir}")
    print("=" * 72)

    total_tasks_global = 0
    total_ok_global = 0
    total_fail_global = 0
    n_groups = 0

    for group_key, tasks, sims_with_frames, sims_without_frames in iter_task_groups(df_idx, args):
        n_groups += 1
        total_tasks_global += len(tasks)

        print("\n" + "-" * 72)
        print(f"[grupo {n_groups}] {group_key}")
        print(f"  simulaciones con frames: {sims_with_frames}")
        print(f"  simulaciones sin frames: {sims_without_frames}")
        print(f"  atascos a procesar:      {len(tasks)}")
        print("-" * 72)

        ok, fail = process_task_batch(
            tasks=tasks,
            workers=workers,
            args=args,
            summary_out=summary_out,
            error_log_out=error_log_out,
            samples_out=samples_out,
        )

        total_ok_global += ok
        total_fail_global += fail

        del tasks
        gc.collect()

    print("\n" + "=" * 72)
    print(f"[+] Grupos procesados:           {n_groups}")
    print(f"[+] Atascos totales:             {total_tasks_global}")
    print(f"[+] Atascos con arco valido:     {total_ok_global}")
    print(f"[+] Atascos omitidos/con error:  {total_fail_global}")
    print(f"[+] Resumen por atasco:          {summary_out}")

    if error_log_out.exists():
        print(f"[+] Log de errores:              {error_log_out}")

    if samples_out.exists():
        print(f"[+] Muestras para violines:      {samples_out}")

    if summary_out.exists():
        make_configuration_summary(summary_out, config_summary_out)
        print(f"[+] Resumen por configuracion:   {config_summary_out}")

    print("=" * 72)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fuerza normal promedio en bulk y arco, con muestreo opcional para violin plots."
    )

    parser.add_argument("--idx", required=True, help="Ruta a master_sim_index.csv.")
    parser.add_argument("--out", required=True, help="Directorio de salida.")

    parser.add_argument(
        "--contact-mode",
        choices=["pair", "point"],
        default="pair",
        help="pair agrupa contactos por par de particulas; point usa puntos individuales.",
    )

    parser.add_argument("--workers", type=int, default=0, help="Numero de procesos. 0 usa todos menos uno.")
    parser.add_argument("--flush-every", type=int, default=25, help="Cada cuantos atascos escribir buffers.")
    parser.add_argument("--in-flight-factor", type=int, default=2, help="Tareas simultaneas por worker.")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe salidas previas.")

    parser.add_argument("--max-sims", type=int, default=None, help="Procesa solo las primeras N simulaciones.")
    parser.add_argument("--max-jams-per-sim", type=int, default=None, help="Procesa solo los primeros N atascos por simulacion.")

    parser.add_argument("--category", default=None, help="Filtro por category exacta.")
    parser.add_argument("--geometry-label", default=None, help="Filtro por geometria: Disco-Disco, Tri-Disco, etc.")
    parser.add_argument("--chi-values", nargs="*", default=None, help="Filtro por valores de chi.")
    parser.add_argument("--area-ratio", type=float, default=None, help="Filtro por area_ratio_nominal si existe.")
    parser.add_argument("--r-ratio", type=float, default=None, help="Filtro por r_ratio_nominal si existe.")
    parser.add_argument("--ratio-tol", type=float, default=1e-6, help="Tolerancia absoluta para filtros de ratio.")

    parser.add_argument(
        "--process-by-group",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Procesa por bloques de configuracion para liberar memoria entre grupos.",
    )

    parser.add_argument(
        "--save-force-samples",
        action="store_true",
        help="Guarda muestras de fuerzas normales para violin plots.",
    )

    parser.add_argument(
        "--bulk-sample-per-jam",
        type=int,
        default=200,
        help="Maximo de contactos bulk a guardar por atasco. 0 guarda todos.",
    )

    parser.add_argument(
        "--arco-sample-per-jam",
        type=int,
        default=0,
        help="Maximo de contactos arco-arco a guardar por atasco. 0 guarda todos.",
    )

    parser.add_argument(
        "--sample-seed",
        type=int,
        default=12345,
        help="Semilla para muestreo reproducible.",
    )

    parser.add_argument("--verbose-filters", action="store_true", help="Imprime filtros.")

    return parser


def main():
    args = build_parser().parse_args()
    run_analysis(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()