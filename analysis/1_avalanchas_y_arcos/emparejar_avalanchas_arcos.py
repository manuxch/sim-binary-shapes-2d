#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Une cada avalancha con el arco (snapshot atasco_XXXXX.xy) que la detuvo.

Entrada (salidas de processor.py y arch_consolidator.py):
  processed_data/1_avalanche_data/resultados_completos_esqueleto.csv
      columnas atasco_id / emparejado_ok (las agrega processor.py)
  processed_data/1_avalanche_data/resultados_completos_arcos.csv
      columna Atasco_ID (numero del atasco_XXXXX.xy)

Salida:
  processed_data/1_avalanche_data/resultados_avalanchas_con_arco.csv
      una fila por avalancha que termino en un atasco permanente con arco
      detectado: columnas de la avalancha + columnas del arco.

Solo quedan las avalanchas que terminaron en un atasco que se guardo
(detencion de mas de 0.5 + tEsperaAtasco s). Las que se cortaron por una
detencion que se resolvio sola no tienen arco y no aparecen.

Uso:
    python3 analysis/1_avalanchas_y_arcos/emparejar_avalanchas_arcos.py
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas  # noqa: E402


def emparejar(av_path, arcos_path):
    av = pd.read_csv(av_path)
    if 'atasco_id' not in av.columns:
        sys.exit("[!] El esqueleto no tiene la columna atasco_id: correr processor.py --emparejar.")
    arc = pd.read_csv(arcos_path)
    arc = arc[pd.to_numeric(arc['Atasco_ID'], errors='coerce').notna()].copy()
    arc['atasco_id'] = arc['Atasco_ID'].astype(int)

    con_atasco = av[av['atasco_id'].notna()].copy()
    con_atasco['atasco_id'] = con_atasco['atasco_id'].astype(int)
    # columnas del arco que no repiten las de la avalancha (salvo las claves)
    cols_arc = ['sim_hash', 'atasco_id'] + [c for c in arc.columns
                                           if c not in con_atasco.columns and c != 'Atasco_ID']
    unido = con_atasco.merge(arc[cols_arc], on=['sim_hash', 'atasco_id'], how='inner')

    n_sims = av['sim_hash'].nunique()
    n_sims_mal = av.loc[~av['emparejado_ok'].astype(bool), 'sim_hash'].nunique() if 'emparejado_ok' in av else 0
    print(f"Avalanchas totales:                         {len(av)}  ({n_sims} simulaciones)")
    print(f"  terminaron en un atasco guardado:         {len(con_atasco)} ({100 * len(con_atasco) / max(len(av), 1):.1f} %)")
    print(f"  ... y con arco detectado en ese atasco:   {len(unido)} ({100 * len(unido) / max(len(av), 1):.1f} %)")
    if n_sims_mal:
        print(f"  simulaciones sin emparejar (atascos predichos != atasco_*.xy en disco): {n_sims_mal}")
    return unido


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--av', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_esqueleto.csv'))
    ap.add_argument('--arcos', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_completos_arcos.csv'))
    ap.add_argument('--out', default=os.path.join(rutas.AVALANCHE_DIR, 'resultados_avalanchas_con_arco.csv'))
    args = ap.parse_args()
    unido = emparejar(args.av, args.arcos)
    unido.to_csv(args.out, index=False)
    print(f"Guardado: {args.out}")


if __name__ == '__main__':
    main()
