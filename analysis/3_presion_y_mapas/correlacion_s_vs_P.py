#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correlacion entre el tamano medio de avalancha <s> y la presion media <P>
de los atascos, un punto por simulacion (sistema, chi, razon de areas,
orificio).

Figura (por defecto): un panel por sistema; el color de cada punto es chi
(barra de color). Se usa un solo orificio W (el _W_ de la carpeta, --W,
default 2.0), para que <s> sea comparable; si aun quedan varias familias
(distinto Radio_salida), cada una tiene su marcador. Solo se unen con una linea
los puntos de una misma familia, en orden de chi. Eje y logaritmico (<s> va
de ~1 a cientos); --liny para lineal. --un_panel: todos los sistemas en un
mismo panel, color por sistema (la version anterior).

  <s>  media de 'tamano_big' (granos grandes por avalancha, la misma <s> de
       graficos_finales.py) o de 'total_mix' (--s total), sobre todas las
       avalanchas de la simulacion. Error: SEM entre avalanchas.
  <P>  presion reducida P/g de la region (--region arco|roi|bulk), media
       pesada por area de grano sobre todos los atascos de la simulacion.
       Error: SEM entre atascos (igual que comparar_presion_por_chi.py).
       Con --magnitud tau se usa el deviador tau/g en vez de P.

Entradas:
  resumen_presion_por_atasco.csv     (presion_tensor_arch.py)
  resultados_completos_esqueleto.csv (processor.py)
  master_sim_index.csv               (indexer.py: sim_hash <-> carpeta)
La simulacion se empareja por las dos ultimas carpetas de la ruta
(BARRIDO_.../Chi_..._W_...), asi no importa si el indice y la presion se
calcularon con el disco montado en rutas distintas.

Salida (en processed_data/5_graficos_finales/ por defecto):
  16-s-vs-P-<region>-ratio-<r>-W-<W>.pdf  y  ..._datos.csv con los valores graficados.
Coeficiente de Pearson r de cada sistema en el titulo de su panel (con
eje y log, r se calcula con log<s>).

Uso:
    python3 analysis/3_presion_y_mapas/correlacion_s_vs_P.py \\
        --presion processed_data/presion/tensor_nuevo/resumen_presion_por_atasco.csv
    python3 analysis/3_presion_y_mapas/correlacion_s_vs_P.py --region roi --W 2.0 --radio_salida 1.0
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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # rutas.py y estilo_figuras.py
import rutas  # noqa: E402
from estilo_figuras import (aplicar_estilo, estilo_sistema, guardar_figura,  # noqa: E402
                            ERRORBAR_KW, SYSTEM_NAME_MAP)
from comparar_presion_por_chi import filtrar_lotes_confirmados, _estadistica_pesada  # noqa: E402

COLUMNA_PRESION = {'P': 'SumP_reducida', 'tau': 'SumTau_reducida'}
ETIQUETA_X = {'P': r'Reduced Mean Pressure $\langle P\rangle / g$',
              'tau': r'Reduced Mean Shear Stress $\langle \tau\rangle / g$'}
ETIQUETA_Y = {'big': r'Mean Avalanche Size $\langle s \rangle$',
              'total': r'Mean Avalanche Size $\langle s \rangle$ (all grains)'}
COLUMNA_S = {'big': 'tamano_big', 'total': 'total_mix'}
NOMBRE_REGION = {'arco': 'arch', 'roi': 'ROI', 'bulk': 'bulk'}


W_REGEX = re.compile(r'_W_([0-9]+(?:p[0-9]+)?)')
MARCADORES = ['o', 's', '^', 'D', 'v', 'p', 'h', '<', '>']


def ancho_W(clave):
    m = W_REGEX.search(str(clave))
    return float(m.group(1).replace('p', '.')) if m else np.nan


def clave_carpeta(ruta):
    """Las dos ultimas carpetas de una ruta: 'BARRIDO_X/Chi_0p2_W_2p0'."""
    partes = os.path.normpath(str(ruta)).replace('\\', '/').rstrip('/').split('/')
    return '/'.join(partes[-2:])


def presion_por_simulacion(path_csv, magnitud, region):
    df = pd.read_csv(path_csv, dtype={'lote': str, 'jam_id': str})
    df = filtrar_lotes_confirmados(df, path_csv)
    col_sum, col_area = f"{COLUMNA_PRESION[magnitud]}_{region}", f"Area_{region}"
    faltan = [c for c in (col_sum, col_area) if c not in df.columns]
    if faltan:
        sys.exit(f"[!] Al csv de presion le faltan las columnas {faltan}")
    filas = []
    for sim_path, g in df.groupby('sim_path'):
        w = g[col_area].to_numpy(float)
        with np.errstate(invalid='ignore', divide='ignore'):
            x = g[col_sum].to_numpy(float) / w
        media, std, sem, n, _ = _estadistica_pesada(x, w)
        filas.append(dict(clave=clave_carpeta(sim_path), sim_path=sim_path, P=media, P_sem=sem,
                          n_atascos=n))
    return pd.DataFrame(filas)


def avalanchas_por_simulacion(path_av, path_idx, col_s, solo_con_arco):
    av = pd.read_csv(path_av)
    if solo_con_arco:
        if 'atasco_id' not in av.columns:
            sys.exit("[!] El esqueleto no tiene atasco_id: volve a correr processor.py (version nueva).")
        av = av[av['atasco_id'].notna()]
    idx = pd.read_csv(path_idx)
    if 'area_ratio_nominal' not in idx.columns and 'area_ratio' in idx.columns:
        idx['area_ratio_nominal'] = idx['area_ratio'].round(3)
    idx = idx.drop_duplicates(subset=['sim_hash'])
    idx['clave'] = idx['path'].map(clave_carpeta)
    g = av.groupby('sim_hash')[col_s].agg(['mean', 'sem', 'count']).reset_index()
    g.columns = ['sim_hash', 's', 's_sem', 'n_avalanchas']
    cols = [c for c in ('sim_hash', 'clave', 'system_type', 'chi', 'area_ratio_nominal', 'Radio_salida')
            if c in idx.columns]
    return g.merge(idx[cols], on='sim_hash', how='inner')


def agregar_puros(df):
    """Las simulaciones puras (chi = 0, system_type sin '-', ej. 'Cuad') se
    suman como punto chi = 0 de cada mezcla con el mismo grano grande
    ('Cuad-Disco'), igual que la referencia pura de graficos_finales.py."""
    st = df['system_type'].astype(str)
    puros, mezclas = df[~st.str.contains('-')], df[st.str.contains('-')]
    extra = []
    for sis in mezclas['system_type'].unique():
        base = str(sis).split('-')[0]
        p = puros[puros['system_type'] == base]
        if len(p) and not ((mezclas['system_type'] == sis) & (mezclas['chi'] == 0)).any():
            extra.append(p.assign(system_type=sis))
    return pd.concat([mezclas] + extra, ignore_index=True) if len(mezclas) else df


def pearson(x, y, logy):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if logy:
        ok = y > 0
        x, y = x[ok], np.log(y[ok])
    return np.corrcoef(x, y)[0, 1] if len(x) > 2 else np.nan


def graficar_paneles(df, out, magnitud, region, tipo_s, logx, logy, error, chi_max):
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable
    aplicar_estilo()
    sistemas = sorted(df['sistema'].unique(), key=lambda s: (s != 'Disco(G)-Disco(C)', s))
    ncol = 2 if len(sistemas) > 1 else 1
    nfil = int(np.ceil(len(sistemas) / ncol))
    fig, axes = plt.subplots(nfil, ncol, figsize=(6.2 * ncol, 4.6 * nfil), sharex=True, sharey=True,
                             squeeze=False)
    norm, cmap = Normalize(0, chi_max), plt.cm.viridis
    familias = sorted(df[['Radio_salida', 'W']].drop_duplicates().itertuples(index=False, name=None),
                      key=lambda t: (np.nan_to_num(t[0]), np.nan_to_num(t[1])))
    marcador = {f: MARCADORES[i % len(MARCADORES)] for i, f in enumerate(familias)}
    vistos = set()
    for ax, sis in zip(axes.flat, sistemas):
        sub = df[df['sistema'] == sis]
        for fam, g in sub.groupby(['Radio_salida', 'W'], dropna=False):
            fam = tuple(fam)
            g = g.sort_values('chi')
            m = marcador.get(fam, 'o')
            ax.plot(g['P'], g['s'], color='0.65', lw=0.9, zorder=1)
            if error:
                ax.errorbar(g['P'], g['s'], xerr=g['P_sem'], yerr=g['s_sem'], fmt='none', ecolor='0.55',
                            elinewidth=0.8, capsize=2, zorder=2)
            lbl = None
            if len(familias) > 1 and fam not in vistos:
                lbl = f"$R_{{out}}$ = {fam[0]:g}, W = {fam[1]:g}"
                vistos.add(fam)
            ax.scatter(g['P'], g['s'], c=g['chi'], cmap=cmap, norm=norm, marker=m, s=55,
                       edgecolors='black', linewidths=0.6, zorder=3, label=lbl)
        r = pearson(sub['P'], sub['s'], logy)
        etiqueta = estilo_sistema(sis)[2]
        ax.set_title(f"{etiqueta}  ($r$ = {r:.2f})" if np.isfinite(r) else etiqueta, fontsize='medium')
        if logx:
            ax.set_xscale('log')
        if logy:
            from matplotlib.ticker import ScalarFormatter, NullFormatter
            ax.set_yscale('log')
            ax.yaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_minor_formatter(NullFormatter())
    for ax in axes.flat[len(sistemas):]:
        ax.set_visible(False)
    for ax in axes[-1, :]:
        ax.set_xlabel(f"{ETIQUETA_X[magnitud]} ({NOMBRE_REGION[region]})")
    for ax in axes[:, 0]:
        ax.set_ylabel(ETIQUETA_Y[tipo_s])
    if len(familias) > 1:
        fig.legend(loc='lower center', ncol=min(len(familias), 4), frameon=False, fontsize='small',
                   bbox_to_anchor=(0.45, -0.02))
    fig.tight_layout(rect=(0, 0.05 if len(familias) > 1 else 0, 0.9, 1))
    cax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, label=r'$\chi$')
    return guardar_figura(out, fig)


def graficar(df, out, magnitud, region, tipo_s, logx, logy, error):
    aplicar_estilo()
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sistemas = sorted(df['sistema'].unique(), key=lambda s: (s != 'Disco(G)-Disco(C)', s))
    for sis in sistemas:
        sub = df[df['sistema'] == sis].sort_values('chi')
        color, marker, etiqueta = estilo_sistema(sis)
        r = sub[['P', 's']].corr().iloc[0, 1] if len(sub) > 2 else np.nan
        lbl = f"{etiqueta} ($r$ = {r:.2f})" if np.isfinite(r) else etiqueta
        xerr = sub['P_sem'] if error else None
        yerr = sub['s_sem'] if error else None
        ax.errorbar(sub['P'], sub['s'], xerr=xerr, yerr=yerr, color=color, marker=marker, ls='-', lw=0.8,
                    ms=7, label=lbl, **ERRORBAR_KW)
    r_tot = df[['P', 's']].corr().iloc[0, 1] if len(df) > 2 else np.nan
    ax.set_xlabel(f"{ETIQUETA_X[magnitud]} ({NOMBRE_REGION[region]})")
    ax.set_ylabel(ETIQUETA_Y[tipo_s])
    if logx:
        ax.set_xscale('log')
    if logy:
        ax.set_yscale('log')
    ax.legend(title=f"all: $r$ = {r_tot:.2f}" if np.isfinite(r_tot) else None, frameon=False,
              loc='best', fontsize='small')
    return guardar_figura(out, fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--presion', default=os.path.join(rutas.PRESION_DIR, 'tensor_nuevo',
                                                      'resumen_presion_por_atasco.csv'),
                    help='resumen_presion_por_atasco.csv de presion_tensor_arch.py')
    ap.add_argument('--av', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_esqueleto.csv'))
    ap.add_argument('--idx', default=rutas.MASTER_INDEX)
    ap.add_argument('--region', choices=['arco', 'roi', 'bulk'], default='arco')
    ap.add_argument('--magnitud', choices=['P', 'tau'], default='P', help='P (presion) o tau (deviador)')
    ap.add_argument('--s', choices=['big', 'total'], default='big',
                    help="big: granos grandes por avalancha (tamano_big, default); total: total_mix")
    ap.add_argument('--area_ratio', type=float, default=0.1, help='razon de areas nominal (default 0.1)')
    ap.add_argument('--radio_salida', type=float, default=None, help='filtra Radio_salida; por defecto todos')
    ap.add_argument('--chi_max', type=float, default=0.4)
    ap.add_argument('--sistemas', nargs='+', default=None,
                    help="system_type del indice (ej. Disco-Disco Cuad-Disco); por defecto todos")
    ap.add_argument('--solo_con_arco', action='store_true',
                    help='solo avalanchas que terminaron en un atasco guardado (con arco)')
    ap.add_argument('--W', type=float, default=2.0,
                    help='orificio W de la carpeta (_W_2p0 -> 2.0, default); un solo orificio por figura')
    ap.add_argument('--logx', action='store_true')
    ap.add_argument('--liny', action='store_true', help='eje y lineal (por defecto logaritmico)')
    ap.add_argument('--un_panel', action='store_true',
                    help='todos los sistemas en un mismo panel, color por sistema')
    ap.add_argument('--sin_error', action='store_true', help='sin barras de error')
    ap.add_argument('--out', default=None,
                    help='pdf de salida (default: 5_graficos_finales/16-s-vs-<P|tau>-<region>-ratio-<r>-W-<W>.pdf)')
    args = ap.parse_args()

    pres = presion_por_simulacion(args.presion, args.magnitud, args.region)
    aval = avalanchas_por_simulacion(args.av, args.idx, COLUMNA_S[args.s], args.solo_con_arco)
    df = aval.merge(pres, on='clave', how='inner')
    print(f"Simulaciones: {len(pres)} con presion, {len(aval)} con avalanchas, {len(df)} en ambas.")
    if df.empty:
        print("  ejemplos de claves (presion):  ", pres['clave'].head(3).tolist())
        print("  ejemplos de claves (avalanchas):", aval['clave'].head(3).tolist())
        sys.exit("[!] Ninguna simulacion coincide entre la presion y las avalanchas.")
    if 'area_ratio_nominal' in df.columns and args.area_ratio is not None:
        df = df[np.isclose(df['area_ratio_nominal'].fillna(1.0), args.area_ratio, atol=1e-3)
                | (df['chi'] == 0)]
    df['W'] = df['clave'].map(ancho_W)
    if args.radio_salida is not None:
        df = df[np.isclose(df['Radio_salida'], args.radio_salida)]
    df = df[np.isclose(df['W'], args.W)]
    df = df[df['chi'] <= args.chi_max]
    if args.sistemas:
        df = df[df['system_type'].isin(args.sistemas)]
    df = df.dropna(subset=['P', 's'])
    df = agregar_puros(df)
    if df.empty:
        sys.exit("[!] No quedo ninguna simulacion despues de filtrar (--W, --area_ratio, --radio_salida, --chi_max).")
    df['sistema'] = df['system_type'].map(lambda s: SYSTEM_NAME_MAP.get(str(s), str(s)))

    out = args.out or os.path.join(
        rutas.GRAFICOS_FINALES_DIR,
        f"16-s-vs-{args.magnitud}-{args.region}-ratio-{args.area_ratio:g}-W-{args.W:g}.pdf")
    datos = os.path.splitext(out)[0] + '_datos.csv'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cols = ['sistema', 'chi', 'area_ratio_nominal', 'Radio_salida', 'W', 'clave', 'P', 'P_sem', 'n_atascos',
            's', 's_sem', 'n_avalanchas']
    df.sort_values(['sistema', 'chi'])[[c for c in cols if c in df.columns]].to_csv(datos, index=False)
    print("Puntos por sistema y familia (Radio_salida, W): valores de chi")
    for (sis, rs, w), g in df.groupby(['sistema', 'Radio_salida', 'W'], dropna=False):
        print(f"  {sis:20s} R_out={rs:<5g} W={w:<5g} chi={sorted(g['chi'].round(3).tolist())}")
    if args.un_panel:
        path = graficar(df, out, args.magnitud, args.region, args.s, args.logx, not args.liny,
                        not args.sin_error)
    else:
        path = graficar_paneles(df, out, args.magnitud, args.region, args.s, args.logx, not args.liny,
                                not args.sin_error, args.chi_max)
    print(f"Figura: {path}\nDatos:  {datos}")


if __name__ == '__main__':
    main()
