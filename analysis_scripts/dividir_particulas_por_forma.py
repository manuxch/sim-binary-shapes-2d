#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Divide presion_por_particula.csv (que puede ser enorme, con todas las
geometrías mezcladas) en un archivo separado por cada forma_grande, en
UNA sola pasada por el archivo — en vez de tener que leerlo entero cada
vez que se quiera procesar una sola geometría después.

Si pyarrow está instalado, escribe Parquet (columnar, comprimido —
sensiblemente más chico y mucho más rápido de leer después). Si no, cae
a CSV plano por geometría (igual mucho más chico que el original, al
estar dividido en 4).

Uso:
    python3 dividir_particulas_por_forma.py --csv presion_por_particula.csv --out_dir por_forma/

Después, en barrido_heatmap.py:
    --csv por_forma/presion_por_particula_Disco.parquet   (o .csv)
"""
import argparse
import os
import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    TIENE_PYARROW = True
except ImportError:
    TIENE_PYARROW = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='presion_por_particula.csv (el grande, sin dividir)')
    parser.add_argument('--out_dir', required=True)
    parser.add_argument('--chunksize', type=int, default=1_000_000)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    if not TIENE_PYARROW:
        print("AVISO: pyarrow no está instalado -> se va a escribir CSV plano por geometría")
        print("       en vez de Parquet. 'pip install pyarrow' y volver a correr esto da")
        print("       archivos bastante más chicos y mucho más rápidos de leer después.")
        print()

    escritores = {}       # forma -> ParquetWriter (si hay pyarrow)
    ya_creado_csv = set()  # formas para las que ya se escribio el header del csv
    filas_por_forma = {}
    filas_totales = 0

    for chunk in pd.read_csv(args.csv, dtype={'jam_id': str}, chunksize=args.chunksize, na_filter=False):
        filas_totales += len(chunk)
        col_filtro = 'forma_grande' if 'forma_grande' in chunk.columns else 'shape'

        for forma, sub in chunk.groupby(col_filtro):
            filas_por_forma[forma] = filas_por_forma.get(forma, 0) + len(sub)

            if TIENE_PYARROW:
                tabla = pa.Table.from_pandas(sub, preserve_index=False)
                if forma not in escritores:
                    path = os.path.join(args.out_dir, f"presion_por_particula_{forma}.parquet")
                    escritores[forma] = pq.ParquetWriter(path, tabla.schema)
                escritores[forma].write_table(tabla)
            else:
                path = os.path.join(args.out_dir, f"presion_por_particula_{forma}.csv")
                header = forma not in ya_creado_csv
                sub.to_csv(path, mode='a', index=False, header=header)
                ya_creado_csv.add(forma)

        print(f"  {filas_totales:,} filas procesadas...", end='\r')

    print()
    if TIENE_PYARROW:
        for w in escritores.values():
            w.close()

    print("\nListo. Filas por geometría:")
    for forma, n in filas_por_forma.items():
        print(f"  {forma}: {n:,}")
    print(f"\nArchivos en: {args.out_dir}/")


if __name__ == '__main__':
    main()
