#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara, por simulacion, cuantos registros de avalanchas y de arcos hay:

  - avalanchas: processed_data/1_avalanche_data/resultados_completos_esqueleto.csv
    (processor.py: una fila por racha de descarga separada por > 0.5 s sin
    granos, detectada en flx.dat)
  - arcos:      processed_data/1_avalanche_data/resultados_completos_arcos.csv
    (generar_csv_arcos.py + arch_consolidator.py: una fila por snapshot de
    atasco atasco_XXXXX.xy con arco detectado)

No tienen por que coincidir: el simulador guarda un snapshot de atasco solo
cuando la detencion dura tEsperaAtasco (5 s) y hay que desatascar; las
detenciones que se resuelven solas (> 0.5 s y < 5 s) cortan una avalancha
pero no generan arco. Un desatasco fallido genera otro snapshot sin
avalancha en el medio.

Ademas verifica si emparejar las dos tablas fila por fila (como hace
'paste' en analysis/4_correlaciones_gnuplot/*.gp) junta filas de
simulaciones distintas.

Uso:
    python3 analysis/utils/contar_avalanchas_vs_arcos.py
    python3 analysis/utils/contar_avalanchas_vs_arcos.py --av otro_esqueleto.csv --arcos otro_arcos.csv
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rutas  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--av', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_esqueleto.csv'))
    ap.add_argument('--arcos', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_arcos.csv'))
    ap.add_argument('--out', default=None, help='CSV con la tabla por simulacion (opcional)')
    args = ap.parse_args()

    av = pd.read_csv(args.av)
    arc = pd.read_csv(args.arcos)
    for nombre, df in (('avalanchas', av), ('arcos', arc)):
        if 'sim_hash' not in df.columns:
            sys.exit(f"[!] La tabla de {nombre} no tiene columna sim_hash")

    n_av = av.groupby('sim_hash').size().rename('n_avalanchas')
    n_arc = arc.groupby('sim_hash').size().rename('n_arcos')
    t = pd.concat([n_av, n_arc], axis=1).fillna(0).astype(int)
    t['arcos/avalanchas'] = t['n_arcos'] / t['n_avalanchas'].replace(0, np.nan)
    meta = [c for c in ('chi', 'area_ratio_nominal', 'system_type', 'path') if c in arc.columns]
    if meta:
        t = t.join(arc.groupby('sim_hash')[meta].first())

    print(f"Avalanchas: {len(av)} filas en {av['sim_hash'].nunique()} simulaciones   ({args.av})")
    print(f"Arcos:      {len(arc)} filas en {arc['sim_hash'].nunique()} simulaciones   ({args.arcos})")
    print(f"\nPor simulacion ({len(t)}):")
    print(f"  mas avalanchas que arcos: {(t['n_avalanchas'] > t['n_arcos']).sum()}")
    print(f"  igual cantidad:           {(t['n_avalanchas'] == t['n_arcos']).sum()}")
    print(f"  mas arcos que avalanchas: {(t['n_avalanchas'] < t['n_arcos']).sum()}")
    print(f"  solo avalanchas (sin arcos): {(t['n_arcos'] == 0).sum()}   solo arcos (sin avalanchas): {(t['n_avalanchas'] == 0).sum()}")
    r = t['arcos/avalanchas'].dropna()
    if len(r):
        print(f"  arcos/avalanchas: mediana {r.median():.2f}  (min {r.min():.2f}, max {r.max():.2f})")
    print(f"  avalanchas por simulacion: mediana {int(t['n_avalanchas'].median())}, "
          f"arcos por simulacion: mediana {int(t['n_arcos'].median())}")

    # Emparejamiento fila a fila (lo que hace 'paste' en los .gp)
    n = min(len(av), len(arc))
    distinta = (av['sim_hash'].to_numpy()[:n] != arc['sim_hash'].to_numpy()[:n])
    print(f"\nEmparejando fila a fila (como 'paste' en analysis/4_correlaciones_gnuplot/):")
    print(f"  filas que quedan de simulaciones DISTINTAS: {distinta.sum()} de {n} ({100 * distinta.mean():.1f} %)")
    if len(av) != len(arc):
        print(f"  ademas sobran {abs(len(av) - len(arc))} filas en una de las dos tablas")
    print("  => una correlacion avalancha-arco armada asi no empareja cada avalancha con su arco.")

    if args.out:
        t.to_csv(args.out)
        print(f"\nTabla por simulacion: {args.out}")


if __name__ == '__main__':
    main()
