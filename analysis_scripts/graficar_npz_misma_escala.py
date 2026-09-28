#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regrafica los mapas promediados que guarda barrido_heatmap.py (.npz, uno
por forma y bucket) con UNA escala de color comun a todos, sin volver a
decodificar frames.

Los .npz tienen la presion media en unidades fisicas (cada corrida la
decodifico con su propia escala de frames), asi que se pueden comparar
directamente entre formas.

Uso (en la carpeta donde estan los .npz):
    python3 graficar_npz_misma_escala.py heatmap_*.npz
    # escala = percentiles 1-99 de TODOS los mapas juntos

    python3 graficar_npz_misma_escala.py heatmap_*.npz --vmin 5 --vmax 200
    # escala fija a mano

Genera, junto a cada .npz, heatmap_<forma>_escala_comun_<bucket>.png
(no pisa los .png originales).

Necesita barrido_heatmap.py (y sus modulos) en la misma carpeta.
"""
import argparse
import os
import re

import numpy as np

import barrido_heatmap as b

RE_NOMBRE = re.compile(r'^heatmap_(.+?)_((?:ratio|chi)[0-9p]+(?:_chi[0-9p]+)?)$')


def forma_y_bucket(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    m = RE_NOMBRE.match(stem)
    if m:
        return m.group(1), m.group(2)
    return stem.replace('heatmap_', '', 1), 'todos'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('npz', nargs='+', help='archivos .npz de barrido_heatmap.py')
    parser.add_argument('--pct', type=float, nargs=2, default=[1, 99], metavar=('MIN', 'MAX'),
                        help='percentiles para la escala comun (default: 1 99)')
    parser.add_argument('--vmin', type=float, default=None, help='fuerza el minimo de la escala')
    parser.add_argument('--vmax', type=float, default=None, help='fuerza el maximo de la escala')
    parser.add_argument('--col_p', default='P_reducida',
                        help='magnitud graficada, solo para la etiqueta (default: P_reducida)')
    args = parser.parse_args()

    mapas = []
    for path in sorted(args.npz):
        d = np.load(path)
        forma, bucket = forma_y_bucket(path)
        mapas.append((path, forma, bucket, d['P_media'], int(d['n_imagenes'])))
        print(f"  {os.path.basename(path)}: forma={forma}, {bucket}, {int(d['n_imagenes'])} atascos")

    vmin, vmax = b.escala_de_mapas([m[3] for m in mapas], args.pct[0], args.pct[1])
    if args.vmin is not None:
        vmin = args.vmin
    if args.vmax is not None:
        vmax = args.vmax
    print(f"Escala comun: vmin={vmin:.4g}  vmax={vmax:.4g}")

    for path, forma, bucket, P_media, n in mapas:
        base = os.path.join(os.path.dirname(path) or '.', f"heatmap_{forma}_escala_comun.png")
        b.graficar_bucket(P_media, n, forma, bucket, base, vmin, vmax, args.col_p)


if __name__ == '__main__':
    main()
