import os
from dataclasses import dataclass, field
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # estilo_figuras.py y rutas.py viven en analysis/
import rutas
from estilo_figuras import (SYSTEM_STYLE, ENGLISH_LABELS, SYSTEM_NAME_MAP,
                            set_plot_fonts, aplicar_estilo, ERRORBAR_KW,
                            REF_LINE_KW, SEQ_STYLE, anotar_chi)

# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

@dataclass
class AnalysisConfig:
    """Rutas y estilos comunes para todas las figuras."""
    data_path: str = os.path.join(rutas.AVALANCHE_DIR, "estadisticas_flujo_agregadas.csv")
    arcos_path: str = os.path.join(rutas.AVALANCHE_DIR, "resultados_completos_arcos.csv")
    raw_flow_path: str = os.path.join(rutas.AVALANCHE_DIR, "resultados_completos_esqueleto.csv")
    out_dir: str = rutas.GRAFICOS_FINALES_DIR

    # Estilos: vienen de estilo_figuras.py (comun a todos los scripts)
    system_style: Dict[str, Tuple[str, str]] = field(default_factory=lambda: dict(SYSTEM_STYLE))
    english_labels: Dict[str, str] = field(default_factory=lambda: dict(ENGLISH_LABELS))

CFG = AnalysisConfig()

# Esquema NUEVO de los CSV corregidos.
AR_COL = "area_ratio_nominal"
RR_COL = "r_ratio_nominal"

# SYSTEM_NAME_MAP viene de estilo_figuras.py

# =============================================================================
# HELPERS
# =============================================================================

def save_plot(filename: str):
    os.makedirs(CFG.out_dir, exist_ok=True)
    plt.savefig(f"{CFG.out_dir}/{filename}.pdf", bbox_inches='tight')
    plt.close()


def require_columns(df: pd.DataFrame, cols: List[str], context: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(
            f"Faltan columnas en {context}: {missing}\n"
            f"Columnas disponibles: {df.columns.tolist()}"
        )


def prepare_flow_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida el CSV estadisticas_flujo_agregadas.csv generado por flow_analysis.py.

    Esquema esperado:
        sistema, chi, r_ratio_nominal, area_ratio_nominal, D_d_sq, grano_base,
        S_mean, S_sem, log_S, log_S_err, ...
    """
    require_columns(
        df,
        ['sistema', 'chi', AR_COL, RR_COL, 'D_d_sq', 'grano_base', 'S_mean', 'S_sem', 'log_S', 'log_S_err'],
        'estadisticas_flujo_agregadas.csv',
    )
    return df.copy()


def prepare_arcos(df_arcos: pd.DataFrame) -> pd.DataFrame:
    """
    Valida y normaliza resultados_completos_arcos.csv generado por arch_consolidator.py.

    Ese archivo debe traer columnas reales y nominales desde master_sim_index.csv.
    Para agrupar/graficar se usan SOLO las nominales.
    """
    require_columns(
        df_arcos,
        ['sim_hash', 'system_type', 'chi', AR_COL, RR_COL,
         'Total_Particulas_Arco', 'Particulas_Tipo_0', 'Particulas_Tipo_1',
         'Tortuosidad', 'Relacion_Aspecto', 'Altura', 'Span', 'Longitud'],
        'resultados_completos_arcos.csv',
    )

    out = df_arcos.copy()
    out['sistema'] = out['system_type'].map(SYSTEM_NAME_MAP)
    out = out.dropna(subset=['sistema'])
    return out


def get_pure_ref(df: pd.DataFrame, system_name: str, orifice: float, col: str = 'log_S'):
    """Referencia del sistema puro de la matriz correspondiente."""
    matrix_type = system_name.split('(')[0]
    ref = df[(df['chi'] == 0.0) &
             (df['sistema'].str.startswith(matrix_type)) &
             (df['D_d_sq'] == orifice)]
    if ref.empty:
        return None, None

    if col == 'log_S':
        err_col = 'log_S_err'
    elif col == 'S_mean':
        err_col = 'S_sem'
    else:
        err_col = col + '_err'

    if err_col not in ref.columns:
        return ref[col].mean(), None

    return ref[col].mean(), ref[err_col].mean()


def filter_standard_size(df: pd.DataFrame, target_ar: float, atol: float, system_col: str = 'sistema') -> pd.DataFrame:
    """
    Filtro estándar para comparar sistemas a tamaño aproximadamente fijo.

    Usa area_ratio_nominal. Esto es importante: no usar area_ratio real para seleccionar
    curvas porque separa artificialmente 0.0998 y 0.0999.
    """
    require_columns(df, [system_col, AR_COL], 'filter_standard_size')

    mask_disco = (
        (df[system_col] == 'Disco(G)-Disco(C)') &
        np.isclose(df[AR_COL].astype(float), 0.1, atol=0.03)
    )
    mask_otros = (
        (df[system_col] != 'Disco(G)-Disco(C)') &
        np.isclose(df[AR_COL].astype(float), target_ar, atol=atol)
    )
    return df[mask_disco | mask_otros].copy()


def select_by_nominal_ar(df: pd.DataFrame, target: float, atol: float = 0.05) -> pd.DataFrame:
    require_columns(df, [AR_COL], 'select_by_nominal_ar')
    return df[np.isclose(df[AR_COL].astype(float), target, atol=atol)].copy()

# =============================================================================
# GRÁFICOS DE FLUJO
# =============================================================================

def plot_puros_vs_orificio(df: pd.DataFrame):
    print("  -> Plotting 1: Pure Systems vs Orifice...")
    df_puros = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco'))].sort_values('D_d_sq')
    if df_puros.empty:
        return

    plt.figure()
    plt.errorbar(
        df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'],
        fmt='o-', color='black', label='Pure Disks', **ERRORBAR_KW
    )
    plt.xlabel(r"Orifice Ratio $(D/d)^2$")
    plt.ylabel(r"$\ln(\langle s \rangle + 1)$")
    plt.legend(title="System")
    save_plot("1-pure-vs-orifice")


def plot_disco_vs_area_ratio(df: pd.DataFrame):
    print("  -> Plotting 2: Disco(G)-Disco(C) vs Area Ratio...")

    df_sys = df[df['sistema'] == 'Disco(G)-Disco(C)'].copy()
    if df_sys.empty:
        return

    main_dd = df_sys['D_d_sq'].value_counts().idxmax()
    df_sys = df_sys[df_sys['D_d_sq'] == main_dd]

    plt.figure()

    val_ref, _ = get_pure_ref(df, 'Disco(G)-Disco(C)', main_dd, 'log_S')
    if val_ref is not None:
        plt.axhline(y=val_ref, **REF_LINE_KW, label=r'$\chi = 0$ (Pure)')

    target_chis = [0.01, 0.1, 0.14, 0.2]
    colors, markers = SEQ_STYLE(len(target_chis))

    for chi, color, marker in zip(target_chis, colors, markers):
        grp = df_sys[np.isclose(df_sys['chi'], chi, atol=0.005)].sort_values(AR_COL)
        if grp.empty:
            continue

        plot_data = (
            grp.groupby(AR_COL, dropna=False)
               .agg(log_S=('log_S', 'mean'), log_S_err=('log_S_err', 'mean'))
               .reset_index()
               .sort_values(AR_COL)
        )

        plt.errorbar(
            plot_data[AR_COL], plot_data['log_S'], yerr=plot_data['log_S_err'],
            fmt=f'{marker}-', color=color, label=rf'$\chi = {chi}$',
            **ERRORBAR_KW,
        )

    plt.xlabel(r"Nominal Area Ratio $R_{\rm a}$")
    plt.ylabel(r"$\ln(\langle s \rangle + 1)$")

    plt.legend(loc='best')

    save_plot("2-discog-discoc-vs-area-ratio")


LOCS_DERECHA = ('lower right', 'center right', 'upper right')


def _puntos_tapados(ax, puntos, loc, titulo, margen_px=10.0):
    """Cuantos puntos (en coordenadas de datos) quedan debajo de la leyenda,
    con un margen en pixeles por el tamano de marcadores y barras de error."""
    leg = ax.legend(loc=loc, title=titulo)
    ax.figure.canvas.draw()
    caja = leg.get_window_extent()
    disp = ax.transData.transform(puntos)
    return int(np.sum((disp[:, 0] >= caja.x0 - margen_px) & (disp[:, 0] <= caja.x1 + margen_px) &
                      (disp[:, 1] >= caja.y0 - margen_px) & (disp[:, 1] <= caja.y1 + margen_px)))


def _puntos_de(curvas, n_seg=30):
    """Puntos de las curvas (R_a, x, y, err): los datos, los extremos de las
    barras de error y puntos intermedios sobre las lineas que los unen."""
    puntos = []
    for _, x, y, err in curvas:
        x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
        e = np.nan_to_num(np.asarray(err, dtype=float), nan=0.0)
        for xi, yi, ei in zip(x, y, e):
            puntos += [(xi, yi), (xi, yi - ei), (xi, yi + ei)]
        t = np.linspace(0.0, 1.0, n_seg)
        for i in range(len(x) - 1):
            puntos += list(zip(x[i] + t * (x[i + 1] - x[i]), y[i] + t * (y[i + 1] - y[i])))
    return np.asarray(puntos, dtype=float)


def margen_para_leyenda(ax, curvas, titulo, paso=0.1, max_extra=1.0):
    """Fraccion del rango de y que hay que agregar arriba para que la leyenda
    entre a la derecha sin tapar curvas (0 si ya entra). No cambia los ejes."""
    puntos = _puntos_de(curvas)
    if any(_puntos_tapados(ax, puntos, loc, titulo) == 0 for loc in LOCS_DERECHA):
        return 0.0
    y0, y1 = ax.get_ylim()
    extra = paso
    while extra <= max_extra:
        ax.set_ylim(y0, y1 + extra * (y1 - y0))
        if _puntos_tapados(ax, puntos, 'upper right', titulo) == 0:
            break
        extra += paso
    ax.set_ylim(y0, y1)
    return min(extra, max_extra)


def leyenda_a_la_derecha(ax, curvas, titulo):
    """Leyenda adentro de los ejes, del lado derecho, en la posicion (abajo,
    centro o arriba) que tapa menos puntos con sus barras de error."""
    puntos = _puntos_de(curvas)
    tapados = {loc: _puntos_tapados(ax, puntos, loc, titulo) for loc in LOCS_DERECHA}
    ax.legend(loc=min(LOCS_DERECHA, key=lambda l: tapados[l]), title=titulo)


def plot_sweeps_by_system(
    df: pd.DataFrame,
    target_systems: List[Tuple[str, str]],
    zoom: bool = False,
    xlim: Tuple[float, float] = (0.05, 0.15),
):
    if zoom:
        print("  -> Plotting 4 zoom: Clogging Curves (chi 0.05 - 0.15)...")
    else:
        print("  -> Plotting 4: Clogging Curves (Sweeps)...")

    # Chis que NO querés mostrar en el gráfico general.
    # La versión zoom sí los conserva.
    excluded_chis_no_zoom = [0.07, 0.075, 0.085, 0.09, 0.095, 0.105, 0.11, 0.15]

    # =========================================================================
    # PRIMERA PASADA: arma las curvas de cada sistema (sin dibujar todavia) y
    # junta, de paso, el rango global de x e y (contemplando barra de error)
    # entre TODOS los sistemas de esta llamada. Con eso, las 4 figuras que
    # salen de una misma llamada (la tanda sin zoom, o la tanda con zoom)
    # quedan con el mismo rango de ejes y son directamente comparables entre
    # si. Las dos llamadas (zoom=False y zoom=True) siguen siendo rangos
    # independientes entre si, a proposito: forzar el mismo rango ancho de la
    # tanda sin zoom sobre la tanda con zoom anularia el propio sentido del
    # zoom.
    # =========================================================================
    datos_por_sistema = {}
    x_all, y_lo_all, y_hi_all = [], [], []

    for system_name, _ in target_systems:
        df_mix = df[(df['sistema'] == system_name) & (df['chi'] > 0.0)].copy()

        if df_mix.empty:
            continue

        # En el gráfico SIN zoom, quitamos los chi intermedios.
        # En el gráfico CON zoom, los dejamos para ver el detalle.
        if not zoom:
            mask_excluded = np.zeros(len(df_mix), dtype=bool)
            for chi_excl in excluded_chis_no_zoom:
                mask_excluded |= np.isclose(df_mix['chi'].astype(float), chi_excl, atol=1e-6)

            df_mix = df_mix[~mask_excluded].copy()

        if df_mix.empty:
            continue

        main_dd = df_mix['D_d_sq'].value_counts().idxmax()
        p0, e0 = get_pure_ref(df, system_name, main_dd, 'log_S')

        if p0 is None:
            continue

        # R_a = 0.5 no se incluye: solo existe para Disco-Disco y no se puede
        # comparar entre sistemas.
        targets = [0.1, 0.2, 0.4]
        curvas = []

        for target in targets:
            grp_raw = select_by_nominal_ar(df_mix, target, atol=0.06)

            if grp_raw.empty:
                continue

            available = np.sort(grp_raw[AR_COL].dropna().unique())
            chosen = available[np.argmin(np.abs(available - target))]
            grp_raw = grp_raw[np.isclose(grp_raw[AR_COL], chosen, atol=1e-12)]

            grp = (
                grp_raw.groupby('chi')
                       .agg(log_S=('log_S', 'mean'), log_S_err=('log_S_err', 'mean'))
                       .reset_index()
                       .sort_values('chi')
            )

            if grp.empty:
                continue

            x = [0.0] + grp['chi'].tolist()
            y = [p0] + grp['log_S'].tolist()
            err = [e0] + grp['log_S_err'].tolist()
            curvas.append((chosen, x, y, err))

            print(f"\nSistema: {system_name}\n  R_a {target} -> {AR_COL} real {chosen:.4f}")

            x_all.extend(x)
            y_arr = np.asarray(y, dtype=float)
            err_arr = np.nan_to_num(np.asarray(err, dtype=float), nan=0.0)
            y_lo_all.extend((y_arr - err_arr).tolist())
            y_hi_all.extend((y_arr + err_arr).tolist())

        if curvas:
            datos_por_sistema[system_name] = curvas

    if not datos_por_sistema:
        return

    # Rango de x compartido: en la version zoom se respeta el xlim explicito
    # que ya pasa el caller (es la razon de ser del zoom); en la version sin
    # zoom se calcula de los datos, con un margen del 5%.
    if zoom:
        x_range = xlim
    else:
        x_min, x_max = min(x_all), max(x_all)
        pad_x = (x_max - x_min) * 0.05 if x_max > x_min else 0.02
        x_range = (x_min - pad_x, x_max + pad_x)

    # Rango de y compartido, con margen del 8% incluyendo las barras de error.
    y_min, y_max = min(y_lo_all), max(y_hi_all)
    pad_y = (y_max - y_min) * 0.08 if y_max > y_min else 0.1
    y_range = (y_min - pad_y, y_max + pad_y)

    # =========================================================================
    # SEGUNDA PASADA: una figura por sistema, todas con el mismo x_range/y_range.
    # =========================================================================
    figuras = []
    for system_name, _ in target_systems:
        if system_name not in datos_por_sistema:
            continue
        system_id = system_name.lower().replace('(', '').replace(')', '').replace('_', '-').replace(' ', '-')

        fig = plt.figure()
        ax = plt.gca()
        curvas = datos_por_sistema[system_name]
        colors, markers = SEQ_STYLE(len(curvas))
        for (chosen, x, y, err), color, marker in zip(curvas, colors, markers):
            plt.errorbar(x, y, yerr=err, fmt=f'{marker}-', color=color,
                         label=rf"$R_{{\rm a}} = {chosen:.3g}$", **ERRORBAR_KW)

        plt.xlabel(r"Concentration $\chi$")
        plt.ylabel(r"$\ln(\langle s \rangle + 1)$")
        plt.xlim(*x_range)
        plt.ylim(*y_range)
        titulo = CFG.english_labels.get(system_name, system_name)
        nombre = (f"4-{system_id}-clogging-curves-zoom-chi-0p05-0p15" if zoom
                  else f"4-{system_id}-clogging-curves")
        figuras.append((fig, ax, curvas, titulo, nombre))

    # Cartel con el sistema (ej. "Triangle-Disk") como titulo de la leyenda,
    # adentro y a la derecha sin tapar curvas. Si en alguna figura no entra,
    # se agrega el mismo margen arriba en TODAS (siguen con el mismo eje y).
    extra = max(margen_para_leyenda(ax, curvas, titulo) for _, ax, curvas, titulo, _ in figuras)
    for fig, ax, curvas, titulo, nombre in figuras:
        if extra > 0:
            ax.set_ylim(y_range[0], y_range[1] + extra * (y_range[1] - y_range[0]))
        leyenda_a_la_derecha(ax, curvas, titulo)
        plt.figure(fig.number)
        save_plot(nombre)


def main():
    print("[+] Starting integrated PDF pipeline...")

    aplicar_estilo(verbose=True)

    os.makedirs(CFG.out_dir, exist_ok=True)

    df = pd.read_csv(CFG.data_path)
    df = prepare_flow_stats(df)

    # Limpieza: sistema fuera del estudio actual.
    df = df[df['sistema'] != 'Cuad(G)-Cuad(C)']

    # Orden de los sistemas: Triangle, Square, Pentagon y Disk-Disk al final.
    sistemas_meta = [
        ('Tri(G)-Disco(C)', 'Triangle'),
        ('Cuad(G)-Disco(C)', 'Square'),
        ('Pent(G)-Disco(C)', 'Pentagon'),
        ('Disco(G)-Disco(C)', 'Disk'),
    ]

    # Flujo / avalanchas
    # plot_puros_vs_orificio(df)
    plot_disco_vs_area_ratio(df)
    plot_sweeps_by_system(df, sistemas_meta)
    plot_sweeps_by_system(df, sistemas_meta, zoom=True, xlim=(0.05, 0.15))
    plot_geometric_effects(df)
    plot_geometric_effects_raw(df)
    plot_geometric_effects_linear(df)

    # Arcos
    plot_arch_analysis(df)
    plot_arch_geometry_deep_dive(df)
    plot_arch_evolution_vs_chi(df)

    print("\n[+] Pipeline finished.")
    print(f"[+] All plots generated successfully in: {CFG.out_dir}")


if __name__ == "__main__":
    main()