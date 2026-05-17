import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

AV_PATH = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
IDX_PATH = "/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
OUTPUT_DIR = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/3_tail_distributions"


def ensure_nominal_columns(df):
    if 'area_ratio_nominal' not in df.columns and 'area_ratio' in df.columns:
        df['area_ratio_nominal'] = df['area_ratio'].round(3)
    if 'r_ratio_nominal' not in df.columns and 'r_ratio' in df.columns:
        df['r_ratio_nominal'] = df['r_ratio'].round(2)
    return df


def main(av_path=AV_PATH, idx_path=IDX_PATH, output_dir=OUTPUT_DIR, fixed_chi=None):
    os.makedirs(output_dir, exist_ok=True)

    try:
        df_av = pd.read_csv(av_path)
        df_idx = pd.read_csv(idx_path)
        df_idx = ensure_nominal_columns(df_idx)

        cols_idx = [
            'sim_hash',
            'chi',
            'system_type',
            'r_ratio',
            'r_ratio_nominal',
            'area_ratio',
            'area_ratio_nominal',
        ]
        cols_idx = [c for c in cols_idx if c in df_idx.columns]

        df = pd.merge(df_av, df_idx[cols_idx], on='sim_hash', how='left')

        if fixed_chi is not None:
            df = df[df['chi'] == fixed_chi]
            print(f"--- Analizando colas para chi fijo: {fixed_chi} ---")

        for sistema in df['system_type'].dropna().unique():
            print(f"Procesando colas del sistema: {sistema}...")
            df_sis = df[df['system_type'] == sistema].copy()

            df_sis['label'] = df_sis.apply(
                lambda r: fr"$\chi$={r['chi']} | AR={r['area_ratio_nominal']}",
                axis=1,
            )
            df_sis = df_sis.sort_values(['chi', 'area_ratio_nominal'])

            plt.figure(figsize=(10, 6))
            sns.kdeplot(
                data=df_sis,
                x='tamano_big',
                hue='label',
                log_scale=True,
                common_norm=False,
                palette='magma',
                linewidth=2.5,
                alpha=0.8,
            )

            titulo = f'Distribución de Avalanchas: {sistema}'
            if fixed_chi:
                titulo += fr' ($\chi$={fixed_chi})'

            plt.title(titulo, fontsize=14, pad=15)
            plt.xlabel('Tamaño de Avalancha ($S_{big}$)', fontsize=12)
            plt.ylabel('Densidad de Probabilidad $P(S)$', fontsize=12)
            plt.grid(True, which="both", ls="-", alpha=0.15)

            sys_safe = str(sistema).replace(" ", "_").replace("-", "_")
            suffix = f"_chi{str(fixed_chi).replace('.', 'p')}" if fixed_chi else ""
            save_path = os.path.join(output_dir, f"tail_{sys_safe}{suffix}.png")
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

        print(f"\n--- ÉXITO: gráficos generados en '{output_dir}' ---")

    except Exception as e:
        print(f"Error crítico en tail_distribution: {e}")


if __name__ == "__main__":
    main()
