#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostico de los archivos atasco_contacts_*.dat y del tensor de
esfuerzos que calcula presion_tensor_arch.py, usando el equilibrio
estatico de cada grano en el atasco.

Usa las MISMAS funciones que presion_tensor_arch.py (fuerzas_contacto,
normales_contacto, parse_paredes), asi que lo que se verifica aca es lo que
efectivamente se calcula.

1) Signo de la tangencial e impulso/fuerza: para cada grano, la suma de
   fuerzas de contacto equilibra su peso, sum_c F_c = (0, m g). Se calcula
   el residuo |sum F - (0, m g)| / (m g) bajo varias hipotesis; la correcta
   es la que da ~0.
     codigo_actual   F_A = (-fn n + ft t) / dt   (convencion de Box2D)
     signo_anterior  F_A = (-fn n - ft t) / dt   (version vieja del script)
     sin_tangencial  F_A = (-fn n) / dt
     ..._sin_/dt     lo mismo sin dividir por dt (por si el archivo trae fuerzas)

2) Normal del contacto y simetria del tensor, por tipo de grano: el
   torque neto sum(r_x F_y - r_y F_x) = S01 - S10 tiene que ser ~0, o sea el
   tensor de cada grano tiene que ser simetrico. Se compara la normal
   'nueva' (exacta con discos; cara de referencia entre poligonos y contra
   paredes) con la 'vieja' (lado mas cercano del poligono A).
   Ademas: P > 0 (compresion) y la relacion tau/P.

Uso:
    python3 analysis/utils/verificar_contactos.py --sim_path /ruta/a/Chi_0p0_W_2p0 --jam_id 1 2 3 4 5
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3_presion_y_mapas"))
from presion_tensor_arch import parse_xy, parse_paredes, fuerzas_contacto  # noqa: E402


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


def sumas_por_grano(df, ids):
    """Suma por grano de F y de S_ij = r_i F_j (sobre A: F_A; sobre B: -F_A)."""
    a_ok, b_ok = df['a_valida'].to_numpy(), df['b_valida'].to_numpy()
    Fx, Fy = df['Fx_A'].to_numpy(), df['Fy_A'].to_numpy()
    rax, ray = (df['px'] - df['pos_x_A']).to_numpy(), (df['py'] - df['pos_y_A']).to_numpy()
    rbx, rby = (df['px'] - df['pos_x_B']).to_numpy(), (df['py'] - df['pos_y_B']).to_numpy()
    ia, ib = df['id_a'].to_numpy(), df['id_b'].to_numpy()
    out = {}
    for k, (va, vb) in {'Fx': (Fx, -Fx), 'Fy': (Fy, -Fy),
                        'S00': (rax * Fx, -rbx * Fx), 'S11': (ray * Fy, -rby * Fy),
                        'S01': (rax * Fy, -rbx * Fy), 'S10': (ray * Fx, -rby * Fx)}.items():
        sa = pd.Series(np.where(a_ok, va, 0.0), index=ia).groupby(level=0).sum()
        sb = pd.Series(np.where(b_ok, vb, 0.0), index=ib).groupby(level=0).sum()
        out[k] = sa.add(sb, fill_value=0).reindex(ids).fillna(0).to_numpy()
    return out


def metricas(S, area, peso):
    norma = np.sqrt(S['S00']**2 + S['S11']**2 + S['S01']**2 + S['S10']**2)
    norma = np.where(norma > 0, norma, np.nan)
    P = -0.5 * (S['S00'] + S['S11']) / area
    sxx, syy, sxy = -S['S00'] / area, -S['S11'] / area, -0.5 * (S['S01'] + S['S10']) / area
    tau = np.sqrt((0.5 * (sxx - syy))**2 + sxy**2)
    with np.errstate(invalid='ignore', divide='ignore'):
        return {
            'residuo': float(np.nanmedian(np.hypot(S['Fx'], S['Fy'] - peso) / peso)),
            'asim_med': float(np.nanmedian(np.abs(S['S01'] - S['S10']) / norma)),
            'asim_p90': float(np.nanpercentile(np.abs(S['S01'] - S['S10']) / norma, 90)),
            'P<0_%': 100.0 * float(np.mean(P < 0)),
            'tau/P': float(np.nanmedian(tau / np.where(P > 0, P, np.nan))),
            'tau>P_%': 100.0 * float(np.mean(tau > P)),
        }


def diagnosticar(xy_file, ct_file, dens, dt, g):
    p = pd.DataFrame.from_dict(parse_xy(xy_file), orient='index')
    paredes = parse_paredes(xy_file)
    c = pd.read_csv(ct_file, sep=r'\s+', comment='#', header=None,
                    names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'], usecols=range(6))
    info = {
        'contactos': len(c),
        'segmentos_pared': len(paredes),
        'f_tan_negativos_%': 100.0 * (c['f_tan'] < 0).mean(),
        'f_norm_mediana': float(c['f_norm'].median()),
    }

    # Granos con al menos 2 contactos (los demas no pueden estar en equilibrio estatico)
    ncont = pd.concat([c['id_a'], c['id_b']]).value_counts()
    ids = [i for i in p.index if ncont.get(i, 0) >= 2]
    toca_pared = set(c.loc[c['id_a'] < 0, 'id_b']) | set(c.loc[c['id_b'] < 0, 'id_a'])
    area = p.loc[ids, 'area'].to_numpy(float)
    peso = np.array([dens[int(t)] for t in p.loc[ids, 'type']]) * area * g
    es_disco = (p.loc[ids, 'shape'] == 'Disco').to_numpy()
    pared = np.array([i in toca_pared for i in ids])
    clases = {
        'discos': es_disco & ~pared,
        'poligonos': ~es_disco & ~pared,
        'tocan_pared': pared,
    }
    info['granos'] = {k: int(v.sum()) for k, v in clases.items()}

    # 1) Hipotesis de signo / dt (normal nueva, granos sin pared)
    sin_pared = ~pared
    hip = {
        'codigo_actual': (+1.0, True), 'signo_anterior': (-1.0, True), 'sin_tangencial': (0.0, True),
        'codigo_actual_sin_/dt': (+1.0, False), 'signo_anterior_sin_/dt': (-1.0, False),
        'sin_tang_sin_/dt': (0.0, False),
    }
    res_signo = {}
    for nombre, (s, div) in hip.items():
        df = fuerzas_contacto(p, c, dt, paredes=paredes, metodo='nuevo', signo_tan=s, dividir_dt=div)
        S = sumas_por_grano(df, ids)
        r = np.hypot(S['Fx'], S['Fy'] - peso) / peso
        res_signo[nombre] = float(np.median(r[sin_pared]))

    # 2) Normal vieja vs nueva, por clase de grano (signo correcto, /dt)
    res_normal = {}
    for metodo in ('nuevo', 'viejo'):
        df = fuerzas_contacto(p, c, dt, paredes=paredes, metodo=metodo)
        S = sumas_por_grano(df, ids)
        for clase, mask in clases.items():
            if mask.sum() == 0:
                continue
            res_normal[(metodo, clase)] = metricas({k: v[mask] for k, v in S.items()}, area[mask], peso[mask])
    return info, res_signo, res_normal


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sim_path', required=True, help='carpeta de la simulacion (la que tiene params.in)')
    ap.add_argument('--jam_id', nargs='+', default=['1'])
    args = ap.parse_args()

    dens, dt, g = leer_params(args.sim_path)
    print(f"params.in: densidades={dens} timeStep={dt} g={g}")
    acum_signo, acum_normal = {}, {}
    for j in args.jam_id:
        xy, ct = buscar_archivos(args.sim_path, j)
        info, res_signo, res_normal = diagnosticar(xy, ct, dens, dt, g)
        print(f"\n== atasco {j}: {info['contactos']} contactos, {info['segmentos_pared']} segmentos de pared, "
              f"granos: {info['granos']}")
        print(f"   f_tan negativos: {info['f_tan_negativos_%']:.1f} %   "
              f"(0 % => el archivo guarda |f_tan| y el signo se perdio)   f_norm mediana: {info['f_norm_mediana']:.4g}")
        for k, v in res_signo.items():
            acum_signo.setdefault(k, []).append(v)
        for k, d in res_normal.items():
            for m, v in d.items():
                acum_normal.setdefault(k, {}).setdefault(m, []).append(v)

    print("\n== 1) Equilibrio de fuerzas, granos sin pared: residuo mediano |sum F - m g| / (m g)  (0 = correcta)")
    for k, v in sorted(acum_signo.items(), key=lambda kv: np.median(kv[1])):
        print(f"   {k:26s} {np.median(v):10.4f}")

    print("\n== 2) Por tipo de grano (mediana sobre atascos)")
    print("   residuo = equilibrio de fuerzas; asim = |S01 - S10| / |S| = torque neto relativo (0 = tensor simetrico)")
    print(f"   {'normal':7s} {'granos':12s} {'residuo':>9s} {'asim med':>9s} {'asim p90':>9s} "
          f"{'P<0 %':>7s} {'tau/P':>7s} {'tau>P %':>8s}")
    for (metodo, clase), d in acum_normal.items():
        print(f"   {metodo:7s} {clase:12s} {np.median(d['residuo']):9.4f} {np.median(d['asim_med']):9.4f} "
              f"{np.median(d['asim_p90']):9.4f} {np.median(d['P<0_%']):7.2f} {np.median(d['tau/P']):7.3f} "
              f"{np.median(d['tau>P_%']):8.2f}")


if __name__ == '__main__':
    main()
