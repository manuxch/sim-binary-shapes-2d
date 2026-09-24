#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visualiza la presión de cada partícula, para UN atasco puntual, a partir
de presion_por_particula.csv (salida de presion_tensor_arch_corregido.py).

Uso:
    python3 graficar_presion_atasco.py --csv presion_por_particula.csv \
        --sim_path /ruta/completa/a/Chi_0p1_W_2p0 --jam_id 1 \
        --out presion_atasco_00001.png
"""
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import Circle, Polygon
from matplotlib.collections import PatchCollection

plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['mathtext.fontset'] = 'stix'


def _parse_coords(s):
    """'coords' llega como JSON (lista de vertices) para poligonos, o
    vacio/NaN para discos."""
    if pd.isna(s) or s == '':
        return None
    return np.array(json.loads(s))


def _dibujar_particulas(ax, df_uno, r, norm, col_p):
    x = df_uno['pos_x'].to_numpy()
    y = df_uno['pos_y'].to_numpy()
    P = df_uno[col_p].to_numpy()
    es_arco = (df_uno['region'] == 'arco').to_numpy()
    es_disco = (df_uno['shape'] == 'Disco').to_numpy()
    vmin = norm.vmin

    # Un patch por particula: circulo real para discos, poligono real
    # (con sus vertices tal cual estan en la simulacion) para el resto.
    # Antes todo se dibujaba como circulo equivalente (misma area), lo
    # cual esta bien para discos pero no representa la forma real de
    # cuadrados/pentagonos/triangulos.
    parches = []
    if 'coords' in df_uno.columns:
        coords_col = df_uno['coords'].to_numpy()
    else:
        coords_col = [None] * len(df_uno)
    for xi, yi, ri, es_d, c in zip(x, y, r, es_disco, coords_col):
        if es_d:
            parches.append(Circle((xi, yi), ri))
        else:
            verts = _parse_coords(c)
            if verts is not None:
                parches.append(Polygon(verts, closed=True))
            else:
                # csv viejo sin 'coords' guardado -> cae al circulo
                # equivalente como ultimo recurso.
                parches.append(Circle((xi, yi), ri))

    pc = PatchCollection(parches, cmap='viridis', norm=norm)
    pc.set_array(np.clip(P, vmin, None))

    # El arco se marca con el borde del propio grano (rojo y mas grueso),
    # no con un anillo aparte -> no hay ambiguedad de a que particula
    # corresponde cada marca.
    pc.set_edgecolor(np.where(es_arco, 'red', 'black'))
    pc.set_linewidth(np.where(es_arco, 1.1, 0.12))
    ax.add_collection(pc)
    ax.set_aspect('equal')
    return pc


def graficar_atasco(df_uno, titulo=None, vmin_pct=2, vmax_pct=98, col_p='P_reducida'):
    if col_p not in df_uno.columns:
        col_p = 'P'  # csv viejo, sin P_reducida todavia
    # Radio real de cada particula, en las mismas unidades que pos_x/pos_y
    # (asume forma ~circular; para poligonos es el radio de un disco de
    # igual area, que es lo mas razonable sin guardar los vertices).
    r = np.sqrt(df_uno['area'].to_numpy() / np.pi)
    x = df_uno['pos_x'].to_numpy()
    y = df_uno['pos_y'].to_numpy()
    P = df_uno[col_p].to_numpy()
    es_arco = df_uno['region'] == 'arco'

    # Antes: vmin/vmax = minimo/maximo absolutos de P. El problema es que
    # en configuraciones bastante homogeneas (ej. chi=0, empaquetamiento
    # cristalino) la gran mayoria de los granos caen en una banda angosta
    # cerca del maximo, y esa banda ocupa una fraccion minuscula del rango
    # de color -> todo se ve "del mismo color". Usando percentiles en vez
    # de extremos absolutos, la escala se estira sobre donde vive la
    # mayoria de los datos; los pocos valores mas extremos que percentil 2
    # o 98 quedan saturados al color limite (mas oscuro/mas claro posible),
    # pero se gana muchisima mas precision visual en el grueso del silo.
    p_pos = P[P > 0]
    if len(p_pos):
        vmin = max(np.percentile(p_pos, vmin_pct), 1e-3)
        vmax = np.percentile(p_pos, vmax_pct)
        if vmax <= vmin:
            vmax = p_pos.max()
    else:
        vmin, vmax = 1e-3, 1.0
    norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)

    fig, (ax_full, ax_zoom) = plt.subplots(
        1, 2, figsize=(11, 9), gridspec_kw={'width_ratios': [1, 1.3]}
    )

    # --- Panel izquierdo: silo completo ---
    pc = _dibujar_particulas(ax_full, df_uno, r, norm, col_p)
    margen = r.max()
    ax_full.set_xlim(x.min() - margen, x.max() + margen)
    ax_full.set_ylim(y.min() - margen, y.max() + margen)
    ax_full.set_xlabel('$x$')
    ax_full.set_ylabel('$y$')
    ax_full.set_title('Silo completo')

    # --- Panel derecho: zoom sobre la zona del arco ---
    if es_arco.any():
        y_arco = df_uno.loc[es_arco, 'pos_y']
        x_arco = df_uno.loc[es_arco, 'pos_x']
        y0, y1 = y_arco.min(), y_arco.max()
        x0, x1 = x_arco.min(), x_arco.max()
        # margen generoso para ver tambien los granos que sostienen el arco
        mx = max((x1 - x0), 4 * r.max())
        my = max((y1 - y0), 4 * r.max())
        xlim = (x0 - mx * 0.8, x1 + mx * 0.8)
        ylim = (max(y.min(), y0 - my * 0.6), y1 + my * 1.8)
    else:
        xlim = (x.min(), x.min() + 8 * r.max())
        ylim = (y.min(), y.min() + 8 * r.max())

    _dibujar_particulas(ax_zoom, df_uno, r, norm, col_p)
    ax_zoom.set_xlim(*xlim)
    ax_zoom.set_ylim(*ylim)
    ax_zoom.set_xlabel('$x$')
    ax_zoom.set_title('Zoom sobre el arco')

    # Recuadro en el panel completo mostrando que zona se amplia
    from matplotlib.patches import Rectangle
    ax_full.add_patch(Rectangle((xlim[0], ylim[0]), xlim[1]-xlim[0], ylim[1]-ylim[0],
                                 fill=False, edgecolor='dimgray', linewidth=0.8, linestyle='--'))

    cbar = fig.colorbar(pc, ax=[ax_full, ax_zoom], label=('Presión reducida $P/g$ (escala log)' if col_p=='P_reducida' else 'Presión $P$ (escala log)'),
                         fraction=0.05, pad=0.02, extend='both')

    from matplotlib.lines import Line2D
    leyenda = [Line2D([0], [0], marker='o', color='w', markerfacecolor='none',
                       markeredgecolor='red', markeredgewidth=1.2, markersize=10,
                       label='arco')]
    ax_zoom.legend(handles=leyenda, loc='upper right', frameon=False)

    fig.suptitle(titulo or '')
    return fig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='presion_por_particula.csv')
    parser.add_argument('--sim_path', required=True)
    parser.add_argument('--jam_id', required=True)
    parser.add_argument('--out', default='presion_atasco.png')
    parser.add_argument('--vmin_pct', type=float, default=2,
                         help='Percentil inferior de P usado como limite de color (default: 2)')
    parser.add_argument('--vmax_pct', type=float, default=98,
                         help='Percentil superior de P usado como limite de color (default: 98)')
    parser.add_argument('--col_p', default='P_reducida', choices=['P', 'P_reducida'],
                         help="Que columna de presion graficar (default: P_reducida = P/g)")
    args = parser.parse_args()

    # jam_id se guarda con ceros a la izquierda (00001) -> forzamos texto
    # para no perderlos al leer, y para poder comparar sin ambiguedad.
    df = pd.read_csv(args.csv, dtype={'jam_id': str})
    jam_id_str = str(args.jam_id).zfill(5)

    df_uno = df[(df['sim_path'] == args.sim_path) & (df['jam_id'] == jam_id_str)]
    if df_uno.empty:
        raise SystemExit(
            f"No encontré filas para sim_path={args.sim_path!r}, jam_id={jam_id_str!r}. "
            f"Revisá que ambos coincidan exactamente con lo que hay en el csv."
        )

    titulo = f"chi={df_uno['chi'].iloc[0]}  —  jam_id={jam_id_str}"
    fig = graficar_atasco(df_uno, titulo=titulo, vmin_pct=args.vmin_pct, vmax_pct=args.vmax_pct, col_p=args.col_p)
    fig.savefig(args.out, dpi=200)
    print(f"Guardado: {args.out}")


if __name__ == '__main__':
    main()