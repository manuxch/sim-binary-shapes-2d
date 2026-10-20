#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mapas promedio de las componentes del tensor de esfuerzos por separado,
incluida la de afuera de la diagonal (sigma_xy), a partir de
presion_por_particula_<Forma>.parquet (salida de presion_tensor_arch.py).

Para cada celda de una grilla en (x, y) se promedia, pesando por el area de
cada grano y sobre todos los atascos elegidos:

    sigma_xx, sigma_yy, sigma_xy  (en unidades de g, columnas *_reducida)

Figura (una fila):
    sigma_xx | sigma_yy | sigma_xy | perfil de sigma_xy(x)
  - sigma_xx y sigma_yy con la misma escala de color.
  - sigma_xy con escala divergente simetrica (azul < 0 < rojo).
  - el perfil promedia sigma_xy en una franja de alturas (--banda_y) y lo
    compara con -sigma_xy(-x): si el silo es simetrico izquierda-derecha,
    sigma_xy tiene que ser impar en x (las dos curvas coinciden).

Ademas imprime |sigma_xy| / P medio y la asimetria espejo, para
cuantificar que tan grande es la parte fuera de la diagonal.

Convencion (la de presion_tensor_arch.py): compresion positiva,
sigma = -(1/A) sum_c r (x) f. Junto a la pared izquierda la friccion de la
pared sostiene a los granos (fuerza hacia arriba) y da sigma_xy > 0; junto a
la derecha, sigma_xy < 0 (efecto Janssen). Ver analysis/utils/verificar_tensor.py.

Uso:
    pywork analysis/3_presion_y_mapas/mapa_tensor_componentes.py \\
        --parquet <out>/presion_por_particula_Disco.parquet --chi 0.2 --incluir 'Ratio_0p1'
    # varias formas, una figura por forma:
    pywork analysis/3_presion_y_mapas/mapa_tensor_componentes.py \\
        --parquet <out>/presion_por_particula_*.parquet --chi 0.0 0.2
"""
import argparse
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas  # noqa: E402
from estilo_figuras import aplicar_estilo, guardar_figura, REF_LINE_KW  # noqa: E402

COMPONENTES = ['sigma_xx_reducida', 'sigma_yy_reducida', 'sigma_xy_reducida', 'P_reducida', 'tau_reducida']


def acumular(path, incluir, chis, region, xlim, ylim, nx, ny):
    """Suma de area*valor y de area por celda, leyendo el parquet por lotes."""
    import pyarrow.dataset as ds
    import pyarrow.compute as pc
    dset = ds.dataset(path)
    cols = ['sim_path', 'jam_id', 'chi', 'pos_x', 'pos_y', 'area', 'region'] + COMPONENTES
    cols = [c for c in cols if c in dset.schema.names]
    filtro = pc.match_substring_regex(pc.field('sim_path'), incluir) if incluir else None
    suma = {c: np.zeros((ny, nx)) for c in COMPONENTES}
    peso = np.zeros((ny, nx))
    n_granos, atascos = 0, set()
    for lote in dset.to_batches(columns=cols, filter=filtro):
        d = lote.to_pandas()
        if chis is not None and 'chi' in d:
            d = d[np.isclose(d['chi'].to_numpy(float)[:, None], chis, atol=1e-6).any(axis=1)]
        if region and 'region' in d:
            d = d[d['region'].isin(region)]
        d = d[np.isfinite(d['area']) & (d['area'] > 0)]
        if d.empty:
            continue
        ix = np.floor((d['pos_x'].to_numpy() - xlim[0]) / (xlim[1] - xlim[0]) * nx).astype(int)
        iy = np.floor((d['pos_y'].to_numpy() - ylim[0]) / (ylim[1] - ylim[0]) * ny).astype(int)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        k = iy[ok] * nx + ix[ok]
        a = d['area'].to_numpy()[ok]
        peso += np.bincount(k, weights=a, minlength=nx * ny).reshape(ny, nx)
        for c in COMPONENTES:
            v = np.nan_to_num(d[c].to_numpy(float)[ok])
            suma[c] += np.bincount(k, weights=a * v, minlength=nx * ny).reshape(ny, nx)
        n_granos += int(ok.sum())
        atascos.update(zip(d['sim_path'], d['jam_id']))
    return suma, peso, n_granos, len(atascos)


def nombre_forma(path):
    m = re.search(r'presion_por_particula_(.+?)\.parquet', os.path.basename(path))
    return m.group(1) if m else os.path.splitext(os.path.basename(path))[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--parquet', nargs='+', required=True, help='presion_por_particula_<Forma>.parquet (uno o varios)')
    ap.add_argument('--incluir', default=None, help="regex sobre sim_path (ej. 'Ratio_0p1_Chi_0p2_W_2p0')")
    ap.add_argument('--chi', type=float, nargs='+', default=None, help='chi a incluir (default todos)')
    ap.add_argument('--region', nargs='+', default=None, choices=['arco', 'roi', 'bulk'],
                    help='solo granos de estas regiones (default todos)')
    ap.add_argument('--xlim', type=float, nargs=2, default=[-10.5, 10.5])
    ap.add_argument('--ylim', type=float, nargs=2, default=[0.0, 27.0])
    ap.add_argument('--celda', type=float, default=1.0, help='lado de la celda de la grilla (default 1 = d grande)')
    ap.add_argument('--banda_y', type=float, nargs=2, default=[10.0, 20.0],
                    help='alturas que se promedian para el perfil sigma_xy(x)')
    ap.add_argument('--min_peso', type=float, default=5.0,
                    help='celdas con menos area acumulada que esto quedan en blanco')
    ap.add_argument('--out_dir', default=os.path.join(rutas.PRESION_DIR, 'componentes_tensor'))
    args = ap.parse_args()

    aplicar_estilo()
    nx = max(1, int(round((args.xlim[1] - args.xlim[0]) / args.celda)))
    ny = max(1, int(round((args.ylim[1] - args.ylim[0]) / args.celda)))
    xc = args.xlim[0] + (np.arange(nx) + 0.5) * (args.xlim[1] - args.xlim[0]) / nx
    yc = args.ylim[0] + (np.arange(ny) + 0.5) * (args.ylim[1] - args.ylim[0]) / ny
    ext = [args.xlim[0], args.xlim[1], args.ylim[0], args.ylim[1]]

    for path in args.parquet:
        forma = nombre_forma(path)
        suma, peso, n, n_at = acumular(path, args.incluir, args.chi, args.region,
                                       args.xlim, args.ylim, nx, ny)
        if n == 0:
            print(f"[!] {forma}: ningun grano con esos filtros")
            continue
        vacio = peso < args.min_peso
        m = {c: np.where(vacio, np.nan, suma[c] / np.where(peso > 0, peso, 1)) for c in COMPONENTES}

        # --- numeros ---
        tot = {c: suma[c].sum() / peso.sum() for c in COMPONENTES}
        abs_xy = np.nansum(np.abs(m['sigma_xy_reducida']) * peso) / peso[~vacio].sum()
        print(f"\n== {forma}: {n:,} granos, {n_at} atascos"
              + (f", chi {args.chi}" if args.chi else "") + (f", region {args.region}" if args.region else ""))
        print(f"   promedios pesados por area (unidades de g):  sigma_xx {tot['sigma_xx_reducida']:.3f}  "
              f"sigma_yy {tot['sigma_yy_reducida']:.3f}  sigma_xy {tot['sigma_xy_reducida']:+.3f}  "
              f"P {tot['P_reducida']:.3f}  tau {tot['tau_reducida']:.3f}")
        print(f"   |sigma_xy| medio por celda / P medio = {abs_xy / tot['P_reducida']:.3f}")
        banda = (yc >= args.banda_y[0]) & (yc <= args.banda_y[1])
        w = peso[banda]
        perfil = np.nansum(np.nan_to_num(m['sigma_xy_reducida'][banda]) * w, axis=0) / np.where(w.sum(0) > 0, w.sum(0), np.nan)
        espejo = -perfil[::-1]
        ok = np.isfinite(perfil) & np.isfinite(espejo)
        if ok.any():
            asim = np.nansum(np.abs(perfil[ok] - espejo[ok])) / max(np.nansum(np.abs(perfil[ok]) + np.abs(espejo[ok])), 1e-12)
            print(f"   perfil sigma_xy(x) en y in {args.banda_y}: izquierda {np.nanmean(perfil[xc < 0]):+.3f}, "
                  f"derecha {np.nanmean(perfil[xc > 0]):+.3f}  |  asimetria espejo {asim:.3f} (0 = impar perfecto)")

        # --- figura ---
        fig, axs = plt.subplots(1, 4, figsize=(22, 6), gridspec_kw={'width_ratios': [1, 1, 1, 1.1]})
        vmax_d = np.nanpercentile(np.r_[m['sigma_xx_reducida'].ravel(), m['sigma_yy_reducida'].ravel()], 98)
        for ax, c, tit in [(axs[0], 'sigma_xx_reducida', r'$\sigma_{xx}/g$'),
                           (axs[1], 'sigma_yy_reducida', r'$\sigma_{yy}/g$')]:
            im = ax.imshow(m[c], origin='lower', extent=ext, cmap='viridis', vmin=0, vmax=vmax_d, aspect='equal')
            fig.colorbar(im, ax=ax, shrink=0.8)
            ax.set_title(tit)
        lim = np.nanpercentile(np.abs(m['sigma_xy_reducida']), 98)
        im = axs[2].imshow(m['sigma_xy_reducida'], origin='lower', extent=ext, cmap='RdBu_r',
                           vmin=-lim, vmax=lim, aspect='equal')
        fig.colorbar(im, ax=axs[2], shrink=0.8)
        axs[2].set_title(r'$\sigma_{xy}/g$')
        for ax in axs[:3]:
            ax.axhspan(*args.banda_y, color='k', alpha=0.06, lw=0)
            ax.set_xlabel(r'$x$')
        axs[0].set_ylabel(r'$y$')

        axs[3].axhline(0, **REF_LINE_KW)
        axs[3].plot(xc, perfil, '-', color='#D55E00', lw=2, label=r'$\sigma_{xy}(x)$')
        axs[3].plot(xc, espejo, '--', color='#0072B2', lw=2, label=r'$-\sigma_{xy}(-x)$')
        axs[3].set_xlabel(r'$x$')
        axs[3].set_ylabel(r'$\sigma_{xy}/g$' + f'  ($y \\in [{args.banda_y[0]:g}, {args.banda_y[1]:g}]$)')
        axs[3].legend(loc='best')
        fig.suptitle(f"{forma}" + (f",  $\\chi$ = {', '.join(f'{c:g}' for c in args.chi)}" if args.chi else "")
                     + f"   ({n_at} jams)", y=1.02)

        sufijo = ''
        if args.chi:
            sufijo += '_chi' + '-'.join(f"{c:g}".replace('.', 'p') for c in args.chi)
        if args.region:
            sufijo += '_' + '-'.join(args.region)
        out = os.path.join(args.out_dir, f"componentes_tensor_{forma}{sufijo}.pdf")
        guardar_figura(out, fig)
        plt.close(fig)
        print(f"   Figura: {out}")


if __name__ == '__main__':
    main()
