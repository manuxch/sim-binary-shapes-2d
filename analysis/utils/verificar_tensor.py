#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verificacion independiente del tensor de esfuerzos por grano, en especial de
la parte fuera de la diagonal (sigma_xy) y del deviador tau, que calcula
presion_tensor_arch.py. Usa la MISMA funcion del script
(calcular_tensor_y_presion_vectorizado), asi que lo que se prueba es lo que
efectivamente se calcula.

Tres pruebas:

1) --sintetico (no necesita datos): casos armados a mano con resultado
   conocido, sigma = -(1/A) sum_c r (x) f:
     a. disco comprimido por dos fuerzas opuestas a lo largo de una direccion
        u (angulo 0, 30, 45, 90, 135 grados): sigma = (2F/A) u u^T, o sea
        sigma_xy = (2F/A) u_x u_y, P = tau = F/A. Prueba el SIGNO de sigma_xy
        (compresion a lo largo de la diagonal y = x  ->  sigma_xy > 0).
     b. corte puro con fuerzas tangenciales (torque neto 0), en un disco y en
        un cuadrado: sigma_xy = -2T/A, tau = 2T/A. Prueba la tangencial.
     c. dos discos que se tocan (contacto grano-grano, 3ra ley) comprimidos a
        lo largo de u: cada uno tiene sigma = (2F/A) u u^T.
     d. 200 granos al azar con fuerzas al azar, rotados un angulo: P y tau no
        cambian y sigma rota como R sigma R^T.

2) --sim_path y --jam_id: rota un atasco REAL (granos, paredes y contactos)
   un angulo y recalcula. P y tau de cada grano no tienen que cambiar y el
   tensor tiene que rotar como R sigma R^T. Prueba todo el camino real
   (normales de discos, poligonos y paredes; fuerza tangencial).

3) --parquet (salida de presion_tensor_arch.py): chequeo fisico con datos.
     - Espejo: el silo es simetrico izquierda-derecha, asi que en promedio
       sigma_xy(-x) = -sigma_xy(x), y sigma_xx, sigma_yy, P, tau son pares.
     - Paredes (efecto Janssen): las paredes sostienen parte del peso por
       friccion (fuerza hacia arriba sobre los granos). Eso da sigma_xy > 0
       junto a la pared izquierda y < 0 junto a la derecha, con
       |sigma_xy| / sigma_xx <= friccion de la pared (0.5 en params.in).

Uso:
    python3 analysis/utils/verificar_tensor.py --sintetico
    python3 analysis/utils/verificar_tensor.py --sim_path <carpeta_simulacion> --jam_id 1 2 3
    python3 analysis/utils/verificar_tensor.py --parquet <out>/presion_por_particula_Disco.parquet \\
        --incluir 'Chi_0p2_W_2p0'
"""
import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3_presion_y_mapas"))
from presion_tensor_arch import (parse_xy, parse_paredes,  # noqa: E402
                                 calcular_tensor_y_presion_vectorizado)

TOL = 1e-4
fallas = []


def chequear(nombre, obtenido, esperado, tol=TOL):
    obtenido, esperado = np.asarray(obtenido, float), np.asarray(esperado, float)
    escala = max(1.0, float(np.max(np.abs(esperado))))
    err = float(np.max(np.abs(obtenido - esperado))) / escala
    ok = err < tol
    if not ok:
        fallas.append(nombre)
    print(f"   [{'OK ' if ok else 'MAL'}] {nombre:58s} error relativo {err:.1e}")
    return ok


# ---------------------------------------------------------------------------
# Helpers para armar casos
# ---------------------------------------------------------------------------

def tabla_particulas(granos):
    """granos: lista de dicts con id, x, y y (r) o (coords)."""
    filas = {}
    for g in granos:
        if 'coords' in g:
            c = np.asarray(g['coords'], dtype=np.float32)
            x2, y2 = c[:, 0], c[:, 1]
            area = 0.5 * abs(np.dot(x2, np.roll(y2, 1)) - np.dot(y2, np.roll(x2, 1)))
            filas[g['id']] = dict(pos_x=c[:, 0].mean(), pos_y=c[:, 1].mean(),
                                  r_eff=float(np.max(np.hypot(*(c - c.mean(0)).T))),
                                  type=0, shape={3: 'Triangulo', 4: 'Cuadrado', 5: 'Pentagono'}[len(c)],
                                  area=area, coords=c)
        else:
            filas[g['id']] = dict(pos_x=g['x'], pos_y=g['y'], r_eff=g['r'], type=0, shape='Disco',
                                  area=np.pi * g['r'] ** 2, coords=None)
    df = pd.DataFrame.from_dict(filas, orient='index')
    df.index.name = 'id'
    return df


def contacto(id_a, id_b, p, n, f_sobre_b):
    """Contacto en formato del archivo: n = normal de A hacia B, f_sobre_b =
    fuerza que recibe B. Box2D aplica sobre B fn*n + ft*t_b2d, con
    t_b2d = (n_y, -n_x)  ->  fn = f.n, ft = f.t_b2d (dt = 1: impulso = fuerza)."""
    n = np.asarray(n, float) / np.hypot(*n)
    f = np.asarray(f_sobre_b, float)
    t_b2d = np.array([n[1], -n[0]])
    return dict(id_a=id_a, id_b=id_b, px=p[0], py=p[1], f_norm=f @ n, f_tan=f @ t_b2d)


def tensor_codigo(granos, contactos, paredes=None):
    """sigma (compresion > 0), P y tau por grano, calculados por el script."""
    p = tabla_particulas(granos)
    c = pd.DataFrame(contactos).astype({'id_a': np.int32, 'id_b': np.int32, 'px': np.float32,
                                         'py': np.float32, 'f_norm': np.float32, 'f_tan': np.float32})
    _, part = calcular_tensor_y_presion_vectorizado(p, c, [], dt=1.0, umbral_r=0.0, g=1.0, paredes=paredes)
    return part.set_index('id')


def tensor_directo(granos, contactos_fuerza):
    """sigma = -(1/A) sum r (x) f, calculado a mano a partir de las fuerzas
    sobre cada grano (independiente de normales y convenciones del script)."""
    p = tabla_particulas(granos)
    out = {}
    for gid, fila in p.iterrows():
        S = np.zeros((2, 2))
        for (q, pc, f) in contactos_fuerza:
            if q == gid:
                r = np.array([pc[0] - fila.pos_x, pc[1] - fila.pos_y])
                S += np.outer(r, f)
        sig = -S / fila.area
        sig = 0.5 * (sig + sig.T)
        out[gid] = sig
    return out


def invariantes(sig):
    P = 0.5 * (sig[0, 0] + sig[1, 1])
    tau = np.hypot(0.5 * (sig[0, 0] - sig[1, 1]), sig[0, 1])
    return P, tau


def sigma_de(part, gid):
    f = part.loc[gid]
    return np.array([[f.sigma_xx_reducida, f.sigma_xy_reducida],
                     [f.sigma_xy_reducida, f.sigma_yy_reducida]])


# ---------------------------------------------------------------------------
# 1) Casos sinteticos
# ---------------------------------------------------------------------------

def caso_compresion_disco(theta_deg, F=3.0, R=1.0):
    u = np.array([-np.sin(np.radians(theta_deg)), np.cos(np.radians(theta_deg))])  # theta=0 -> eje y
    granos = [dict(id=0, x=0.0, y=0.0, r=R)]
    cont, cf = [], []
    for s in (+1, -1):                       # un contacto en +u y otro en -u, empujando hacia el centro
        pc = s * R * u
        f = -s * F * u
        cont.append(contacto(-1, 0, pc, -pc, f))       # pared A -> grano B: normal hacia el centro del grano
        cf.append((0, pc, f))
    return granos, cont, cf, u


def prueba_sintetica():
    print("\n== 1a) Disco comprimido a lo largo de u: sigma = (2F/A) u u^T, P = tau = F/A")
    F, R = 3.0, 1.0
    A = np.pi * R ** 2
    for th in (0, 30, 45, 90, 135):
        granos, cont, cf, u = caso_compresion_disco(th, F, R)
        part = tensor_codigo(granos, cont)
        sig = sigma_de(part, 0)
        esperado = (2 * F / A) * np.outer(u, u)
        chequear(f"theta={th:3d}  u=({u[0]:+.2f},{u[1]:+.2f})  sigma_xy={esperado[0,1]:+.3f}", sig, esperado)
        chequear(f"theta={th:3d}  P y tau", [part.loc[0, 'P'], part.loc[0, 'tau']], [F / A, F / A])

    print("\n== 1b) Corte puro con fuerzas tangenciales (torque 0): sigma_xy = -2T/A, tau = 2T/A")
    F0, T = 2.0, 0.7
    puntos = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    fuerzas = [(-F0, T), (F0, -T), (T, -F0), (-T, F0)]
    for forma in ('disco', 'cuadrado'):
        if forma == 'disco':
            granos = [dict(id=0, x=0.0, y=0.0, r=1.0)]
        else:
            granos = [dict(id=0, coords=[(-1, -1), (1, -1), (1, 1), (-1, 1)])]
        cont = [contacto(-1, 0, p, -np.array(p, float), f) for p, f in zip(puntos, fuerzas)]
        cf = [(0, p, np.array(f, float)) for p, f in zip(puntos, fuerzas)]
        part = tensor_codigo(granos, cont)
        A = part.loc[0, 'area']
        esperado = np.array([[2 * F0 / A, -2 * T / A], [-2 * T / A, 2 * F0 / A]])
        chequear(f"{forma}: sigma (codigo vs a mano)", sigma_de(part, 0), tensor_directo(granos, cf)[0])
        chequear(f"{forma}: sigma (codigo vs analitico)", sigma_de(part, 0), esperado)
        chequear(f"{forma}: P = 2F0/A, tau = 2T/A", [part.loc[0, 'P'], part.loc[0, 'tau']],
                 [2 * F0 / A, 2 * T / A])

    print("\n== 1c) Dos discos en contacto grano-grano, comprimidos a lo largo de u")
    for th in (0, 45, 120):
        u = np.array([np.cos(np.radians(th)), np.sin(np.radians(th))])
        granos = [dict(id=0, x=0.0, y=0.0, r=1.0), dict(id=1, x=2 * u[0], y=2 * u[1], r=1.0)]
        F = 1.5
        cont = [contacto(-1, 0, -u, u, F * u),            # pared empuja al grano 0 hacia +u
                contacto(0, 1, u, u, F * u),              # grano 0 (A) empuja al grano 1 (B) hacia +u
                contacto(-1, 1, 3 * u, -u, -F * u)]       # pared empuja al grano 1 hacia -u
        part = tensor_codigo(granos, cont)
        esperado = (2 * F / np.pi) * np.outer(u, u)
        chequear(f"theta={th:3d}: grano A", sigma_de(part, 0), esperado)
        chequear(f"theta={th:3d}: grano B", sigma_de(part, 1), esperado)

    print("\n== 1d) 200 granos al azar, fuerzas al azar, rotados 37 grados")
    rng = np.random.default_rng(0)
    granos, cont = [], []
    for i in range(200):
        x, y = rng.uniform(-50, 50, 2)
        granos.append(dict(id=i, x=x, y=y, r=1.0))
        for _ in range(rng.integers(2, 6)):
            a = rng.uniform(0, 2 * np.pi)
            pc = (x + np.cos(a), y + np.sin(a))
            cont.append(contacto(-1, i, pc, (-np.cos(a), -np.sin(a)), rng.normal(size=2)))
    base = tensor_codigo(granos, cont)
    ang = np.radians(37.0)
    Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    granos_r = [dict(g, x=(Rm @ [g['x'], g['y']])[0], y=(Rm @ [g['x'], g['y']])[1]) for g in granos]
    cont_r = []
    for c in cont:      # rotar punto y normal; fn y ft (componentes en la base n, t) no cambian
        cont_r.append(dict(c, px=(Rm @ [c['px'], c['py']])[0], py=(Rm @ [c['px'], c['py']])[1]))
    rot = tensor_codigo(granos_r, cont_r)
    chequear("P igual", rot['P'].to_numpy(), base['P'].to_numpy(), 1e-3)
    chequear("tau igual", rot['tau'].to_numpy(), base['tau'].to_numpy(), 1e-3)
    sig_rot = np.array([Rm @ sigma_de(base, i) @ Rm.T for i in base.index])
    chequear("sigma rota como R sigma R^T", np.array([sigma_de(rot, i) for i in base.index]), sig_rot, 1e-3)


# ---------------------------------------------------------------------------
# 2) Rotacion de un atasco real
# ---------------------------------------------------------------------------

def prueba_rotacion_real(sim_path, jam_ids, ang_deg=37.0):
    ang = np.radians(ang_deg)
    Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    for j in jam_ids:
        jam = f"{int(j):05d}"
        xy = glob.glob(os.path.join(sim_path, "frames_*", f"atasco_{jam}.xy"))
        ct = glob.glob(os.path.join(sim_path, "frames_*", f"atasco_contacts_{jam}.dat"))
        if not xy or not ct:
            sys.exit(f"[!] No encuentro atasco_{jam}.xy / atasco_contacts_{jam}.dat en {sim_path}/frames_*")
        p = pd.DataFrame.from_dict(parse_xy(xy[0]), orient='index')
        p.index.name = 'id'
        paredes = parse_paredes(xy[0])
        c = pd.read_csv(ct[0], sep=r'\s+', comment='#', header=None,
                        names=['id_a', 'id_b', 'px', 'py', 'f_norm', 'f_tan'], usecols=range(6))
        _, base = calcular_tensor_y_presion_vectorizado(p, c, [], 1.0, 0.0, g=1.0, paredes=paredes)

        pr = p.copy()
        xyr = np.stack([p['pos_x'], p['pos_y']], 1).astype(float) @ Rm.T
        pr['pos_x'], pr['pos_y'] = xyr[:, 0], xyr[:, 1]
        pr['coords'] = [None if v is None else (np.asarray(v, float) @ Rm.T) for v in p['coords']]
        cr = c.copy()
        pc = np.stack([c['px'], c['py']], 1).astype(float) @ Rm.T
        cr['px'], cr['py'] = pc[:, 0], pc[:, 1]
        par_r = paredes @ Rm.T if len(paredes) else paredes
        _, rot = calcular_tensor_y_presion_vectorizado(pr, cr, [], 1.0, 0.0, g=1.0, paredes=par_r)

        base, rot = base.set_index('id'), rot.set_index('id').loc[base.set_index('id').index]
        escala = float(np.median(base['P'].abs())) or 1.0
        print(f"\n== 2) Atasco {j}: {len(base)} granos rotados {ang_deg:.0f} grados "
              f"(errores relativos a la mediana de |P| = {escala:.4g})")
        sb = np.stack([[base.sigma_xx_reducida, base.sigma_xy_reducida],
                       [base.sigma_xy_reducida, base.sigma_yy_reducida]]).transpose(2, 0, 1)
        sr = np.stack([[rot.sigma_xx_reducida, rot.sigma_xy_reducida],
                       [rot.sigma_xy_reducida, rot.sigma_yy_reducida]]).transpose(2, 0, 1)
        esperado = Rm @ sb @ Rm.T
        for nombre, a, b in (('P', rot['P'], base['P']), ('tau', rot['tau'], base['tau']),
                             ('sigma = R sigma R^T', sr, esperado)):
            d = np.abs(np.asarray(a, float) - np.asarray(b, float)) / escala
            ok = np.percentile(d, 99) < 1e-3
            if not ok:
                fallas.append(f"atasco {j}: {nombre}")
            print(f"   [{'OK ' if ok else 'MAL'}] {nombre:24s} diferencia: mediana {np.median(d):.1e}, "
                  f"p99 {np.percentile(d, 99):.1e}, max {d.max():.1e}")


# ---------------------------------------------------------------------------
# 3) Chequeo fisico con la salida (parquet)
# ---------------------------------------------------------------------------

def prueba_parquet(path, incluir, ancho_banda, y_min):
    import pyarrow.dataset as ds
    import pyarrow.compute as pc
    cols = ['sim_path', 'jam_id', 'pos_x', 'pos_y', 'region', 'area',
            'P_reducida', 'tau_reducida', 'sigma_xx_reducida', 'sigma_yy_reducida', 'sigma_xy_reducida']
    dset = ds.dataset(path)
    filtro = pc.match_substring_regex(pc.field('sim_path'), incluir) if incluir else None
    t = dset.to_table(columns=cols, filter=filtro)
    df = t.to_pandas()
    if df.empty:
        sys.exit("[!] Ninguna fila coincide con --incluir")
    print(f"\n== 3) {os.path.basename(path)}: {len(df):,} granos, "
          f"{df.groupby(['sim_path', 'jam_id']).ngroups} atascos, {df['sim_path'].nunique()} simulaciones")
    if df['sim_path'].nunique() > 1:
        print("   (ojo: mezcla varias simulaciones; con --incluir se elige una sola configuracion)")

    xw = np.percentile(np.abs(df['pos_x']), 99.9)       # pared ~ el grano mas alejado del centro
    print(f"   pared estimada en |x| ~ {xw:.2f} (params.in: Radio_silo)")

    def media(sub, col):
        return np.average(sub[col], weights=sub['area']) if len(sub) else np.nan

    # Espejo: perfiles en bandas de x, por encima de y_min (lejos del arco)
    alto = df[df['pos_y'] > y_min]
    bordes = np.linspace(0, xw, 6)
    print(f"\n   Espejo (granos con y > {y_min}): promedio pesado por area en bandas de |x|")
    print(f"   {'banda |x|':>12s} {'sxy(x<0)':>10s} {'sxy(x>0)':>10s} {'sxx(x<0)':>10s} {'sxx(x>0)':>10s} "
          f"{'tau(x<0)':>10s} {'tau(x>0)':>10s}")
    for a, b in zip(bordes[:-1], bordes[1:]):
        izq = alto[(alto['pos_x'] < -a) & (alto['pos_x'] >= -b)]
        der = alto[(alto['pos_x'] > a) & (alto['pos_x'] <= b)]
        print(f"   {a:5.1f}-{b:5.1f} {media(izq, 'sigma_xy_reducida'):10.3f} {media(der, 'sigma_xy_reducida'):10.3f} "
              f"{media(izq, 'sigma_xx_reducida'):10.3f} {media(der, 'sigma_xx_reducida'):10.3f} "
              f"{media(izq, 'tau_reducida'):10.3f} {media(der, 'tau_reducida'):10.3f}")
    print("   Esperado: sxy(x<0) = -sxy(x>0); sxx y tau iguales a ambos lados.")

    # Paredes (Janssen)
    izq = alto[alto['pos_x'] < -(xw - ancho_banda)]
    der = alto[alto['pos_x'] > (xw - ancho_banda)]
    print(f"\n   Junto a las paredes (|x| > {xw - ancho_banda:.2f}, y > {y_min}):")
    for nombre, sub, signo in (('izquierda', izq, +1), ('derecha', der, -1)):
        sxy, sxx = media(sub, 'sigma_xy_reducida'), media(sub, 'sigma_xx_reducida')
        ok = np.sign(sxy) == signo
        print(f"   [{'OK ' if ok else '?? '}] pared {nombre:9s}: sigma_xy = {sxy:+.3f}, sigma_xx = {sxx:.3f}, "
              f"|sigma_xy|/sigma_xx = {abs(sxy) / sxx:.2f}   (esperado: signo {'+' if signo > 0 else '-'}, "
              f"cociente <= friccion de la pared)")
        if not ok:
            fallas.append(f"signo de sigma_xy en la pared {nombre}")
    if len(izq) and len(der):
        asim = (media(izq, 'sigma_xy_reducida') + media(der, 'sigma_xy_reducida')) / \
               (abs(media(izq, 'sigma_xy_reducida')) + abs(media(der, 'sigma_xy_reducida')))
        print(f"   asimetria (sxy_izq + sxy_der)/(|sxy_izq| + |sxy_der|) = {asim:+.3f}   (0 = espejo perfecto)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sintetico', action='store_true', help='casos con resultado conocido (no necesita datos)')
    ap.add_argument('--sim_path', help='carpeta de una simulacion: rota atascos reales')
    ap.add_argument('--jam_id', nargs='+', default=['1'])
    ap.add_argument('--angulo', type=float, default=37.0, help='angulo de rotacion en grados (default 37)')
    ap.add_argument('--parquet', help='presion_por_particula_<Forma>.parquet: chequeo de espejo y paredes')
    ap.add_argument('--incluir', default=None, help='regex sobre sim_path para elegir una configuracion')
    ap.add_argument('--ancho_banda', type=float, default=2.0, help='ancho de la franja junto a la pared')
    ap.add_argument('--y_min', type=float, default=15.0, help='solo granos por encima de esta altura')
    args = ap.parse_args()
    if not (args.sintetico or args.sim_path or args.parquet):
        args.sintetico = True

    if args.sintetico:
        prueba_sintetica()
    if args.sim_path:
        prueba_rotacion_real(args.sim_path, args.jam_id, args.angulo)
    if args.parquet:
        prueba_parquet(args.parquet, args.incluir, args.ancho_banda, args.y_min)

    print("\n" + ("TODO OK" if not fallas else f"{len(fallas)} chequeos fallaron: " + "; ".join(fallas)))
    sys.exit(1 if fallas else 0)


if __name__ == '__main__':
    main()
