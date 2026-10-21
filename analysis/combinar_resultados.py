#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Junta los resultados ya calculados de dos corridas (ej. las simulaciones de
siempre + una tanda nueva de octogonos) sin volver a analizar los datos
crudos. Despues recalcula las estadisticas agregadas de flujo (rapido).

    --base   raiz de los resultados viejos (default: el repo)
    --nuevo  raiz de los resultados nuevos (ej. Downloads/resultados_octogonos)
    --out    raiz donde queda todo junto (no toca --base ni --nuevo)

En cada raiz se buscan (si existen):
    master_sim_index.csv
    processed_data/1_avalanche_data/resultados_completos_esqueleto.csv
    processed_data/1_avalanche_data/resultados_completos_arcos.csv
    processed_data/fuerzas/datos_v4/resumen_fuerza_normal_por_atasco.csv
    processed_data/fuerzas/datos_v4/resumen_fuerza_normal_por_configuracion.csv
    <presion>/resumen_presion_por_atasco.csv, resumen_presion_por_configuracion.csv
    <presion>/presion_por_particula_<Forma>.parquet  (se enlazan, no se copian)

Se pueden concatenar porque cada fila es de una simulacion, un atasco o una
configuracion, y las del --nuevo son simulaciones distintas. Si una
simulacion (sim_hash) esta en las dos, gana la de --nuevo.

Uso:
    pywork analysis/combinar_resultados.py \\
        --nuevo /mnt/c/Users/Juli/Downloads/resultados_octogonos \\
        --out   /mnt/c/Users/Juli/Downloads/resultados_combinados
    # y despues las figuras con esa raiz:
    RESULTADOS_DIR=/mnt/c/Users/Juli/Downloads/resultados_combinados bash analysis/correr_todo.sh extras figuras
"""
import argparse
import os
import shutil
import sys

import pandas as pd

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

AV = os.path.join("processed_data", "1_avalanche_data")
FZ = os.path.join("processed_data", "fuerzas", "datos_v4")
TABLAS = [
    "master_sim_index.csv",
    os.path.join(AV, "resultados_completos_esqueleto.csv"),
    os.path.join(AV, "resultados_completos_arcos.csv"),
    os.path.join(FZ, "resumen_fuerza_normal_por_atasco.csv"),
    os.path.join(FZ, "resumen_fuerza_normal_por_configuracion.csv"),
]
TABLAS_PRESION = ["resumen_presion_por_atasco.csv", "resumen_presion_por_configuracion.csv"]


def leer(path):
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path, low_memory=False)
    except OSError as e:
        sys.exit(f"[!] No se pudo leer {path}: {e}\n"
                 "    Si esta en OneDrive: 'Mantener siempre en este dispositivo' y volver a correr.")


def juntar(p_base, p_nuevo, p_out, hashes_nuevos):
    a, b = leer(p_base), leer(p_nuevo)
    if a is None and b is None:
        return None
    if a is not None and b is not None and 'sim_hash' in a.columns and hashes_nuevos:
        a = a[~a['sim_hash'].isin(hashes_nuevos)]
    partes = [x for x in (a, b) if x is not None]
    df = pd.concat(partes, ignore_index=True, sort=False)
    os.makedirs(os.path.dirname(p_out) or '.', exist_ok=True)
    df.to_csv(p_out, index=False)
    na, nb = (0 if a is None else len(a)), (0 if b is None else len(b))
    print(f"  {os.path.basename(p_out):45s} {na:>9,} + {nb:>7,} = {len(df):>9,} filas")
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default=REPO_DIR, help='raiz de los resultados viejos (default: el repo)')
    ap.add_argument('--nuevo', required=True, help='raiz de los resultados nuevos')
    ap.add_argument('--out', required=True, help='raiz donde queda todo junto')
    ap.add_argument('--presion_base', default=None,
                    help='carpeta de presion_tensor_arch.py de los viejos (ej. processed_data/presion/tensor_v3_fix_tangencial)')
    ap.add_argument('--presion_nuevo', default=None, help='idem de los nuevos')
    args = ap.parse_args()

    base, nuevo, out = (os.path.abspath(p) for p in (args.base, args.nuevo, args.out))
    if out in (base, nuevo):
        sys.exit("[!] --out tiene que ser una carpeta distinta de --base y --nuevo (no se pisan resultados).")
    print(f"Base:  {base}\nNuevo: {nuevo}\nOut:   {out}\n")

    idx_nuevo = leer(os.path.join(nuevo, "master_sim_index.csv"))
    if idx_nuevo is None:
        sys.exit(f"[!] No hay master_sim_index.csv en {nuevo}")
    hashes = set(idx_nuevo['sim_hash'])

    print("Tablas (base + nuevo = combinado):")
    for rel in TABLAS:
        juntar(os.path.join(base, rel), os.path.join(nuevo, rel), os.path.join(out, rel), hashes)

    if args.presion_base or args.presion_nuevo:
        dir_out = os.path.join(out, "processed_data", "presion", "tensor")
        os.makedirs(dir_out, exist_ok=True)
        print(f"\nPresion -> {dir_out}")
        for nombre in TABLAS_PRESION:
            juntar(os.path.join(args.presion_base or '-', nombre), os.path.join(args.presion_nuevo or '-', nombre),
                   os.path.join(dir_out, nombre), set())
        # parquet por forma: se enlazan (son grandes); si una forma esta en los
        # dos, gana la del nuevo
        for d in (args.presion_base, args.presion_nuevo):
            if not d or not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.startswith('presion_por_particula_') and f.endswith('.parquet'):
                    dst = os.path.join(dir_out, f)
                    if os.path.lexists(dst):
                        os.remove(dst)
                    try:
                        os.symlink(os.path.abspath(os.path.join(d, f)), dst)
                    except OSError:
                        shutil.copy2(os.path.join(d, f), dst)
                    print(f"  {f} -> {d}")

    # Estadisticas agregadas de flujo sobre el indice y las avalanchas combinadas
    os.environ['RESULTADOS_DIR'] = out
    sys.path.insert(0, os.path.join(REPO_DIR, "analysis", "1_avalanchas_y_arcos"))
    sys.path.insert(0, os.path.join(REPO_DIR, "analysis"))
    import flow_analysis  # noqa: E402  (importado despues de fijar RESULTADOS_DIR)
    idx_out = os.path.join(out, "master_sim_index.csv")
    av_out = os.path.join(out, AV, "resultados_completos_esqueleto.csv")
    if os.path.exists(av_out):
        print()
        flow_analysis.main(idx_path=idx_out, av_path=av_out)
        idx = pd.read_csv(idx_out)
        if 'system_type' in idx.columns:
            print("\nSimulaciones por sistema: " +
                  ", ".join(f"{k}: {v}" for k, v in idx['system_type'].value_counts().items()))
    print(f"\nListo. Para las figuras:\n  export RESULTADOS_DIR={out}\n"
          f"  bash analysis/correr_todo.sh extras figuras")


if __name__ == '__main__':
    main()
