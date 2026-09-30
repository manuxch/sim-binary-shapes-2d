import argparse
import json
import os
from collections import Counter
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # backend sin display; evita fallos silenciosos de
                        # plt.figure()/savefig() bajo multiprocessing en
                        # entornos headless (server/cluster sin X11).
import matplotlib.pyplot as plt

# =============================================================================
# ESTILO -- el mismo de graficos_finales.py
# =============================================================================
# Colores y marcadores por sistema (paleta Wong), nombres en ingles para las
# leyendas, y tamaños de fuente de set_plot_fonts(). Copiados tal cual de
# AnalysisConfig / SYSTEM_NAME_MAP de graficos_finales.py: si se cambian
# alla, cambiarlos tambien aca.

SYSTEM_STYLE = {
    'Disco(G)-Disco(C)': ('#000000', 'o'),
    'Disco(G)-Tri(C)':   ('#E69F00', '^'),
    'Disco(G)-Cuad(C)':  ('#D55E00', 's'),
    'Disco(G)-Pent(C)':  ('#CC79A7', 'p'),
    'Tri(G)-Disco(C)':   ('#009E73', '^'),
    'Cuad(G)-Disco(C)':  ('#56B4E9', 's'),
    'Pent(G)-Disco(C)':  ('#0072B2', 'p'),
}

ENGLISH_LABELS = {
    'Disco(G)-Disco(C)': 'Disk-Disk',
    'Disco(G)-Tri(C)':   'Disk-Triangle',
    'Disco(G)-Cuad(C)':  'Disk-Square',
    'Disco(G)-Pent(C)':  'Disk-Pentagon',
    'Tri(G)-Disco(C)':   'Triangle-Disk',
    'Cuad(G)-Disco(C)':  'Square-Disk',
    'Pent(G)-Disco(C)':  'Pentagon-Disk',
}

SYSTEM_NAME_MAP = {
    'Disco-Disco': 'Disco(G)-Disco(C)',
    'Disco-Tri':   'Disco(G)-Tri(C)',
    'Disco-Cuad':  'Disco(G)-Cuad(C)',
    'Disco-Pent':  'Disco(G)-Pent(C)',
    'Tri-Disco':   'Tri(G)-Disco(C)',
    'Cuad-Disco':  'Cuad(G)-Disco(C)',
    'Pent-Disco':  'Pent(G)-Disco(C)',
}


def set_plot_fonts(labels: int = 20, ticks: int = 16, legend: int = 14):
    plt.rcParams.update({
        'axes.labelsize': labels,
        'xtick.labelsize': ticks,
        'ytick.labelsize': ticks,
        'legend.fontsize': legend,
        'text.usetex': False,
        'mathtext.fontset': 'stix',
        'font.family': 'STIXGeneral',
    })


# a nivel de modulo, asi los procesos del Pool tambien lo tienen
set_plot_fonts()

# =============================================================================
# CONFIGURACIÓN (valores por defecto; se cambian por argumentos)
# =============================================================================
INDEX_FILE = "/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
WINDOW_SIZE = 10.0   # tamaño del batch en segundos
CPU_CORES = cpu_count()
FORMATO = 'pdf'      # igual que save_plot() de graficos_finales.py
# Reemplazo de prefijo en la columna 'path' del index (ej. el index tiene
# /home/juli/work/... pero en esta PC el disco esta en /mnt/h/work/...).
PREFIJO_VIEJO = None
PREFIJO_NUEVO = None


def estilo_sistema(system_type):
    """(color, marcador, etiqueta en ingles) del sistema, como en graficos_finales.py."""
    sistema = SYSTEM_NAME_MAP.get(str(system_type), str(system_type))
    color, marker = SYSTEM_STYLE.get(sistema, ('black', 'o'))
    return color, marker, ENGLISH_LABELS.get(sistema, str(system_type))


def analizar_flujo_temporal(row):
    """
    Devuelve un dict con 'status' explicando el resultado (ok, o el
    motivo exacto de por qué no se generó gráfico para esta fila).
    """
    path = row['path']
    if PREFIJO_VIEJO and str(path).startswith(PREFIJO_VIEJO):
        path = PREFIJO_NUEVO + str(path)[len(PREFIJO_VIEJO):]
    flux_filename = row['fluxFile']
    sim_hash = row['sim_hash']
    tirada = row['tirada']
    base = {'sim_hash': sim_hash, 'tirada': tirada, 'path': path}

    if not os.path.isdir(path):
        return {**base, 'status': 'dir_no_existe'}

    try:
        grain_info = json.loads(row['grain_json'])
    except Exception as e:
        return {**base, 'status': 'json_invalido', 'detail': str(e)}

    # chi_nominal viene DIRECTO del index (columna 'chi'), no se recalcula
    # desde grain_json. grain_json solo trae radius/sides, nunca tuvo
    # counts de población -- por eso el KeyError('count') anterior.
    # 'chi' ya es la concentración objetivo del diseño experimental
    # (confirmado: a r_ratio_nominal fijo, 'chi' es la variable barrida).
    chi_nominal = row['chi']

    if len(grain_info) < 2:
        # Sistema monodisperso (sin aditivo): no hay dos poblaciones que
        # comparar en el tiempo, se omite.
        return {**base, 'status': 'monodisperso_omitido'}

    radios = [g['radius'] for g in grain_info]
    areas_unitarias = {i: np.pi * (g['radius'] ** 2) for i, g in enumerate(grain_info)}
    tipo_chica = int(np.argmin(radios))

    flux_path = os.path.join(path, flux_filename)
    if not os.path.exists(flux_path):
        return {**base, 'status': 'flux_no_existe', 'detail': flux_path}

    try:
        df_flux = pd.read_csv(flux_path, sep=r'\s+', comment='#', header=None, usecols=[1, 2])
    except Exception as e:
        return {**base, 'status': 'error_lectura_flux', 'detail': str(e)}

    if df_flux.empty:
        return {**base, 'status': 'flux_vacio'}
    df_flux.columns = ['tipo', 'tiempo']

    # Chequeo de consistencia: los 'tipo' de flx.dat deben ser subset de
    # los índices 0..N-1 derivados de grain_json.
    tipos_en_flux = set(df_flux['tipo'].unique())
    tipos_esperados = set(areas_unitarias.keys())
    if not tipos_en_flux.issubset(tipos_esperados):
        return {**base, 'status': 'tipo_mismatch',
                'detail': f'flux tiene {sorted(tipos_en_flux)}, se esperaba subset de {sorted(tipos_esperados)}'}

    t_start = df_flux['tiempo'].min()
    t_end = df_flux['tiempo'].max()
    bins = np.arange(t_start, t_end + WINDOW_SIZE, WINDOW_SIZE)
    if len(bins) < 2:
        return {**base, 'status': 'pocos_bins', 'detail': f't_start={t_start}, t_end={t_end}'}

    df_flux['batch'] = pd.cut(df_flux['tiempo'], bins=bins, labels=bins[:-1])

    batch_results = []
    for label, group in df_flux.groupby('batch', observed=True):
        counts = group['tipo'].value_counts()
        a_chicas_out = counts.get(tipo_chica, 0) * areas_unitarias[tipo_chica]
        a_total_out = sum(counts.get(t, 0) * areas_unitarias[t] for t in areas_unitarias.keys())
        if a_total_out > 0:
            batch_results.append({'tiempo': float(label) + WINDOW_SIZE / 2,
                                  'chi_eff': a_chicas_out / a_total_out})

    df_plot = pd.DataFrame(batch_results)
    if df_plot.empty:
        return {**base, 'status': 'sin_batches_validos'}

    try:
        color, marker, label_en = estilo_sistema(row.get('system_type', ''))

        plt.figure()
        # referencia: linea negra discontinua, como el chi = 0 de graficos_finales.py
        plt.axhline(y=chi_nominal, color='black', linestyle='--',
                    label=rf'Nominal $\chi = {chi_nominal:.3g}$', zorder=1)
        plt.plot(df_plot['tiempo'], df_plot['chi_eff'], f'{marker}-', color=color,
                 label=rf'$\chi_{{out}}$ ({WINDOW_SIZE:g} s windows)', zorder=2)

        # diferencia relativa entre el ultimo batch y el valor nominal
        last_row = df_plot.iloc[-1]
        t_final, chi_final = last_row['tiempo'], last_row['chi_eff']
        plt.plot([t_final, t_final], [chi_final, chi_nominal], color='gray', linestyle=':',
                 linewidth=1.5, zorder=1)
        if chi_nominal > 0:
            diff_pct = (chi_nominal - chi_final) / chi_nominal * 100
            plt.annotate(f"{diff_pct:.1f}%", xy=(t_final, (chi_final + chi_nominal) / 2),
                         xytext=(6, 0), textcoords='offset points', va='center',
                         color='gray', fontsize=14)

        plt.xlabel(r"Simulation Time (s)")
        plt.ylabel(r"Outflow Concentration $\chi_{out}$")
        plt.ylim(0, min(1.0, max(chi_nominal * 2.5, df_plot['chi_eff'].max() * 1.3, 0.05)))
        plt.legend(title=f"{label_en}, run {tirada}", title_fontsize=14, loc='upper right')

        graph_name = f"dinamica_flujo_final_{sim_hash}_T{tirada}.{FORMATO}"
        plt.savefig(os.path.join(path, graph_name), bbox_inches='tight')
        plt.close()
    except Exception as e:
        plt.close('all')
        return {**base, 'status': 'error_al_graficar', 'detail': str(e)}

    return {**base, 'status': 'ok'}


def _inicializar_worker(viejo, nuevo, ventana, formato):
    # los workers no heredan lo que main() cambia despues de importar el
    # modulo (con 'spawn' seguro, con 'fork' depende): se pasa explicito
    global PREFIJO_VIEJO, PREFIJO_NUEVO, WINDOW_SIZE, FORMATO
    PREFIJO_VIEJO, PREFIJO_NUEVO, WINDOW_SIZE, FORMATO = viejo, nuevo, ventana, formato


def main():
    parser = argparse.ArgumentParser(
        description="Grafica chi de salida en funcion del tiempo para cada simulacion del index.")
    parser.add_argument('--index', default=INDEX_FILE, help='master_sim_index.csv')
    parser.add_argument('--ventana', type=float, default=WINDOW_SIZE,
                        help='tamaño de la ventana temporal en segundos (default 10)')
    parser.add_argument('--formato', choices=['pdf', 'svg', 'png'], default=FORMATO,
                        help='formato de salida (default pdf, como graficos_finales.py)')
    parser.add_argument('--prefijo_viejo', default=None,
                        help="prefijo de las rutas del index a reemplazar (ej. /home/juli/work)")
    parser.add_argument('--prefijo_nuevo', default=None,
                        help="prefijo nuevo (ej. /mnt/h/work)")
    parser.add_argument('--workers', type=int, default=CPU_CORES)
    args = parser.parse_args()
    if (args.prefijo_viejo is None) != (args.prefijo_nuevo is None):
        raise SystemExit("--prefijo_viejo y --prefijo_nuevo van juntos.")

    if not os.path.exists(args.index):
        print(f"Error: No se encontró {args.index} para chi_temporal.")
        return

    df_idx = pd.read_csv(args.index)
    print(f"Analizando flujos temporales (Chi) sobre {len(df_idx)} filas...")

    tasks = [row for _, row in df_idx.iterrows()]
    with Pool(args.workers, initializer=_inicializar_worker,
              initargs=(args.prefijo_viejo, args.prefijo_nuevo, args.ventana, args.formato)) as p:
        resultados = p.map(analizar_flujo_temporal, tasks)

    conteo = Counter(r['status'] for r in resultados)
    print("\n--- Resumen por motivo ---")
    for status, n in conteo.most_common():
        print(f"  {status}: {n}")

    print("\n--- Ejemplos por motivo de fallo (hasta 3 c/u) ---")
    for status in conteo:
        if status == 'ok':
            continue
        ejemplos = [r for r in resultados if r['status'] == status][:3]
        print(f"\n[{status}]")
        for e in ejemplos:
            print(f"  sim_hash={e['sim_hash']} tirada={e['tirada']} detail={e.get('detail', '')}")

    print(f"\n✅ Proceso terminado. {conteo.get('ok', 0)} gráficos generados de {len(df_idx)} filas.")


if __name__ == "__main__":
    main()