import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

# --- CONFIGURACIÓN ---
AV_PATH = "../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
IDX_PATH = "../master_sim_index.csv"
OUTPUT_DIR = "../processed_data/3_tail_distributions"

def main(av_path=AV_PATH, idx_path=IDX_PATH, output_dir=OUTPUT_DIR, fixed_chi=None):
    """
    Genera gráficos de colas de distribución comparando concentraciones y tamaños de aditivo.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        # 1. Cargar datos
        df_av = pd.read_csv(av_path)
        df_idx = pd.read_csv(idx_path)
        
        # 2. Unir datos usando la "Fuente de Verdad" del Indexer
        # Traemos las columnas físicas ya procesadas
        cols_idx = ['sim_hash', 'chi', 'system_type', 'r_ratio']
        df = pd.merge(df_av, df_idx[cols_idx], on='sim_hash')

        # 3. Opcional: Filtrar por un chi específico (Barrido de Tamaños)
        if fixed_chi is not None:
            df = df[df['chi'] == fixed_chi]
            print(f"--- Analizando colas para chi fijo: {fixed_chi} ---")

        # 4. Generar un gráfico por cada tipo de sistema (Ej: Disco-Cuad)
        sistemas_unicos = df['system_type'].unique()
        
        for sistema in sistemas_unicos:
            print(f"Procesando colas del sistema: {sistema}...")
            df_sis = df[df['system_type'] == sistema].copy()
            
            # --- MEJORA SENIOR: Etiqueta Combinada ---
            # Si el chi es el mismo, la leyenda mostrará el Ratio. Si no, mostrará ambos.
            df_sis['label'] = df_sis.apply(
                lambda r: f"$\chi$={r['chi']} | R={r['r_ratio']}", axis=1
            )
            
            # Ordenamos para que la escala de colores (palette) sea lógica
            df_sis = df_sis.sort_values(['chi', 'r_ratio'])

            plt.figure(figsize=(10, 6))
            
            # Graficamos la distribución de colas (KDE en escala logarítmica)
            sns.kdeplot(data=df_sis, 
                        x='tamano_big', 
                        hue='label', 
                        log_scale=True, 
                        common_norm=False, 
                        palette='magma',
                        linewidth=2.5,
                        alpha=0.8)

            titulo = f'Distribución de Avalanchas: {sistema}'
            if fixed_chi: titulo += f' ($\chi$={fixed_chi})'
            
            plt.title(titulo, fontsize=14, pad=15)
            plt.xlabel('Tamaño de Avalancha ($S_{big}$)', fontsize=12)
            plt.ylabel('Densidad de Probabilidad $P(S)$', fontsize=12)
            plt.grid(True, which="both", ls="-", alpha=0.15)
            
            # Guardado profesional
            sys_safe = sistema.replace(" ", "_").replace("-", "_")
            suffix = f"_chi{str(fixed_chi).replace('.','p')}" if fixed_chi else ""
            save_path = os.path.join(output_dir, f"tail_{sys_safe}{suffix}.png")
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

        print(f"\n--- ÉXITO: {len(sistemas_unicos)} gráficos generados en '{output_dir}' ---")

    except Exception as e:
        print(f"Error crítico en tail_distribution: {e}")

if __name__ == "__main__":
    # Caso 1: Ver todo el panorama (varios chi, varios radios)
    main()
    
    # Caso 2: Ver solo el efecto del tamaño para un chi de 0.1 (Descomenta para usar)
    # main(fixed_chi=0.1)