import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # backend sin display; evita fallos silenciosos de
                        # plt.figure()/savefig() bajo multiprocessing en
                        # entornos headless (server/cluster sin X11).
import matplotlib.pyplot as plt
import os
import json
from multiprocessing import Pool, cpu_count
from collections import Counter

# --- CONFIGURACIÓN ---
INDEX_FILE = "/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
WINDOW_SIZE = 10.0  # Tamaño del batch en segundos
CPU_CORES = cpu_count()


def analizar_flujo_temporal(row):
    """
    Devuelve un dict con 'status' explicando el resultado (ok, o el
    motivo exacto de por qué no se generó gráfico para esta fila).
    """
    path = row['path']
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
        # comparar en el tiempo, se omite. Cambiar a 'pass' acá si de
        # todos modos querés una línea plana en chi_nominal (0.0 o 1.0).
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
        plt.figure(figsize=(10, 5))
        plt.plot(df_plot['tiempo'], df_plot['chi_eff'], marker='o', color='#2980b9',
                 linestyle='-', linewidth=1.2, markersize=4, label=r'$\chi_{salida}$ (Batch 10s)')

        plt.axhline(y=chi_nominal, color='#e74c3c', linestyle='--', linewidth=2,
                    alpha=0.8, label=f'Nominal Objetivo: {chi_nominal:.3f}')

        last_row = df_plot.iloc[-1]
        t_final, chi_final = last_row['tiempo'], last_row['chi_eff']
        plt.plot([t_final, t_final], [chi_final, chi_nominal], color='#27ae60', linestyle=':', linewidth=2.5)

        if chi_nominal > 0:
            diff_pct = (chi_nominal - chi_final) / chi_nominal * 100
            plt.text(t_final + 1, (chi_final + chi_nominal) / 2,
                     f"Diferencia porcentual:\n{diff_pct:.1f}%",
                     color='#27ae60', fontweight='bold', fontsize=9,
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        plt.title(f"Dinámica de Descarga | Hash: {sim_hash} | T{tirada}\nMezcla: {row.get('system_type', 'Desconocido')}", fontsize=12)
        plt.xlabel("Tiempo de Simulación (s)", fontsize=10)
        plt.ylabel(r"Concentración de Salida ($\chi_{area}$)", fontsize=10)
        plt.ylim(0, min(1.0, max(chi_nominal * 2.5, df_plot['chi_eff'].max() * 1.3, 0.05)))
        plt.legend(loc='upper right', frameon=True, shadow=True)
        plt.tight_layout()

        graph_name = f"dinamica_flujo_final_{sim_hash}_T{tirada}.svg"
        plt.savefig(os.path.join(path, graph_name), format='svg')
        plt.close()
    except Exception as e:
        return {**base, 'status': 'error_al_graficar', 'detail': str(e)}

    return {**base, 'status': 'ok'}


def main():
    if not os.path.exists(INDEX_FILE):
        print(f"Error: No se encontró {INDEX_FILE} para chi_temporal.")
        return

    df_idx = pd.read_csv(INDEX_FILE)
    print(f"Analizando flujos temporales (Chi) sobre {len(df_idx)} filas...")

    tasks = [row for _, row in df_idx.iterrows()]
    with Pool(CPU_CORES) as p:
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