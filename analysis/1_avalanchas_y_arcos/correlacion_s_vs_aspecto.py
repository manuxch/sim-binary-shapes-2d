#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correlacion entre el tamano medio de avalancha y la relacion de aspecto de
los arcos, un punto por (sistema, chi).

Eje x (variable independiente): tamano medio de avalancha, en numero de
granos o en masa, de los granos grandes o del total (grandes + chicos):
  s, big    <s>    = tamano_big                     (granos grandes)
  s, total  <s_T>  = total_mix                      (todos los granos)
  masa, big   <M>   = tamano_big * m_grande
  masa, total <M_T> = <M> + (total_mix - tamano_big) * m_chico
(masas de graficar_masa_avalancha.py: densidad * area de params.in).
Eje y: relacion de aspecto del arco <L>/(2<H>), con error por bootstrap,
igual que la figura 15 de graficos_finales.py.

Por defecto hace las cuatro figuras (s/masa x big/total). Se usa un solo
orificio (--W, el _W_ de la carpeta) y una razon de areas (--area_ratio);
los sistemas puros entran como chi = 0 de cada mezcla. El coeficiente de
Pearson de cada sistema solo se imprime por pantalla.

Salida (processed_data/5_graficos_finales/):
  17-AR-vs-<s|M>-<big|total>-ratio-<r>-W-<W>[-logs].pdf  y  ..._datos.csv

Uso:
    python3 analysis/1_avalanchas_y_arcos/correlacion_s_vs_aspecto.py
    python3 analysis/1_avalanchas_y_arcos/correlacion_s_vs_aspecto.py --logs
    python3 analysis/1_avalanchas_y_arcos/correlacion_s_vs_aspecto.py --cantidad masa --especie total
"""
import argparse
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3_presion_y_mapas"))  # ejes_log
import rutas  # noqa: E402
from estilo_figuras import aplicar_estilo, estilo_sistema, guardar_figura, ERRORBAR_KW, SYSTEM_NAME_MAP  # noqa: E402
from graficar_masa_avalancha import masas_por_simulacion  # noqa: E402
from graficos_finales import aspecto_medio  # noqa: E402
from correlacion_s_vs_P import ejes_log  # noqa: E402

W_REGEX = re.compile(r'_W_([0-9]+(?:p[0-9]+)?)')
COLUMNA = {('s', 'big'): 'tamano_big', ('s', 'total'): 'total_mix',
           ('masa', 'big'): 'masa_big', ('masa', 'total'): 'masa_total'}
ETIQUETA_X = {('s', 'big'): r'Mean Avalanche Size $\langle s \rangle$',
              ('s', 'total'): r'Mean Avalanche Size $\langle s_{\rm T} \rangle$ (all grains)',
              ('masa', 'big'): r'Mean Avalanche Mass $\langle M \rangle$',
              ('masa', 'total'): r'Mean Avalanche Mass $\langle M_{\rm T} \rangle$ (all grains)'}


def ancho_W(ruta):
    m = W_REGEX.search(str(ruta))
    return float(m.group(1).replace('p', '.')) if m else np.nan


def filtrar(df, W, area_ratio, chi_max):
    """Un orificio, una razon de areas (chi = 0 se conserva) y los puros como
    chi = 0 de cada mezcla con el mismo grano grande."""
    df = df[np.isclose(df['path'].map(ancho_W), W) & (df['chi'] <= chi_max + 1e-9)]
    if 'area_ratio_nominal' in df.columns:
        df = df[np.isclose(df['area_ratio_nominal'].fillna(1.0), area_ratio, atol=1e-3) | (df['chi'] == 0)]
    st = df['system_type'].astype(str)
    puros, mezclas = df[~st.str.contains('-')], df[st.str.contains('-')]
    extra = [puros[puros['system_type'] == str(sis).split('-')[0]].assign(system_type=sis)
             for sis in mezclas['system_type'].unique()]
    df = pd.concat([mezclas] + extra, ignore_index=True)
    df['sistema'] = df['system_type'].map(lambda s: SYSTEM_NAME_MAP.get(str(s), str(s)))
    return df


def avalanchas(path_av, path_idx, W, area_ratio, chi_max):
    av = pd.read_csv(path_av)
    idx = pd.read_csv(path_idx)
    if 'area_ratio_nominal' not in idx.columns and 'area_ratio' in idx.columns:
        idx['area_ratio_nominal'] = idx['area_ratio'].round(3)
    idx = idx[idx['sim_hash'].isin(av['sim_hash'].unique())].drop_duplicates('sim_hash')
    idx = pd.concat([idx, idx.apply(masas_por_simulacion, axis=1)], axis=1)
    cols = [c for c in ('sim_hash', 'system_type', 'chi', 'area_ratio_nominal', 'path', 'm_grande', 'm_chico')
            if c in idx.columns]
    df = av.merge(idx[cols], on='sim_hash', how='inner')
    df['masa_big'] = df['tamano_big'] * df['m_grande']
    df['masa_total'] = df['masa_big'] + ((df['total_mix'] - df['tamano_big']).clip(lower=0)
                                         * df['m_chico'].fillna(0.0))
    return filtrar(df, W, area_ratio, chi_max)


def arcos(path_arcos, W, area_ratio, chi_max, min_arcos):
    df = filtrar(pd.read_csv(path_arcos), W, area_ratio, chi_max)
    filas = []
    for (sis, chi), g in df.groupby(['sistema', 'chi']):
        r = aspecto_medio(g)
        if r['count'] >= min_arcos:
            filas.append(dict(sistema=sis, chi=chi, AR=r['mean'], AR_sem=r['sem'], n_arcos=r['count']))
    return pd.DataFrame(filas)


def graficar(d, out, etiqueta_x, logs, area_ratio):
    aplicar_estilo()
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for sis in sorted(d['sistema'].unique(), key=lambda s: (s != 'Disco(G)-Disco(C)', s)):
        sub = d[d['sistema'] == sis].sort_values('chi')
        color, marker, etiqueta = estilo_sistema(sis)
        ax.errorbar(sub['x'], sub['AR'], xerr=sub['x_sem'], yerr=sub['AR_sem'], color=color, marker=marker,
                    ls='none', ms=7, label=etiqueta, **ERRORBAR_KW)
    ax.set_xlabel(etiqueta_x)
    ax.set_ylabel('Arch Aspect Ratio')
    if logs:
        ejes_log(ax, True, False)
    ax.legend(title=rf"$R_{{\rm a}} = {area_ratio:g}$", frameon=False, loc='best', fontsize='small')
    return guardar_figura(out, fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--av', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_esqueleto.csv'))
    ap.add_argument('--idx', default=rutas.MASTER_INDEX)
    ap.add_argument('--arcos', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_arcos.csv'))
    ap.add_argument('--cantidad', choices=['s', 'masa', 'ambas'], default='ambas',
                    help='s: numero de granos; masa; ambas (default)')
    ap.add_argument('--especie', choices=['big', 'total', 'ambas'], default='ambas',
                    help='big: granos grandes; total: grandes + chicos; ambas (default)')
    ap.add_argument('--W', type=float, default=2.0, help='orificio W de la carpeta (default 2.0)')
    ap.add_argument('--area_ratio', type=float, default=0.1)
    ap.add_argument('--chi_max', type=float, default=0.4)
    ap.add_argument('--min_arcos', type=int, default=20, help='minimo de arcos por punto (default 20)')
    ap.add_argument('--logs', action='store_true', help='eje x (<s> o <M>) logaritmico')
    args = ap.parse_args()

    av = avalanchas(args.av, args.idx, args.W, args.area_ratio, args.chi_max)
    ar = arcos(args.arcos, args.W, args.area_ratio, args.chi_max, args.min_arcos)
    if av.empty or ar.empty:
        sys.exit(f"[!] Sin datos despues de filtrar: {len(av)} avalanchas, {len(ar)} puntos de arcos "
                 f"(revisar --W, --area_ratio).")

    cantidades = ['s', 'masa'] if args.cantidad == 'ambas' else [args.cantidad]
    especies = ['big', 'total'] if args.especie == 'ambas' else [args.especie]
    os.makedirs(rutas.GRAFICOS_FINALES_DIR, exist_ok=True)
    for cant in cantidades:
        for esp in especies:
            col = COLUMNA[(cant, esp)]
            g = av.groupby(['sistema', 'chi'])[col].agg(['mean', 'sem', 'count']).reset_index()
            g.columns = ['sistema', 'chi', 'x', 'x_sem', 'n_avalanchas']
            d = g.merge(ar, on=['sistema', 'chi'], how='inner').dropna(subset=['x', 'AR'])
            nombre = (f"17-AR-vs-{'M' if cant == 'masa' else 's'}-{esp}-ratio-{args.area_ratio:g}-W-{args.W:g}"
                      f"{'-logs' if args.logs else ''}")
            out = os.path.join(rutas.GRAFICOS_FINALES_DIR, nombre + '.pdf')
            d.sort_values(['sistema', 'chi']).to_csv(os.path.join(rutas.GRAFICOS_FINALES_DIR, nombre + '_datos.csv'),
                                                     index=False)
            print(f"\n{nombre}: Pearson r (solo informativo)")
            for sis, s in d.groupby('sistema'):
                x = np.log(s['x']) if args.logs else s['x']
                r = np.corrcoef(x, s['AR'])[0, 1] if len(s) > 2 else np.nan
                print(f"  {sis:20s} r = {r:+.2f}  ({len(s)} puntos)")
            print(f"Figura: {graficar(d, out, ETIQUETA_X[(cant, esp)], args.logs, args.area_ratio)}")


if __name__ == '__main__':
    main()
