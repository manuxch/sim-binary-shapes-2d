#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estado de tension de los granos del ARCO comparado con la region de arriba
(ROI) y el resto (bulk), mirando el tensor completo y no solo la presion.

Para cada region (promedios pesados por area de grano):
  P        = (sxx + syy)/2           centro del circulo de Mohr
  tau      = radio del circulo de Mohr (deviador)
  s1, s2   = P + tau, P - tau        esfuerzos principales (mayor y menor)
  tau/P
  P_m, tau_m: P y tau del TENSOR PROMEDIO de la region (Born-Huang de la
           region, salvo el factor phi): tau_m <= <tau> porque los ejes
           principales de cada grano apuntan distinto.

Solo para el arco, en ejes propios del arco (t = tangente al arco en cada
grano, n = perpendicular):
  s_tt     = t.sigma.t   compresion A LO LARGO del arco (la que transmite la carga)
  s_nn     = n.sigma.n   compresion perpendicular al arco
  s_tn     = t.sigma.n   corte en ejes del arco (fuera de la diagonal)
  ang      = angulo entre la direccion de s1 y la tangente (0 = el arco
             trabaja a compresion pura a lo largo de su eje)

La tangente sale de ordenar los granos del arco por angulo polar alrededor
del centro del orificio (0, 0) y tomar la direccion entre el anterior y el
siguiente. Por eso s_tt, s_nn, s_tn son aproximados en arcos muy plegados.

P no depende de los ejes (es la traza), asi que sigma_xy NO cambia P: el
estres fuera de la diagonal aparece en tau, en s1/s2 y en s_tt/s_nn.

Con --pdf ademas guarda una figura: P, s1 y s2 por region (arco, ROI,
bulk) para cada forma, con barras de error = error estandar entre atascos.

Uso:
    python3 estres_arco_vs_roi.py --parquet <out>/presion_por_particula_Cuadrado.parquet \\
        --incluir 'Ratio_0p1_Chi_0p2_W_2p0'
    (se puede pasar mas de un parquet: una tabla por archivo)
    python3 estres_arco_vs_roi.py --parquet <out>/presion_por_particula_*.parquet \\
        --incluir 'Ratio_0p1_Chi_0p2_W_2p0' --pdf estres_arco_vs_roi.pdf
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

COLS = ['sim_path', 'jam_id', 'region', 'tipo', 'pos_x', 'pos_y', 'area',
        'sigma_xx_reducida', 'sigma_yy_reducida', 'sigma_xy_reducida']


def leer(path, incluir):
    import pyarrow.dataset as ds
    import pyarrow.compute as pc
    filtro = pc.field('region').isin(['arco', 'roi', 'bulk'])
    if incluir:
        filtro = filtro & pc.match_substring_regex(pc.field('sim_path'), incluir)
    return ds.dataset(path).to_table(columns=COLS, filter=filtro).to_pandas()


def invariantes(sxx, syy, sxy):
    P = 0.5 * (sxx + syy)
    tau = np.hypot(0.5 * (sxx - syy), sxy)
    return P, tau


def ejes_arco(arco):
    """Tangente unitaria (tx, ty) de cada grano del arco, un atasco a la vez."""
    t = np.zeros((len(arco), 2))
    pos = arco[['pos_x', 'pos_y']].to_numpy(float)
    for _, idx in arco.groupby(['sim_path', 'jam_id'], sort=False).indices.items():
        if len(idx) < 2:
            continue
        p = pos[idx]
        orden = np.argsort(-np.arctan2(p[:, 1], p[:, 0]))      # de izquierda (pi) a derecha (0)
        q = p[orden]
        d = np.empty_like(q)
        d[1:-1] = q[2:] - q[:-2]
        d[0], d[-1] = q[1] - q[0], q[-1] - q[-2]
        d /= np.where(np.hypot(d[:, 0], d[:, 1]) > 0, np.hypot(d[:, 0], d[:, 1]), 1.0)[:, None]
        t[idx[orden]] = d
    return t


def resumen(df, nombre):
    w = df['area'].to_numpy(float)
    sxx, syy, sxy = (df[c].to_numpy(float) for c in
                     ('sigma_xx_reducida', 'sigma_yy_reducida', 'sigma_xy_reducida'))
    P, tau = invariantes(sxx, syy, sxy)
    m = lambda v: float(np.average(v, weights=w))  # noqa: E731
    Pm, taum = invariantes(m(sxx), m(syy), m(sxy))
    fila = dict(region=nombre, granos=len(df), P=m(P), tau=m(tau), s1=m(P + tau), s2=m(P - tau),
                tau_P=m(tau) / m(P), P_m=Pm, tau_m=taum, sxx=m(sxx), syy=m(syy), sxy=m(sxy))
    return fila


def por_atasco(sub):
    """P, s1, s2 de la region en cada atasco (pesados por area): media y error estandar entre atascos."""
    P, tau = invariantes(sub['sigma_xx_reducida'].to_numpy(float), sub['sigma_yy_reducida'].to_numpy(float),
                         sub['sigma_xy_reducida'].to_numpy(float))
    d = pd.DataFrame({'k': list(zip(sub['sim_path'], sub['jam_id'])), 'w': sub['area'].to_numpy(float),
                      'P': P * sub['area'].to_numpy(float), 's1': (P + tau) * sub['area'].to_numpy(float),
                      's2': (P - tau) * sub['area'].to_numpy(float)})
    g = d.groupby('k').sum()
    out = {}
    for c in ('P', 's1', 's2'):
        v = g[c] / g['w']
        out[c] = (float(v.mean()), float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0)
    return out


def analizar(path, incluir):
    df = leer(path, incluir)
    if df.empty:
        print(f"\n[!] {os.path.basename(path)}: ninguna fila coincide con --incluir")
        sims = leer_sims(path)
        print(f"    simulaciones en el archivo (sim_path, primeras 10): {sims[:10]}")
        return None
    print(f"\n== {os.path.basename(path)}  ({df.groupby(['sim_path', 'jam_id']).ngroups} atascos, "
          f"{df['sim_path'].nunique()} simulaciones)")
    filas = []
    for reg in ('arco', 'roi', 'bulk'):
        sub = df[df['region'] == reg]
        if len(sub):
            filas.append(resumen(sub, reg))
            for tipo in ('B', 'S'):
                st = sub[sub['tipo'] == tipo]
                if len(st):
                    filas.append(resumen(st, f"{reg}_{tipo}"))
    tabla = pd.DataFrame(filas).set_index('region')
    with pd.option_context('display.float_format', '{:.3f}'.format, 'display.width', 160):
        print("   Promedios pesados por area (unidades reducidas, /g):")
        print(tabla.to_string())

    figura = {reg: por_atasco(df[df['region'] == reg]) for reg in ('arco', 'roi', 'bulk')
              if (df['region'] == reg).any()}
    arco = df[df['region'] == 'arco'].reset_index(drop=True)
    if len(arco) < 2:
        return figura
    t = ejes_arco(arco)
    n = np.stack([-t[:, 1], t[:, 0]], 1)
    S = np.stack([[arco.sigma_xx_reducida, arco.sigma_xy_reducida],
                  [arco.sigma_xy_reducida, arco.sigma_yy_reducida]]).transpose(2, 0, 1).astype(float)
    s_tt = np.einsum('ki,kij,kj->k', t, S, t)
    s_nn = np.einsum('ki,kij,kj->k', n, S, n)
    s_tn = np.einsum('ki,kij,kj->k', t, S, n)
    theta1 = 0.5 * np.arctan2(2 * S[:, 0, 1], S[:, 0, 0] - S[:, 1, 1])   # direccion de s1
    d1 = np.stack([np.cos(theta1), np.sin(theta1)], 1)
    ang = np.degrees(np.arccos(np.clip(np.abs((d1 * t).sum(1)), 0, 1)))
    w = arco['area'].to_numpy(float)
    m = lambda v: float(np.average(v, weights=w))  # noqa: E731
    print("\n   Arco en ejes propios (t = tangente, n = normal al arco):")
    print(f"   s_tt (a lo largo del arco) = {m(s_tt):.3f}   s_nn (perpendicular) = {m(s_nn):.3f}   "
          f"s_tn (corte) = {m(np.abs(s_tn)):.3f}")
    print(f"   angulo entre s1 y la tangente: mediana {np.median(ang):.0f} grados, "
          f"{100 * np.mean(ang < 30):.0f} % de los granos con menos de 30 grados")
    return figura


def leer_sims(path):
    import pyarrow.dataset as ds
    import pyarrow.compute as pc
    t = ds.dataset(path).to_table(columns=['sim_path'])
    return sorted(set(os.path.basename(str(x)) for x in pc.unique(t['sim_path']).to_pylist()))


def graficar(datos, salida, titulo):
    import matplotlib.pyplot as plt
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from estilo_figuras import aplicar_estilo, estilo_forma, guardar_figura, REGION_STYLE, ERRORBAR_KW
    aplicar_estilo()
    colores = {'arco': REGION_STYLE['arco'], 'roi': REGION_STYLE['roi'], 'bulk': ('#999999', 'Bulk')}
    formas = list(datos)
    paneles = (('P', r'$P/g$'), ('s1', r'$\sigma_1/g$'), ('s2', r'$\sigma_2/g$'))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=False)
    ancho = 0.26
    x = np.arange(len(formas))
    for ax, (clave, etiqueta) in zip(axes, paneles):
        for k, reg in enumerate(('arco', 'roi', 'bulk')):
            vals = [datos[f].get(reg, {}).get(clave, (np.nan, 0.0)) for f in formas]
            ax.bar(x + (k - 1) * ancho, [v[0] for v in vals], ancho, yerr=[v[1] for v in vals],
                   color=colores[reg][0], label=colores[reg][1], **ERRORBAR_KW)
        ax.set_xticks(x)
        ax.set_xticklabels([estilo_forma(f)[0] for f in formas])
        ax.set_ylabel(etiqueta)
    axes[0].legend(frameon=False)
    if titulo:
        fig.suptitle(titulo)
    fig.tight_layout()
    print(f"\nFigura: {guardar_figura(salida, fig)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--parquet', nargs='+', required=True, help='presion_por_particula_<Forma>.parquet')
    ap.add_argument('--incluir', default=None, help='regex sobre sim_path (ej. Ratio_0p1_Chi_0p2_W_2p0)')
    ap.add_argument('--pdf', default=None, help='guarda la figura P, s1, s2 por region y forma')
    ap.add_argument('--titulo', default=None)
    args = ap.parse_args()
    datos = {}
    for p in args.parquet:
        if not os.path.exists(p):
            sys.exit(f"[!] No existe {p}")
        r = analizar(p, args.incluir)
        if r:
            forma = os.path.basename(p).replace('presion_por_particula_', '').replace('.parquet', '')
            datos[forma] = r
    if args.pdf and datos:
        graficar(datos, args.pdf, args.titulo)


if __name__ == '__main__':
    main()
