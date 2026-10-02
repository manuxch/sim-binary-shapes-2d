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
  codigo_actual        F_A = (-fn n - ft t) / dt     <- lo que usa presion_tensor_arch.py
  tangencial_invertida F_A = (-fn n + ft t) / dt     <- convencion de Box2D (tangente = (n_y, -n_x))
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
        'codigo_actual': (-1.0, True), 'tangencial_invertida': (+1.0, True), 'sin_tangencial': (0.0, True),
        'codigo_actual_sin_/dt': (-1.0, False), 'tang_invertida_sin_/dt': (+1.0, False), 'sin_tang_sin_/dt': (0.0, False),
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
    return info, res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sim_path', required=True, help='carpeta de la simulacion (la que tiene params.in)')
    ap.add_argument('--jam_id', nargs='+', default=['1'])
    args = ap.parse_args()

    dens, dt, g = leer_params(args.sim_path)
    print(f"params.in: densidades={dens} timeStep={dt} g={g}")
    acum = {}
    for j in args.jam_id:
        xy, ct = buscar_archivos(args.sim_path, j)
        info, res = diagnosticar(xy, ct, dens, dt, g)
        print(f"\n== atasco {j}: {info['contactos']} contactos, {info['granos_evaluados']} granos evaluados (sin paredes)")
        print(f"   f_tan negativos: {info['f_tan_negativos_%']:.1f} %   "
              f"(0 % => el archivo guarda |f_tan| y el signo se perdio)")
        print(f"   f_norm mediana: {info['f_norm_mediana']:.4g}   peso mediano de un grano m*g: {info['peso_grano_mediano_mg']:.4g}")
        for k, v in res.items():
            acum.setdefault(k, []).append(v)
    print("\n== Residuo mediano del equilibrio |sum F - m g| / (m g)  (0 = hipotesis correcta)")
    for k, v in sorted(acum.items(), key=lambda kv: np.median(kv[1])):
        print(f"   {k:26s} {np.median(v):10.4f}")


if __name__ == '__main__':
    main()
