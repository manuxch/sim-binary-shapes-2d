#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grafica la presión media reducida (P/g) en función de chi, un panel por
cada geometría de grano grande, comparando la región arco contra la roi
(grandes en línea sólida, chicas en punteada), a partir de
resumen_presion_por_atasco.csv (el crudo por atasco, no el ya agregado
por configuración).

Por qué desde el crudo y no desde resumen_presion_por_configuracion.csv:
si hay más de una configuración compartiendo el mismo chi (por ejemplo,
distintos anchos de orificio W), agregar solo por forma+chi acá evita que
esos puntos separados queden conectados en zigzag en vez de promediados
en un solo punto por chi.

Además, filtra por razón de áreas (chica/grande) ANTES de agregar: las
carpetas "Ratio_X_..." codifican esa razón en el nombre, y las carpetas
"Chi_X_W_Y" (sin prefijo "Ratio_") son, confirmado con
check_ratio_tamano.py, la misma razón física que "Ratio_0p1" (0.158/0.5
al cuadrado ≈ 0.0999) — asi que se funden automáticamente dentro de ese
grupo, en vez de quedar como una familia aparte o (peor) mezclarse con
razones distintas.

Uso:
    python3 comparar_presion_por_chi.py --csv resumen_presion_por_atasco.csv \
        --out comparacion_chi.png

    # Otra razon de areas, otro subconjunto de formas, u otro rango de chi:
    python3 comparar_presion_por_chi.py --csv resumen_presion_por_atasco.csv \
        --ratio 0.3 --formas Disco Cuadrado --chi_max 0.4 --out comparacion_chi.png
"""
import argparse
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['mathtext.fontset'] = 'stix'

# Vermillion para arco, azul para roi (paleta Wong, colorblind-safe) --
# mismo rojo que ya se usa para marcar el arco en graficar_presion_atasco.py
COLOR_ARCO = '#D55E00'
COLOR_ROI = '#0072B2'
REGIONES = ('arco', 'roi')

RATIO_REGEX = re.compile(r'Ratio_([0-9]+p[0-9]+)')
# Carpetas "Chi_X_W_Y" sin prefijo "Ratio_" -> misma razon fisica que
# Ratio_0p1 (confirmado a mano: 0.158/0.5 al cuadrado = 0.0999). Si en el
# futuro aparece otra familia sin prefijo con otra razon, este valor por
# defecto ya no aplicaria y habria que revisarlo.
RATIO_SIN_PREFIJO = 0.1


def extraer_ratio_area(sim_path):
    m = RATIO_REGEX.search(str(sim_path))
    if m:
        return float(m.group(1).replace('p', '.'))
    return RATIO_SIN_PREFIJO


def agregar_por_forma_y_chi(df, regiones=REGIONES):
    """Suma SumP_reducida_{region}_{B,S} y Area_{region}_{B,S} agrupando
    SOLO por (forma_grande, chi) -- pooleando todos los atascos de
    cualquier configuracion/ancho que comparta ese chi -- y recien ahi
    divide, para tener un unico punto, correctamente ponderado por area,
    por cada combinacion forma+chi. Hace las dos regiones (arco y roi) de
    una sola pasada, en vez de agregar dos veces por separado."""
    cols_necesarias = []
    for region in regiones:
        cols_necesarias += [f'SumP_reducida_{region}_B', f'Area_{region}_B',
                             f'SumP_reducida_{region}_S', f'Area_{region}_S']
    faltantes = [c for c in cols_necesarias if c not in df.columns]
    if faltantes:
        raise SystemExit(
            f"Al csv le faltan columnas {faltantes}. Hace falta la version "
            f"de presion_tensor_arch_corregido.py con presion reducida."
        )

    g = df.groupby(['forma_grande', 'chi'], dropna=False)
    out = g[cols_necesarias].sum().reset_index()
    out['n_atascos'] = g.size().to_numpy()

    for region in regiones:
        out[f'mean_P_reducida_{region}_B'] = out[f'SumP_reducida_{region}_B'] / out[f'Area_{region}_B']
        out[f'mean_P_reducida_{region}_S'] = out[f'SumP_reducida_{region}_S'] / out[f'Area_{region}_S']
    return out


def graficar_una_forma(df_agg, forma, regiones=REGIONES):
    """Una sola figura, para una sola forma de grano grande: arco vs roi,
    grandes vs chicas, en funcion de chi."""
    colores = {regiones[0]: COLOR_ARCO, regiones[1]: COLOR_ROI}
    sub = df_agg[df_agg['forma_grande'] == forma].sort_values('chi')

    fig, ax = plt.subplots(figsize=(6.5, 5))
    for region in regiones:
        color = colores[region]
        ax.plot(sub['chi'], sub[f'mean_P_reducida_{region}_B'], color=color, linestyle='-',
                 marker='o', markersize=4, label=f'{region} — grandes')
        # Las chicas no existen en chi=0 (Area=0 -> NaN); matplotlib corta
        # la linea ahi solo, no hace falta filtrar a mano.
        ax.plot(sub['chi'], sub[f'mean_P_reducida_{region}_S'], color=color, linestyle='--',
                 marker='s', markersize=4, label=f'{region} — chicas')

    ax.set_title(forma)
    ax.set_xlabel(r'$\chi$ (fracción de área de chicas)')
    ax.set_ylabel(r'Presión media reducida $\langle P\rangle / g$')
    ax.legend(loc='center left', bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=9)
    fig.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='resumen_presion_por_atasco.csv')
    parser.add_argument('--out', default='comparacion_chi.png')
    parser.add_argument('--ratio', type=float, default=0.1,
                         help='Razon de areas (chica/grande) a incluir (default: 0.1)')
    parser.add_argument('--formas', nargs='+', default=None,
                         help='Lista de forma_grande a incluir (default: todas las presentes en el csv)')
    parser.add_argument('--chi_min', type=float, default=None)
    parser.add_argument('--chi_max', type=float, default=None)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    df['ratio_area'] = df['sim_path'].apply(extraer_ratio_area)
    df = df[np.isclose(df['ratio_area'], args.ratio, atol=1e-3)]
    if df.empty:
        raise SystemExit(f"No quedo ninguna fila con ratio_area ~= {args.ratio} — revisa --ratio.")
    print(f"Razon de areas = {args.ratio}: {df['sim_path'].nunique()} carpetas distintas incluidas "
          f"({df['config_id'].nunique()} config_id distintos).")

    if args.formas is not None:
        df = df[df['forma_grande'].isin(args.formas)]
    if args.chi_min is not None:
        df = df[df['chi'] >= args.chi_min]
    if args.chi_max is not None:
        df = df[df['chi'] <= args.chi_max]
    if df.empty:
        raise SystemExit("No quedaron filas despues de filtrar — revisa --formas/--chi_min/--chi_max.")

    df_agg = agregar_por_forma_y_chi(df)
    formas = args.formas if args.formas is not None else sorted(df_agg['forma_grande'].dropna().unique())

    base, ext = os.path.splitext(args.out)
    for forma in formas:
        if forma not in df_agg['forma_grande'].values:
            print(f"(sin datos para {forma!r}, se salta)")
            continue
        fig = graficar_una_forma(df_agg, forma)
        out_path = f"{base}_{forma}{ext}"
        fig.savefig(out_path, dpi=200, bbox_inches='tight')
        plt.close(fig)
        print(f"Guardado: {out_path}")


if __name__ == '__main__':
    main()