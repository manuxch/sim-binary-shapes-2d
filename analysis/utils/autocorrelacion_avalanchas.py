"""
Autocorrelacion de los tamanos de avalancha dentro de cada corrida larga y
error de la media por bloques.

flow_analysis.py calcula S_sem = std / sqrt(N) suponiendo avalanchas
independientes. Como todas las avalanchas de una configuracion salen de una
sola corrida (con desatascos), avalanchas consecutivas podrian estar
correlacionadas y ese error quedaria subestimado. Para cada simulacion:

  rho_1, rho_2, rho_3   autocorrelacion de s_i con s_{i+k} (orden temporal)
  tau_int               tiempo de autocorrelacion integrado,
                        1/2 + sum_k rho_k (ventana de Sokal, c = 5);
                        0.5 = sin correlacion
  sem_ingenuo           std / sqrt(N) (lo que usan las figuras)
  sem_bloques           metodo de bloques (Flyvbjerg-Petersen): se promedian
                        avalanchas de a pares sucesivamente y se toma el
                        maximo de los SEM con al menos 32 bloques
  razon                 sem_bloques / sem_ingenuo (~1 = sin correlacion)
  rho1_signif           |rho_1| > 2/sqrt(N) (fuera del 95 % de ruido blanco)

Uso (desde la raiz del repo):
    python3 analysis/utils/autocorrelacion_avalanchas.py
    python3 analysis/utils/autocorrelacion_avalanchas.py --sistema Disco-Disco Disco-Cuad --area_ratio 0.1
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas  # noqa: E402

MIN_BLOQUES = 32


def autocorrelacion(x, k_max):
    x = np.asarray(x, float) - np.mean(x)
    var = np.dot(x, x) / len(x)
    if var == 0:
        return np.zeros(k_max)
    return np.array([np.dot(x[:-k], x[k:]) / len(x) / var for k in range(1, k_max + 1)])


def tau_integrado(x, c=5.0):
    """1/2 + sum_k rho_k, cortando la suma en el primer k >= c * tau (Sokal)."""
    rho = autocorrelacion(x, min(len(x) // 4, 1000))
    tau = 0.5
    for k, r in enumerate(rho, start=1):
        tau += r
        if k >= c * tau:
            break
    return tau


def sem_bloques(x, min_bloques=MIN_BLOQUES):
    """Flyvbjerg-Petersen: SEM a cada nivel de agrupamiento de a pares; se
    devuelve el maximo entre los niveles con al menos min_bloques bloques."""
    x = np.asarray(x, float)
    sems = []
    while len(x) >= min_bloques:
        sems.append(np.std(x, ddof=1) / np.sqrt(len(x)))
        n = len(x) // 2
        x = 0.5 * (x[:2 * n:2] + x[1:2 * n:2])
    return max(sems) if sems else np.nan


def analizar(s):
    n = len(s)
    rho = autocorrelacion(s, 3)
    sem0 = np.std(s, ddof=1) / np.sqrt(n)
    semb = sem_bloques(s)
    return {
        'n_avalanchas': n, 'S_mean': float(np.mean(s)),
        'rho_1': rho[0], 'rho_2': rho[1], 'rho_3': rho[2],
        'tau_int': tau_integrado(s),
        'sem_ingenuo': sem0, 'sem_bloques': semb, 'razon': semb / sem0 if sem0 > 0 else np.nan,
        'rho1_signif': abs(rho[0]) > 2 / np.sqrt(n),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--av', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_esqueleto.csv'))
    ap.add_argument('--idx', default=rutas.MASTER_INDEX)
    ap.add_argument('--sistema', nargs='+', default=None, help="system_type del indice (ej. Disco-Disco Disco-Cuad)")
    ap.add_argument('--area_ratio', type=float, default=None, help="area_ratio_nominal (ej. 0.1)")
    ap.add_argument('--min_avalanchas', type=int, default=100)
    ap.add_argument('--out', default=os.path.join(rutas.AVALANCHE_DIR, 'autocorrelacion_avalanchas.csv'))
    args = ap.parse_args()

    av = pd.read_csv(args.av)
    idx = pd.read_csv(args.idx)[['sim_hash', 'system_type', 'chi', 'area_ratio_nominal', 'path']]
    av = av.merge(idx, on='sim_hash', how='left')
    if args.sistema:
        av = av[av['system_type'].isin(args.sistema)]
    if args.area_ratio is not None:
        av = av[np.isclose(av['area_ratio_nominal'].astype(float), args.area_ratio, atol=0.03)]

    filas = []
    for h, g in av.groupby('sim_hash'):
        g = g.sort_values('t_inicio')
        if len(g) < args.min_avalanchas:
            continue
        meta = g.iloc[0]
        filas.append({'sim_hash': h, 'system_type': meta['system_type'], 'chi': meta['chi'],
                      'area_ratio_nominal': meta['area_ratio_nominal'],
                      **analizar(g['tamano_big'].to_numpy()),
                      'carpeta': '/'.join(str(meta['path']).split('/')[-2:])})
    if not filas:
        sys.exit("[!] Ninguna simulacion con suficientes avalanchas (revisar filtros / --min_avalanchas).")
    r = pd.DataFrame(filas).sort_values(['system_type', 'chi'])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    r.to_csv(args.out, index=False)

    cols = ['system_type', 'chi', 'n_avalanchas', 'rho_1', 'tau_int', 'razon', 'rho1_signif', 'carpeta']
    with pd.option_context('display.width', 220, 'display.max_rows', 500):
        print(r[cols].to_string(index=False, float_format='%.3f'))
    print(f"\n{len(r)} simulaciones con >= {args.min_avalanchas} avalanchas. Tabla completa: {args.out}")
    print(f"rho_1:  mediana {r['rho_1'].median():+.3f}, rango [{r['rho_1'].min():+.3f}, {r['rho_1'].max():+.3f}]")
    print(f"|rho_1| > 2/sqrt(N) (fuera del 95 % de ruido blanco): {int(r['rho1_signif'].sum())} de {len(r)} "
          f"(se esperan ~{0.05 * len(r):.0f} por azar)")
    print(f"tau_int: mediana {r['tau_int'].median():.2f} (0.5 = sin correlacion)")
    print(f"sem_bloques / sem_ingenuo: mediana {r['razon'].median():.2f}, maximo {r['razon'].max():.2f}")


if __name__ == '__main__':
    main()
