#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grafica en funcion de chi, un panel por cada geometria de grano grande,
comparando la region arco contra la roi (grandes en linea solida, chicas
en punteada), a partir de resumen_presion_por_atasco.csv (el crudo por
atasco, no el ya agregado por configuracion). Dos magnitudes, en figuras
separadas:

  - Presion media reducida  <P>/g    -> <out>_<Forma>.png
  - Esfuerzo de corte medio <tau>/g  -> <out>_tau_<Forma>.png
    (tau = radio del circulo de Mohr del tensor de cada particula, la
    parte deviatorica; promedio pesado por area, igual que P)

Por que desde el crudo y no desde resumen_presion_por_configuracion.csv:
si hay mas de una configuracion compartiendo el mismo chi (por ejemplo,
distintos anchos de orificio W), agregar solo por forma+chi aca evita que
esos puntos separados queden conectados en zigzag en vez de promediados
en un solo punto por chi.

Ademas, filtra por razon de areas (chica/grande) ANTES de agregar: las
carpetas "Ratio_X_..." codifican esa razon en el nombre, y las carpetas
"Chi_X_W_Y" (sin prefijo "Ratio_") son, confirmado con
check_ratio_tamano.py, la misma razon fisica que "Ratio_0p1" (0.158/0.5
al cuadrado ~ 0.0999) -- asi que se funden automaticamente dentro de ese
grupo.

Si el csv viene de presion_tensor_arch.py con lotes reanudables (columna
'lote'), solo se usan las filas de lotes confirmados en lotes_ok.txt
(misma carpeta que el csv): asi un lote a medio escribir de una corrida
cortada no aparece duplicado.

Uso:
    python3 comparar_presion_por_chi.py --csv resumen_presion_por_atasco.csv \\
        --out comparacion_chi.png
    # -> comparacion_chi_<Forma>.png (presion) y comparacion_chi_tau_<Forma>.png (corte)

    # Solo una magnitud, otra razon de areas, otras formas u otro rango de chi:
    python3 comparar_presion_por_chi.py --csv resumen_presion_por_atasco.csv \\
        --magnitud tau --ratio 0.3 --formas Disco Cuadrado --chi_max 0.4 --out comparacion_chi.png
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

# magnitud -> (prefijo de las columnas del csv, etiqueta del eje y, sufijo del archivo)
MAGNITUDES = {
    'P':   ('SumP_reducida',   r'Presión media reducida $\langle P\rangle / g$', ''),
    'tau': ('SumTau_reducida', r'Esfuerzo de corte medio reducido $\langle \tau\rangle / g$', '_tau'),
}

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


def filtrar_lotes_confirmados(df, csv_path):
    """Si el csv tiene la columna 'lote', se queda solo con los lotes de
    lotes_ok.txt (los que terminaron de guardarse)."""
    if 'lote' not in df.columns:
        return df
    f_ok = os.path.join(os.path.dirname(os.path.abspath(csv_path)), 'lotes_ok.txt')
    if not os.path.exists(f_ok):
        print(f"AVISO: el csv tiene columna 'lote' pero no encontre {f_ok}; se usan todas las filas.")
        return df
    with open(f_ok) as f:
        ok = {l.strip() for l in f if l.strip()}
    antes = len(df)
    df = df[df['lote'].astype(str).isin(ok)]
    if len(df) < antes:
        print(f"Se descartan {antes - len(df)} filas de lotes sin confirmar (corrida cortada).")
    return df


def agregar_por_forma_y_chi(df, magnitudes, regiones=REGIONES):
    """Suma <prefijo>_{region}_{B,S} y Area_{region}_{B,S} agrupando SOLO
    por (forma_grande, chi) -- pooleando todos los atascos de cualquier
    configuracion/ancho que comparta ese chi -- y recien ahi divide, para
    tener un unico punto, correctamente ponderado por area, por cada
    combinacion forma+chi."""
    cols_necesarias = []
    for region in regiones:
        for t in ('B', 'S'):
            cols_necesarias.append(f'Area_{region}_{t}')
            for mag in magnitudes:
                cols_necesarias.append(f'{MAGNITUDES[mag][0]}_{region}_{t}')
    faltantes = [c for c in cols_necesarias if c not in df.columns]
    if faltantes:
        pista = (" Las columnas SumTau_* las escribe la version de presion_tensor_arch.py "
                 "con esfuerzo de corte: hay que volver a correrlo."
                 if any(c.startswith('SumTau') for c in faltantes) else "")
        raise SystemExit(f"Al csv le faltan columnas {faltantes}.{pista}")

    g = df.groupby(['forma_grande', 'chi'], dropna=False)
    out = g[cols_necesarias].sum().reset_index()
    out['n_atascos'] = g.size().to_numpy()

    for mag in magnitudes:
        pref = MAGNITUDES[mag][0]
        for region in regiones:
            for t in ('B', 'S'):
                out[f'mean_{mag}_{region}_{t}'] = out[f'{pref}_{region}_{t}'] / out[f'Area_{region}_{t}']
    return out


def graficar_una_forma(df_agg, forma, mag, etiqueta_chi, regiones=REGIONES):
    """Una sola figura, para una sola forma de grano grande y una magnitud:
    arco vs roi, grandes vs chicas, en funcion de chi."""
    colores = {regiones[0]: COLOR_ARCO, regiones[1]: COLOR_ROI}
    sub = df_agg[df_agg['forma_grande'] == forma].sort_values('chi')

    fig, ax = plt.subplots(figsize=(6.5, 5))
    for region in regiones:
        color = colores[region]
        ax.plot(sub['chi'], sub[f'mean_{mag}_{region}_B'], color=color, linestyle='-',
                marker='o', markersize=4, label=f'{region} — grandes')
        # Las chicas no existen en chi=0 (Area=0 -> NaN); matplotlib corta
        # la linea ahi solo, no hace falta filtrar a mano.
        ax.plot(sub['chi'], sub[f'mean_{mag}_{region}_S'], color=color, linestyle='--',
                marker='s', markersize=4, label=f'{region} — chicas')

    ax.set_title(forma)
    ax.set_xlabel(etiqueta_chi)
    ax.set_ylabel(MAGNITUDES[mag][1])
    ax.legend(loc='center left', bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=9)
    fig.tight_layout()
    return fig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', required=True, help='resumen_presion_por_atasco.csv')
    parser.add_argument('--out', default='comparacion_chi.png')
    parser.add_argument('--magnitud', choices=['P', 'tau', 'ambas'], default='ambas',
                        help="P (presion), tau (esfuerzo de corte) o ambas (default), "
                             "cada una en su propia figura")
    parser.add_argument('--ratio', type=float, default=0.1,
                        help='Razon de areas (chica/grande) a incluir (default: 0.1)')
    parser.add_argument('--formas', nargs='+', default=None,
                        help='Lista de forma_grande a incluir (default: todas las presentes en el csv)')
    parser.add_argument('--chi_min', type=float, default=None)
    parser.add_argument('--chi_max', type=float, default=None)
    parser.add_argument('--etiqueta_chi', default=r'$\chi$ (fracción de área de chicas)',
                        help='Texto del eje x')
    args = parser.parse_args()

    magnitudes = ['P', 'tau'] if args.magnitud == 'ambas' else [args.magnitud]

    df = pd.read_csv(args.csv, dtype={'lote': str, 'jam_id': str})
    df = filtrar_lotes_confirmados(df, args.csv)
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

    df_agg = agregar_por_forma_y_chi(df, magnitudes)
    formas = args.formas if args.formas is not None else sorted(df_agg['forma_grande'].dropna().unique())
    print("Atascos por forma y chi:")
    print(df_agg[['forma_grande', 'chi', 'n_atascos']].to_string(index=False))

    base, ext = os.path.splitext(args.out)
    for mag in magnitudes:
        sufijo = MAGNITUDES[mag][2]
        for forma in formas:
            if forma not in df_agg['forma_grande'].values:
                print(f"(sin datos para {forma!r}, se salta)")
                continue
            fig = graficar_una_forma(df_agg, forma, mag, args.etiqueta_chi)
            out_path = f"{base}{sufijo}_{forma}{ext}"
            fig.savefig(out_path, dpi=200, bbox_inches='tight')
            plt.close(fig)
            print(f"Guardado: {out_path}")


if __name__ == '__main__':
    main()