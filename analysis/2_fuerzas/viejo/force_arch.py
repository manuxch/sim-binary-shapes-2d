#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
force_arch.py

Análisis de fuerza normal promedio en bulk y arco.

Objetivo:
    Para cada configuración:
        geometría + tamaño + concentración chi

    calcular:
        <F_n>_bulk
        <F_n>_arco

Definiciones:
    bulk:
        todos los contactos grano-grano del atasco.

    arco:
        contactos arco-arco, es decir, contactos donde ambas partículas
        pertenecen al arco detectado.

Características:
    - Mantiene detección de arco con networkx.
    - No guarda todos los contactos por defecto.
    - Guarda una fila resumen por atasco.
    - Promedia luego por configuración.
    - Usa multiprocessing.
    - Permite tolerancia para filtrar area_ratio y r_ratio.

Salidas:
    resumen_fuerza_normal_por_atasco.csv
    resumen_fuerza_normal_por_configuracion.csv
    errores_procesamiento.csv

Ejemplo disco-disco, area_ratio ~ 0.1, variando chi:

python-contenedor force_arch.py \
  --idx /home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv \
  --out /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/fn_disco_disco_A0p1 \
  --geometry-label Disco-Disco \
  --area-ratio 0.1 \
  --ratio-tol 1e-3 \
  --contact-mode pair \
  --workers 6 \
  --flush-every 10 \
  --verbose-filters \
  --overwrite
"""

import os
import re
import glob
import json
import argparse
import multiprocessing as mp
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

import numpy as np
import pandas as pd
import networkx as nx


# =============================================================================
# ETIQUETAS GEOMÉTRICAS
# =============================================================================

def shape_name_from_sides(sides):
    """
    Convierte número de lados a una etiqueta corta.
    """
    try:
        sides = int(sides)
    except Exception:
        return "Desconocido"

    mapping = {
        1: "Disco",
        3: "Tri",
        4: "Cuad",
        5: "Pent",
    }

    return mapping.get(sides, f"Pol{sides}")


def get_geometry_label_from_row(row):
    """
    Construye una etiqueta geométrica confiable usando grain_json.

    Ejemplos:
        Disco
        Cuad
        Pent
        Disco-Disco
        Cuad-Disco
        Tri-Disco
        Pent-Disco

    Se ordena por radio decreciente.
    """
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

        if len(names) == 1:
            return names[0]

        return "-".join(names)

    except Exception:
        return row.get("system_type", "Desconocido")


# =============================================================================
# PARSEADORES
# =============================================================================

def parse_params(filename):
    """
    Lee parámetros mínimos desde params.in.
    """
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
    """
    Lee atasco_XXXXX.xy.

    Devuelve:
        particles[pid] = {
            "pos": (x, y),
            "r_eff": radio efectivo,
            "type": tipo,
            "shape": etiqueta
        }

    Calcula r_eff una sola vez.
    """
    particles = {}

    with open(filename, "r") as f:
        for line in f:
            p = line.split()

            if not p:
                continue

            pid = int(p[0])

            # Ignorar silo, tapa y paredes.
            if pid < 0:
                continue

            n_sides = int(p[1])

            if n_sides == 1:
                # id 1 x y radio tipo
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
                # id n x1 y1 x2 y2 ... tipo
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
    """
    Devuelve radio efectivo ya calculado.
    """
    return float(p_data["r_eff"])


def read_contacts(filename):
    """
    Lee atasco_contacts_XXXXX.dat.

    Lee columnas:
        id_a id_b px py f_norm f_tan

    Devuelve DataFrame con contactos grano-grano.
    """
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
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=cols)
    except ValueError:
        return pd.DataFrame(columns=cols)

    if df.empty:
        return df

    df["id_a"] = df["id_a"].astype(np.int64)
    df["id_b"] = df["id_b"].astype(np.int64)

    # Solo contactos grano-grano.
    df = df[(df["id_a"] > 0) & (df["id_b"] > 0)].copy()

    if df.empty:
        return df

    # Pares ordenados.
    df["pair_a"] = np.minimum(df["id_a"].values, df["id_b"].values)
    df["pair_b"] = np.maximum(df["id_a"].values, df["id_b"].values)

    return df


# =============================================================================
# DETECCIÓN DE ARCOS CON NETWORKX
# =============================================================================

def es_cimiento_estable(pid, particles, G, path, idx, r_salida):
    """
    Decide si una partícula extrema del camino es cimiento lateral.
    """
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
    """
    Recorta extremos que actúan como cimientos.
    """
    if not path:
        return []

    iL = 0

    while iL < len(path) and es_cimiento_estable(
        path[iL],
        particles,
        G,
        path,
        iL,
        r_salida,
    ):
        iL += 1

    iR = len(path) - 1

    while iR >= iL and es_cimiento_estable(
        path[iR],
        particles,
        G,
        path,
        iR,
        r_salida,
    ):
        iR -= 1

    if iL > iR:
        return []

    return path[iL:iR + 1]


def detectar_arco_primario(G, particles, params):
    """
    Busca el camino de contactos que cruza la salida de izquierda a derecha.

    Mantiene la lógica basada en networkx del código original.
    """
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
                    mejor_arco = purgar_cimientos(
                        path,
                        particles,
                        G,
                        r_salida,
                    )

            except nx.NetworkXNoPath:
                continue

    return mejor_arco


# =============================================================================
# CONTACTOS Y GRAFO
# =============================================================================

def aggregate_contacts_for_graph(df_contacts, particles):
    """
    Agrupa contactos por par de partículas para construir el grafo.
    """
    if df_contacts.empty:
        return pd.DataFrame()

    valid_ids = set(particles.keys())

    df = df_contacts[
        df_contacts["pair_a"].isin(valid_ids) &
        df_contacts["pair_b"].isin(valid_ids)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    grouped = (
        df
        .groupby(["pair_a", "pair_b"], as_index=False)
        .agg(
            px=("px", "mean"),
            py=("py", "mean"),
            f_norm=("f_norm", "sum"),
        )
    )

    return grouped


def build_contact_graph(grouped_contacts, particles):
    """
    Construye grafo de contactos para networkx.
    """
    G = nx.Graph()

    for pid, attr in particles.items():
        G.add_node(pid, **attr)

    for _, row in grouped_contacts.iterrows():
        u = int(row["pair_a"])
        v = int(row["pair_b"])

        if u not in particles or v not in particles:
            continue

        y_max = max(particles[u]["pos"][1], particles[v]["pos"][1])

        # Mantengo el criterio original.
        costo = 10.0 ** min(float(y_max), 100.0)

        G.add_edge(
            u,
            v,
            weight=float(row["f_norm"]),
            costo_arco=costo,
        )

    return G


def prepare_force_dataset(df_contacts, particles, contact_mode="pair"):
    """
    Genera dataset mínimo para calcular fuerza normal promedio.

    contact_mode:
        pair:
            agrupa por par de partículas y suma F_n.
            Recomendado para polígonos.

        point:
            conserva cada punto de contacto.
    """
    valid_ids = set(particles.keys())

    df = df_contacts[
        df_contacts["pair_a"].isin(valid_ids) &
        df_contacts["pair_b"].isin(valid_ids)
    ].copy()

    if df.empty:
        return df

    if contact_mode == "point":
        out = df[["pair_a", "pair_b", "f_norm"]].copy()
        out = out.rename(columns={"pair_a": "id_a", "pair_b": "id_b"})

    elif contact_mode == "pair":
        out = (
            df
            .groupby(["pair_a", "pair_b"], as_index=False)
            .agg(f_norm=("f_norm", "sum"))
        )

        out = out.rename(columns={"pair_a": "id_a", "pair_b": "id_b"})

    else:
        raise ValueError("contact_mode debe ser 'pair' o 'point'.")

    out["id_a"] = out["id_a"].astype(np.int64)
    out["id_b"] = out["id_b"].astype(np.int64)
    out["f_norm"] = out["f_norm"].astype(float)

    return out


# =============================================================================
# RESUMEN POR ATASCO
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


def summarize_fn_one_jam(df_forces, arco_path):
    """
    Calcula fuerza normal promedio en bulk y arco.

    Definiciones:
        bulk:
            todos los contactos grano-grano.

        arco:
            solo contactos arco-arco.
            Es decir, ambos ids pertenecen al arco.
    """
    ids_arco = set(int(x) for x in arco_path)

    id_a = df_forces["id_a"]
    id_b = df_forces["id_b"]
    f_norm = df_forces["f_norm"].to_numpy(dtype=float)

    in_a = id_a.isin(ids_arco).to_numpy()
    in_b = id_b.isin(ids_arco).to_numpy()

    mask_bulk = np.ones(len(df_forces), dtype=bool)
    mask_arco = in_a & in_b

    f_bulk = f_norm[mask_bulk]
    f_arco = f_norm[mask_arco]

    return {
        "N_contactos_bulk": int(f_bulk.size),
        "mean_Fn_bulk": mean_or_nan(f_bulk),
        "std_Fn_bulk": std_or_nan(f_bulk),

        "N_contactos_arco": int(f_arco.size),
        "mean_Fn_arco": mean_or_nan(f_arco),
        "std_Fn_arco": std_or_nan(f_arco),
    }


# =============================================================================
# PROCESAMIENTO DE UN ATASCO
# =============================================================================

def extract_jam_id(xy_file):
    base = os.path.basename(xy_file)
    m = re.search(r"atasco_(\d+)\.xy$", base)

    if m:
        return m.group(1)

    return None


def process_one_jam_task(task):
    """
    Worker multiproceso para procesar un atasco.

    Devuelve solo una fila resumen.
    """
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
    params_file = os.path.join(sim_path, "params.in")
    params = parse_params(params_file)

    frames_dir = os.path.dirname(xy_file)
    contacts_file = os.path.join(frames_dir, f"atasco_contacts_{jam_id}.dat")

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
                "error": "Sin partículas válidas",
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
                "error": "Sin contactos válidos para grafo",
            }

        G = build_contact_graph(grouped_graph, particles)

        arco_path = detectar_arco_primario(G, particles, params)

        if not arco_path:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "No se detectó arco válido",
            }

        df_forces = prepare_force_dataset(
            raw_contacts,
            particles,
            contact_mode=contact_mode,
        )

        if df_forces.empty:
            return {
                "ok": False,
                "xy_file": xy_file,
                "error": "Sin contactos válidos para fuerzas",
            }

        summary = summarize_fn_one_jam(df_forces, arco_path)

        # Metadata mínima.
        for col, value in sim_row.items():
            if col != "path":
                summary[col] = value

        summary["Atasco_ID"] = jam_id
        summary["contact_mode"] = contact_mode
        summary["n_particulas_arco"] = int(len(arco_path))
        summary["arco_ids"] = json.dumps([int(x) for x in arco_path])
        summary["xy_file"] = xy_file

        return {
            "ok": True,
            "summary": summary,
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
    """
    Busca carpeta frames_*.
    """
    sim_path = sim_row["path"]

    if "dirID" in sim_row and pd.notnull(sim_row["dirID"]):
        candidate = os.path.join(sim_path, f"frames_{sim_row['dirID']}")

        if os.path.isdir(candidate):
            return candidate

    candidates = sorted(glob.glob(os.path.join(sim_path, "frames_*")))

    if candidates:
        return candidates[0]

    return None


def select_simulations(df_idx, args):
    """
    Filtros opcionales sobre master_sim_index.csv.
    """
    df = df_idx.copy()

    if args.verbose_filters:
        print(f"[filtro] Inicial: {len(df)} simulaciones")

    if args.system_type is not None and "system_type" in df.columns:
        df = df[df["system_type"] == args.system_type]

        if args.verbose_filters:
            print(f"[filtro] system_type={args.system_type}: {len(df)}")

    if args.geometry_label is not None:
        df = df[df["geometry_label"] == args.geometry_label]

        if args.verbose_filters:
            print(f"[filtro] geometry_label={args.geometry_label}: {len(df)}")

    if args.chi_values:
        chi_vals = [float(x) for x in args.chi_values]
        df = df[df["chi"].astype(float).isin(chi_vals)]

        if args.verbose_filters:
            print(f"[filtro] chi_values={chi_vals}: {len(df)}")

    if args.area_ratio is not None and "area_ratio" in df.columns:
        target = float(args.area_ratio)
        tol = float(args.ratio_tol)

        df = df[
            np.isclose(
                df["area_ratio"].astype(float),
                target,
                rtol=0.0,
                atol=tol,
                equal_nan=False,
            )
        ]

        if args.verbose_filters:
            print(f"[filtro] area_ratio={target} ± {tol}: {len(df)}")

    if args.r_ratio is not None and "r_ratio" in df.columns:
        target = float(args.r_ratio)
        tol = float(args.ratio_tol)

        df = df[
            np.isclose(
                df["r_ratio"].astype(float),
                target,
                rtol=0.0,
                atol=tol,
                equal_nan=False,
            )
        ]

        if args.verbose_filters:
            print(f"[filtro] r_ratio={target} ± {tol}: {len(df)}")

    if args.area_small is not None and "area_small" in df.columns:
        target = float(args.area_small)
        tol = float(args.ratio_tol)

        df = df[
            np.isclose(
                df["area_small"].astype(float),
                target,
                rtol=0.0,
                atol=tol,
                equal_nan=False,
            )
        ]

        if args.verbose_filters:
            print(f"[filtro] area_small={target} ± {tol}: {len(df)}")

    if args.r_small is not None and "r_small" in df.columns:
        target = float(args.r_small)
        tol = float(args.ratio_tol)

        df = df[
            np.isclose(
                df["r_small"].astype(float),
                target,
                rtol=0.0,
                atol=tol,
                equal_nan=False,
            )
        ]

        if args.verbose_filters:
            print(f"[filtro] r_small={target} ± {tol}: {len(df)}")

    if args.max_sims is not None:
        df = df.head(args.max_sims)

        if args.verbose_filters:
            print(f"[filtro] max_sims={args.max_sims}: {len(df)}")

    return df


def make_minimal_sim_row(sim_row_pd):
    """
    Reduce la metadata que viaja a cada worker.
    """
    wanted_cols = [
        "path",
        "sim_hash",
        "system_type",
        "geometry_label",
        "chi",
        "area_ratio",
        "r_ratio",
        "r_small",
        "area_small",
        "tirada",
        "dirID",
    ]

    out = {}

    for col in wanted_cols:
        if col in sim_row_pd.index:
            value = sim_row_pd[col]

            if pd.isna(value):
                value = np.nan

            out[col] = value

    return out


def build_tasks(df_idx, args):
    """
    Construye lista de atascos a procesar.
    """
    tasks = []
    sims_with_frames = 0
    sims_without_frames = 0

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
            })

    return tasks, sims_with_frames, sims_without_frames


def choose_workers(requested_workers):
    """
    Define número de procesos.

    --workers 0:
        usa todos los núcleos menos uno.
    """
    ncpu = mp.cpu_count()

    if requested_workers is None or requested_workers == 0:
        return max(1, ncpu - 1)

    return max(1, min(int(requested_workers), ncpu))


def append_csv_rows(rows, path):
    """
    Escribe lista de diccionarios a CSV incrementalmente.
    """
    if not rows:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows)

    write_header = not path.exists()
    df.to_csv(path, mode="a", header=write_header, index=False)


# =============================================================================
# RESUMEN POR CONFIGURACIÓN
# =============================================================================

def sem_from_series(x):
    x = pd.Series(x).dropna()

    if len(x) <= 1:
        return np.nan

    return float(x.std(ddof=1) / np.sqrt(len(x)))


def make_configuration_summary(summary_path, out_path):
    """
    Promedia sobre todos los atascos de una misma configuración.

    Importante:
        Se promedia primero por atasco y luego entre atascos.
        Así, cada atasco pesa una vez.
    """
    df = pd.read_csv(summary_path)

    if df.empty:
        return

    group_cols = [
        "geometry_label",
        "area_ratio",
        "r_ratio",
        "r_small",
        "area_small",
        "chi",
        "contact_mode",
    ]

    group_cols = [c for c in group_cols if c in df.columns]

    res = (
        df
        .groupby(group_cols, dropna=False)
        .agg(
            n_atascos=("Atasco_ID", "count"),

            mean_Fn_bulk=("mean_Fn_bulk", "mean"),
            std_between_jams_Fn_bulk=("mean_Fn_bulk", "std"),
            sem_Fn_bulk=("mean_Fn_bulk", sem_from_series),
            mean_N_contactos_bulk=("N_contactos_bulk", "mean"),

            mean_Fn_arco=("mean_Fn_arco", "mean"),
            std_between_jams_Fn_arco=("mean_Fn_arco", "std"),
            sem_Fn_arco=("mean_Fn_arco", sem_from_series),
            mean_N_contactos_arco=("N_contactos_arco", "mean"),

            mean_n_particulas_arco=("n_particulas_arco", "mean"),
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

    if args.overwrite:
        for p in [summary_out, config_summary_out, error_log_out]:
            if p.exists():
                p.unlink()

    if not idx_path.exists():
        raise FileNotFoundError(f"No se encontró el índice maestro: {idx_path}")

    df_idx = pd.read_csv(idx_path)

    required_cols = ["path", "sim_hash", "chi", "grain_json"]

    for col in required_cols:
        if col not in df_idx.columns:
            raise ValueError(f"Falta la columna requerida en master_sim_index.csv: {col}")

    df_idx["geometry_label"] = df_idx.apply(get_geometry_label_from_row, axis=1)

    if args.verbose_filters:
        print("[info] Geometrías disponibles:")
        print(
            df_idx["geometry_label"]
            .value_counts(dropna=False)
            .sort_index()
            .to_string()
        )
        print()

    df_idx = select_simulations(df_idx, args)

    if df_idx.empty:
        print("[!] No quedaron simulaciones después de aplicar filtros.")
        return

    if args.verbose_filters:
        cols_show = [
            "geometry_label",
            "chi",
            "area_ratio",
            "r_ratio",
            "area_small",
            "r_small",
            "path",
        ]
        cols_show = [c for c in cols_show if c in df_idx.columns]

        print("\n[info] Simulaciones seleccionadas:")
        print(
            df_idx[cols_show]
            .sort_values([c for c in ["geometry_label", "area_ratio", "r_ratio", "chi"] if c in cols_show])
            .to_string(index=False)
        )
        print()

    tasks, sims_with_frames, sims_without_frames = build_tasks(df_idx, args)

    if not tasks:
        print("[!] No se encontraron atascos para procesar.")
        return

    workers = choose_workers(args.workers)
    flush_every = max(1, int(args.flush_every))

    print("=" * 72)
    print(" ANÁLISIS DE FUERZA NORMAL PROMEDIO: BULK vs ARCO")
    print("=" * 72)
    print(f"[+] Simulaciones seleccionadas: {len(df_idx)}")
    print(f"[+] Simulaciones con frames:    {sims_with_frames}")
    print(f"[+] Simulaciones sin frames:    {sims_without_frames}")
    print(f"[+] Atascos a procesar:         {len(tasks)}")
    print(f"[+] Modo de contacto:           {args.contact_mode}")
    print(f"[+] Definición de arco:         arco_arco")
    print(f"[+] Workers:                    {workers}")
    print(f"[+] Flush every:                {flush_every}")
    print(f"[+] Salida:                     {out_dir}")
    print("=" * 72)

    total_ok = 0
    total_fail = 0

    buffer_summary = []
    buffer_errors = []

    def flush_buffers():
        nonlocal buffer_summary, buffer_errors

        if buffer_summary:
            append_csv_rows(buffer_summary, summary_out)
            buffer_summary = []

        if buffer_errors:
            append_csv_rows(buffer_errors, error_log_out)
            buffer_errors = []

    if workers == 1:
        for k, task in enumerate(tasks, start=1):
            result = process_one_jam_task(task)

            if result and result.get("ok"):
                buffer_summary.append(result["summary"])
                total_ok += 1
            else:
                total_fail += 1
                buffer_errors.append({
                    "xy_file": result.get("xy_file") if result else "unknown",
                    "error": result.get("error") if result else "unknown",
                })

            if k % flush_every == 0:
                flush_buffers()
                print(
                    f"[+] Procesados {k}/{len(tasks)} | ok={total_ok} | fail={total_fail}",
                    flush=True,
                )

    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            task_iter = iter(tasks)
            futures = set()
            max_in_flight = max(1, workers * args.in_flight_factor)

            for _ in range(min(max_in_flight, len(tasks))):
                try:
                    task = next(task_iter)
                    futures.add(executor.submit(process_one_jam_task, task))
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

                    if result and result.get("ok"):
                        buffer_summary.append(result["summary"])
                        total_ok += 1
                    else:
                        total_fail += 1
                        buffer_errors.append({
                            "xy_file": result.get("xy_file") if result else "unknown",
                            "error": result.get("error") if result else "unknown",
                        })

                    try:
                        task = next(task_iter)
                        futures.add(executor.submit(process_one_jam_task, task))
                    except StopIteration:
                        pass

                    if k % flush_every == 0:
                        flush_buffers()
                        print(
                            f"[+] Procesados {k}/{len(tasks)} | ok={total_ok} | fail={total_fail}",
                            flush=True,
                        )

    flush_buffers()

    print("\n" + "=" * 72)
    print(f"[+] Atascos totales:             {len(tasks)}")
    print(f"[+] Atascos con arco válido:     {total_ok}")
    print(f"[+] Atascos omitidos/con error:  {total_fail}")
    print(f"[+] Resumen por atasco:          {summary_out}")

    if error_log_out.exists():
        print(f"[+] Log de errores:              {error_log_out}")

    if summary_out.exists():
        make_configuration_summary(summary_out, config_summary_out)
        print(f"[+] Resumen por configuración:   {config_summary_out}")

    print("=" * 72)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fuerza normal promedio en bulk y arco para atascos granulares."
    )

    parser.add_argument(
        "--idx",
        required=True,
        help="Ruta a master_sim_index.csv.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Directorio de salida.",
    )

    parser.add_argument(
        "--contact-mode",
        choices=["pair", "point"],
        default="pair",
        help="pair agrupa contactos por par de partículas; point usa puntos individuales.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=0,
        help="Número de procesos. 0 usa todos los núcleos menos uno.",
    )

    parser.add_argument(
        "--flush-every",
        type=int,
        default=25,
        help="Cada cuántos atascos escribir buffers a disco.",
    )

    parser.add_argument(
        "--in-flight-factor",
        type=int,
        default=2,
        help="Cantidad máxima de tareas simultáneas encoladas por worker.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribe salidas previas.",
    )

    parser.add_argument(
        "--max-sims",
        type=int,
        default=None,
        help="Procesa solo las primeras N simulaciones.",
    )

    parser.add_argument(
        "--max-jams-per-sim",
        type=int,
        default=None,
        help="Procesa solo los primeros N atascos por simulación.",
    )

    parser.add_argument(
        "--system-type",
        default=None,
        help="Filtro por system_type exacto.",
    )

    parser.add_argument(
        "--geometry-label",
        default=None,
        help="Filtro por geometría real: Disco, Disco-Disco, Tri-Disco, Cuad-Disco, Pent-Disco, etc.",
    )

    parser.add_argument(
        "--chi-values",
        nargs="*",
        default=None,
        help="Filtro por valores de chi. Ej: --chi-values 0.0 0.08 0.16",
    )

    parser.add_argument(
        "--area-ratio",
        type=float,
        default=None,
        help="Filtro por area_ratio.",
    )

    parser.add_argument(
        "--r-ratio",
        type=float,
        default=None,
        help="Filtro por r_ratio.",
    )

    parser.add_argument(
        "--area-small",
        type=float,
        default=None,
        help="Filtro por area_small.",
    )

    parser.add_argument(
        "--r-small",
        type=float,
        default=None,
        help="Filtro por r_small.",
    )

    parser.add_argument(
        "--ratio-tol",
        type=float,
        default=1e-3,
        help="Tolerancia absoluta para comparar area_ratio, r_ratio, area_small y r_small.",
    )

    parser.add_argument(
        "--verbose-filters",
        action="store_true",
        help="Imprime cuántas simulaciones quedan después de cada filtro.",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    run_analysis(args)


if __name__ == "__main__":
    mp.freeze_support()
    main()