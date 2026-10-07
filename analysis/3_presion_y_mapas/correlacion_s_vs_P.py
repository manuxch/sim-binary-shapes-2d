#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correlacion entre el tamano medio de avalancha <s> y la presion media <P>
de los atascos, un punto por simulacion (sistema, chi, razon de areas,
orificio). Color y marcador por sistema; los puntos de un mismo sistema se
unen en orden de chi.

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
  16-s-vs-P-<region>-ratio-<r>.pdf  y  ..._datos.csv con los valores graficados.
En la leyenda: coeficiente de Pearson r de cada sistema; en el titulo de
la leyenda, el de todos los puntos juntos.

Uso:
    python3 analysis/3_presion_y_mapas/correlacion_s_vs_P.py \\
        --presion processed_data/presion/tensor_nuevo/resumen_presion_por_atasco.csv
    python3 analysis/3_presion_y_mapas/correlacion_s_vs_P.py --region roi --area_ratio 0.1 --logy
"""
import argparse
import os
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
    ap.add_argument('--logx', action='store_true')
    ap.add_argument('--logy', action='store_true')
    ap.add_argument('--sin_error', action='store_true', help='sin barras de error')
    ap.add_argument('--out', default=None,
                    help='pdf de salida (default: 5_graficos_finales/16-s-vs-<P|tau>-<region>-ratio-<r>.pdf)')
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
    if args.radio_salida is not None:
        df = df[np.isclose(df['Radio_salida'], args.radio_salida)]
    df = df[df['chi'] <= args.chi_max]
    if args.sistemas:
        df = df[df['system_type'].isin(args.sistemas)]
    df = df.dropna(subset=['P', 's'])
    df = agregar_puros(df)
    if df.empty:
        sys.exit("[!] No quedo ninguna simulacion despues de filtrar (--area_ratio, --radio_salida, --chi_max).")
    df['sistema'] = df['system_type'].map(lambda s: SYSTEM_NAME_MAP.get(str(s), str(s)))

    out = args.out or os.path.join(
        rutas.GRAFICOS_FINALES_DIR,
        f"16-s-vs-{args.magnitud}-{args.region}-ratio-{args.area_ratio:g}.pdf")
    datos = os.path.splitext(out)[0] + '_datos.csv'
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cols = ['sistema', 'chi', 'area_ratio_nominal', 'Radio_salida', 'clave', 'P', 'P_sem', 'n_atascos',
            's', 's_sem', 'n_avalanchas']
    df.sort_values(['sistema', 'chi'])[[c for c in cols if c in df.columns]].to_csv(datos, index=False)
    print("Puntos por sistema (chi):")
    for sis, g in df.groupby('sistema'):
        print(f"  {sis:20s} {sorted(g['chi'].round(3).tolist())}")
    path = graficar(df, out, args.magnitud, args.region, args.s, args.logx, args.logy, not args.sin_error)
    print(f"Figura: {path}\nDatos:  {datos}")


if __name__ == '__main__':
    main()
