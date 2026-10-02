#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostico de los archivos atasco_contacts_*.dat: verifica, con el
equilibrio estatico de cada grano, la convencion de signo de la fuerza
tangencial y si las columnas son impulsos (hay que dividir por dt) o
fuerzas.

En un atasco (estatico) la suma de fuerzas de contacto sobre cada grano
equilibra su peso: sum_c F_c = (0, m g). Para cada grano que NO toca
paredes ni piso se calcula el residuo |sum F - (0, m g)| / (m g) bajo
varias hipotesis; la correcta es la que da residuo ~0.

Hipotesis (F sobre el grano A del contacto; n = normal de A hacia B,
t = (-n_y, n_x), igual que presion_tensor_arch.py):
  codigo_actual        F_A = (-fn n + ft t) / dt     <- presion_tensor_arch.py (convencion de Box2D, tangente = (n_y, -n_x))
  signo_anterior       F_A = (-fn n - ft t) / dt     <- version anterior del script (signo tangencial invertido)
  sin_tangencial       F_A = (-fn n) / dt
  (y las mismas tres sin dividir por dt, por si el archivo ya trae fuerzas)

Uso:
    python3 analysis/utils/verificar_contactos.py --sim_path /ruta/a/Chi_0p0_W_2p0 --jam_id 1
    python3 analysis/utils/verificar_contactos.py --sim_path ... --jam_id 1 2 3 4 5
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3_presion_y_mapas"))
from presion_tensor_arch import parse_xy, normales_poligonos  # noqa: E402


def leer_params(sim_path):
    """Densidad por tipo de grano, timeStep y g desde params.in."""
    dens, dt, g = [], 0.001, 9.8
    with open(os.path.join(sim_path, "params.in")) as f:
        lineas = [l.split('#')[0].strip() for l in f]
    for i, l in enumerate(lineas):
        if l.startswith('noTipoGranos:'):
            n = int(l.split(':')[1])
            granos = [x for x in lineas[i + 1:] if x][:n]
            dens = [float(x.split()[3]) for x in granos]
        elif l.startswith('timeStep:'):
            dt = float(l.split(':')[1])
        elif l.startswith('g:'):
            g = abs(float(l.split(':')[1]))
    return dens, dt, g


def buscar_archivos(sim_path, jam_id):
    jam = f"{int(jam_id):05d}"
    xy = glob.glob(os.path.join(sim_path, "frames_*", f"atasco_{jam}.xy"))
    ct = glob.glob(os.path.join(sim_path, "frames_*", f"atasco_contacts_{jam}.dat"))
    if not xy or not ct:
        sys.exit(f"[!] No encuentro atasco_{jam}.xy / atasco_contacts_{jam}.dat en {sim_path}/frames_*")
    return xy[0], ct[0]


def diagnosticar(xy_file, ct_file, dens, dt, g):
    p = pd.DataFrame.from_dict(parse_xy(xy_file), orient='index')
    c = pd.read_csv(ct_file, sep=r'\s+', comment='#', header=None,
                    names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'], usecols=range(6))

    info = {
        'contactos': len(c),
        'f_tan_negativos_%': 100.0 * (c['f_tan'] < 0).mean(),
        'f_norm_mediana': float(c['f_norm'].median()),
        'peso_grano_mediano_mg': float(np.median([dens[int(t)] * a * g for t, a in zip(p['type'], p['area'])])),
    }

    # Solo contactos grano-grano; granos que tocan pared/piso quedan fuera
    toca_pared = set(c.loc[c['id_a'] < 0, 'id_b']) | set(c.loc[c['id_b'] < 0, 'id_a'])
    gg = c[(c['id_a'] >= 0) & (c['id_b'] >= 0) & c['id_a'].isin(p.index) & c['id_b'].isin(p.index)].copy()

    # Normal de A hacia B (misma geometria que presion_tensor_arch.py)
    pa = p.loc[gg['id_a']]
    nx = np.zeros(len(gg))
    ny = np.zeros(len(gg))
    es_disco = (pa['shape'] == 'Disco').to_numpy()
    dx = gg['px'].to_numpy() - pa['pos_x'].to_numpy()
    dy = gg['py'].to_numpy() - pa['pos_y'].to_numpy()
    nr = np.hypot(dx, dy)
    nr[nr == 0] = 1.0
    nx[es_disco], ny[es_disco] = (dx / nr)[es_disco], (dy / nr)[es_disco]
    if (~es_disco).any():
        sel = ~es_disco
        nv = normales_poligonos(gg['px'].to_numpy()[sel], gg['py'].to_numpy()[sel],
                                pa['pos_x'].to_numpy()[sel], pa['pos_y'].to_numpy()[sel],
                                pa['coords'].to_numpy()[sel])
        nx[sel], ny[sel] = nv[:, 0], nv[:, 1]
    tx, ty = -ny, nx
    fn = gg['f_norm'].to_numpy()
    ft = gg['f_tan'].to_numpy()

    candidatos = [i for i in p.index if i not in toca_pared]
    peso = pd.Series({i: dens[int(p.at[i, 'type'])] * p.at[i, 'area'] * g for i in candidatos})
    ncont = pd.concat([gg['id_a'], gg['id_b']]).value_counts()
    candidatos = [i for i in candidatos if ncont.get(i, 0) >= 2]

    hip = {
        'codigo_actual': (+1.0, True), 'signo_anterior': (-1.0, True), 'sin_tangencial': (0.0, True),
        'codigo_actual_sin_/dt': (+1.0, False), 'signo_anterior_sin_/dt': (-1.0, False), 'sin_tang_sin_/dt': (0.0, False),
    }
    res = {}
    for nombre, (s, div) in hip.items():
        esc = 1.0 / dt if div else 1.0
        fax = (-fn * nx + s * ft * tx) * esc
        fay = (-fn * ny + s * ft * ty) * esc
        sx = pd.Series(fax, index=gg['id_a'].to_numpy()).groupby(level=0).sum().sub(
            pd.Series(fax, index=gg['id_b'].to_numpy()).groupby(level=0).sum(), fill_value=0)
        sy = pd.Series(fay, index=gg['id_a'].to_numpy()).groupby(level=0).sum().sub(
            pd.Series(fay, index=gg['id_b'].to_numpy()).groupby(level=0).sum(), fill_value=0)
        sx, sy = sx.reindex(candidatos).fillna(0), sy.reindex(candidatos).fillna(0)
        w = peso.reindex(candidatos)
        res[nombre] = float(np.median(np.hypot(sx, sy - w) / w))
    info['granos_evaluados'] = len(candidatos)

    # Simetria del tensor de cada grano: S01 - S10 = sum(r_x f_y - r_y f_x) es
    # el torque neto, que en un atasco estatico tiene que ser ~0. Ademas:
    # P > 0 (compresion) y la relacion tau/P.
    pb = p.loc[gg['id_b']]
    rax, ray = dx, dy
    rbx = gg['px'].to_numpy() - pb['pos_x'].to_numpy()
    rby = gg['py'].to_numpy() - pb['pos_y'].to_numpy()
    tens = {}
    for nombre, s in (('codigo_actual', +1.0), ('signo_anterior', -1.0)):
        fax = (-fn * nx + s * ft * tx) / dt
        fay = (-fn * ny + s * ft * ty) / dt
        comp = {}
        for k, (ra, rb, fa) in {'S00': (rax, rbx, fax), 'S11': (ray, rby, fay),
                                'S01': (rax, rbx, fay), 'S10': (ray, rby, fax)}.items():
            # sobre A: F_A ; sobre B: -F_A (3ra ley)
            comp[k] = (pd.Series(ra * fa, index=gg['id_a'].to_numpy()).groupby(level=0).sum()
                       .sub(pd.Series(rb * fa, index=gg['id_b'].to_numpy()).groupby(level=0).sum(),
                            fill_value=0).reindex(candidatos).fillna(0).to_numpy())
        S00, S11, S01, S10 = comp['S00'], comp['S11'], comp['S01'], comp['S10']
        norma = np.sqrt(S00**2 + S11**2 + S01**2 + S10**2)
        norma[norma == 0] = np.nan
        area = p.loc[candidatos, 'area'].to_numpy(dtype=float)
        P = -0.5 * (S00 + S11) / area
        sxx, syy, sxy = -S00 / area, -S11 / area, -0.5 * (S01 + S10) / area
        tau = np.sqrt((0.5 * (sxx - syy))**2 + sxy**2)
        asim = np.abs(S01 - S10) / norma
        tens[nombre] = {
            'asim_mediana': float(np.nanmedian(asim)),
            'asim_p90': float(np.nanpercentile(asim, 90)),
            'P_negativa_%': 100.0 * float(np.mean(P < 0)),
            'tau/P_mediana': float(np.nanmedian(tau / np.where(P > 0, P, np.nan))),
            'tau>P_%': 100.0 * float(np.mean(tau > P)),
        }
    return info, res, tens


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sim_path', required=True, help='carpeta de la simulacion (la que tiene params.in)')
    ap.add_argument('--jam_id', nargs='+', default=['1'])
    args = ap.parse_args()

    dens, dt, g = leer_params(args.sim_path)
    print(f"params.in: densidades={dens} timeStep={dt} g={g}")
    acum = {}
    acum_t = {}
    for j in args.jam_id:
        xy, ct = buscar_archivos(args.sim_path, j)
        info, res, tens = diagnosticar(xy, ct, dens, dt, g)
        for k, d in tens.items():
            for m, v in d.items():
                acum_t.setdefault(k, {}).setdefault(m, []).append(v)
        print(f"\n== atasco {j}: {info['contactos']} contactos, {info['granos_evaluados']} granos evaluados (sin paredes)")
        print(f"   f_tan negativos: {info['f_tan_negativos_%']:.1f} %   "
              f"(0 % => el archivo guarda |f_tan| y el signo se perdio)")
        print(f"   f_norm mediana: {info['f_norm_mediana']:.4g}   peso mediano de un grano m*g: {info['peso_grano_mediano_mg']:.4g}")
        for k, v in res.items():
            acum.setdefault(k, []).append(v)
    print("\n== Residuo mediano del equilibrio |sum F - m g| / (m g)  (0 = hipotesis correcta)")
    for k, v in sorted(acum.items(), key=lambda kv: np.median(kv[1])):
        print(f"   {k:26s} {np.median(v):10.4f}")

    print("\n== Tensor por grano (granos sin paredes, mediana sobre atascos)")
    print("   asimetria = |S01 - S10| / |S|  (torque neto relativo; ~0 = simetrico)")
    print(f"   {'':16s} {'asim mediana':>13s} {'asim p90':>9s} {'P<0 %':>7s} {'tau/P med':>10s} {'tau>P %':>8s}")
    for k, d in acum_t.items():
        print(f"   {k:16s} {np.median(d['asim_mediana']):13.4f} {np.median(d['asim_p90']):9.4f} "
              f"{np.median(d['P_negativa_%']):7.2f} {np.median(d['tau/P_mediana']):10.3f} "
              f"{np.median(d['tau>P_%']):8.2f}")


if __name__ == '__main__':
    main()
