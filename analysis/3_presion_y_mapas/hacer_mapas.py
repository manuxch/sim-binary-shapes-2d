#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hace TODOS los mapas de una vez, sin pasos intermedios:

  1. Calcula la escala de los frames (percentiles 2-98 de todas las formas
     juntas) para cada magnitud.
  2. Corre barrido_heatmap.py para cada forma y magnitud (frames + mapa
     promedio + .npz).
  3. Regrafica todos los mapas de una magnitud con la MISMA escala de color
     (graficar_npz_misma_escala.py).

Uso (desde cualquier carpeta):
    pywork analysis/3_presion_y_mapas/hacer_mapas.py

Por defecto: P_reducida y tau_reducida, las 4 formas, ratio 0.1, chi 0 y 0.2,
region x en [-12, 12], y en [-1.5, 27]. Todo se puede cambiar por argumentos
(ver --help). Si se corta, volver a correr lo mismo con --reanudar: no rehace
los frames que ya existen.

Resultado: <salida>/mapas_<magnitud>/heatmap_<Forma>_escala_comun_<bucket>.png

Necesita barrido_heatmap.py y graficar_npz_misma_escala.py (y sus modulos)
en la misma carpeta que este script.
"""
import argparse
import os
import subprocess
import sys
import time

import numpy as np
import pyarrow.parquet as pq

AQUI = os.path.dirname(os.path.abspath(__file__))


def correr(cmd, log):
    print("\n$ " + " ".join(cmd), flush=True)
    log.write("\n$ " + " ".join(cmd) + "\n")
    log.flush()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for linea in proc.stdout:
        # los "N frames generados..." se ven en pantalla pero no llenan el log
        print(linea, end='', flush=True)
        if 'frames generados...' not in linea:
            log.write(linea)
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"Fallo (codigo {proc.returncode}): {' '.join(cmd)}")

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas

def escala_frames(datos, formas, col, pct):
    p_min, p_max = [], []
    for F in formas:
        path = os.path.join(datos, f"presion_por_particula_{F}.parquet")
        v = pq.read_table(path, columns=[col]).column(col).to_numpy(zero_copy_only=False)
        v = v[np.isfinite(v) & (v > 0)]
        a, b = np.percentile(v, pct)
        p_min.append(a)
        p_max.append(b)
        print(f"  {col:13s} {F:10s} p{pct[0]:g}={a:.4g}  p{pct[1]:g}={b:.4g}", flush=True)
    return float(min(p_min)), float(max(p_max))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--datos', default=os.path.join(rutas.PRESION_DIR, 'por_forma'),
                    help='carpeta con presion_por_particula_<Forma>.parquet')
    ap.add_argument('--salida', default=rutas.MAPAS_CALOR_DIR,
                    help='carpeta donde quedan frames y mapas')
    ap.add_argument('--formas', nargs='+', default=['Disco', 'Triangulo', 'Cuadrado', 'Pentagono'])
    ap.add_argument('--magnitudes', nargs='+', default=['P_reducida', 'tau_reducida'])
    ap.add_argument('--ratios', nargs='+', default=['0.1'])
    ap.add_argument('--chis', nargs='+', default=['0.0', '0.2'])
    ap.add_argument('--xlim', nargs=2, default=['-12', '12'])
    ap.add_argument('--ylim', nargs=2, default=['-1.5', '27'])
    ap.add_argument('--pct_frames', type=float, nargs=2, default=[2, 98],
                    help='percentiles para la escala de los frames (default 2 98)')
    ap.add_argument('--workers', default='6')
    ap.add_argument('--chunksize', default='50000')
    ap.add_argument('--reanudar', action='store_true',
                    help='no rehace frames que ya existen (para seguir una corrida cortada)')
    ap.add_argument('--solo_graficar', action='store_true',
                    help='no genera frames: solo regrafica los .npz con escala comun')
    args = ap.parse_args()

    py = sys.executable
    barrido = os.path.join(AQUI, 'barrido_heatmap.py')
    graficar = os.path.join(AQUI, 'graficar_npz_misma_escala.py')
    os.makedirs(args.salida, exist_ok=True)
    log = open(os.path.join(args.salida, 'hacer_mapas.log'), 'a')
    t0 = time.time()

    for col in args.magnitudes:
        dir_mapas = os.path.join(args.salida, f"mapas_{col}")
        os.makedirs(dir_mapas, exist_ok=True)

        if not args.solo_graficar:
            print(f"\n=== {col}: escala de los frames (todas las formas juntas) ===", flush=True)
            vmin, vmax = escala_frames(args.datos, args.formas, col, args.pct_frames)
            print(f"  -> vmin={vmin:.4g}  vmax={vmax:.4g}", flush=True)
            log.write(f"\n{col}: vmin={vmin:.6g} vmax={vmax:.6g}\n")

            for F in args.formas:
                print(f"\n=== {col} / {F} ===", flush=True)
                cmd = [py, barrido,
                       '--csv', os.path.join(args.datos, f"presion_por_particula_{F}.parquet"),
                       '--forma', F, '--col_p', col,
                       '--ratios', *args.ratios, '--chis', *args.chis,
                       '--vmin', f"{vmin:.6g}", '--vmax', f"{vmax:.6g}",
                       '--xlim', *args.xlim, '--ylim', *args.ylim,
                       '--workers', args.workers, '--chunksize', args.chunksize,
                       '--out_dir', os.path.join(args.salida, f"frames_{col}_{F}"),
                       '--out_final', os.path.join(dir_mapas, f"heatmap_{F}.png")]
                if args.reanudar:
                    cmd.append('--reanudar')
                correr(cmd, log)

        print(f"\n=== {col}: misma escala de color para todos los mapas ===", flush=True)
        npz = sorted(os.path.join(dir_mapas, f) for f in os.listdir(dir_mapas)
                     if f.startswith('heatmap_') and f.endswith('.npz'))
        if not npz:
            print(f"  (no hay .npz en {dir_mapas})")
            continue
        correr([py, graficar, *npz, '--col_p', col], log)

    print(f"\nListo en {(time.time() - t0) / 60:.1f} min. Mapas finales:", flush=True)
    for col in args.magnitudes:
        d = os.path.join(args.salida, f"mapas_{col}")
        for f in sorted(os.listdir(d)):
            if '_escala_comun_' in f:
                print(f"  {os.path.join(d, f)}")
    log.close()


if __name__ == '__main__':
    main()
