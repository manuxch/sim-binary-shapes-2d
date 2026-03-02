import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
import re

# --- CONFIGURACIÓN ---
AV_PATH = "../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
IDX_PATH = "../master_sim_index.csv"
OUTPUT_DIR = "../processed_data//3_tail_distributions"

def get_detailed_system_name(row):
    """Analiza el JSON de granos para bautizar la mezcla con precisión."""
    try:
        grains = json.loads(row['grain_json'])
        grains_sorted = sorted(grains, key=lambda x: x['radius'], reverse=True)
        
        big = grains_sorted[0]
        small = grains_sorted[1] if len(grains_sorted) > 1 else None
        
        nombres = {1: "Disco", 3: "Triangulo", 4: "Cuadrado", 5: "Pentagono"}
        name_big = nombres.get(big['sides'], f"Polig({big['sides']})")
        
        if small:
            name_small = nombres.get(small['sides'], f"Polig({small['sides']})")
            return f"{name_big} (G) - {name_small} (C)"
        else:
            return f"{name_big} puro"
    except:
        return "Desconocido"

def main(av_path=AV_PATH, idx_path=IDX_PATH, output_dir=OUTPUT_DIR):
    """
    Crea gráficos de colas de distribución SEPARADOS por tipo de mezcla.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        # 1. Cargar datos
        df_av = pd.read_csv(av_path)
        df_idx = pd.read_csv(idx_path)
        
        # 2. Identificación precisa del sistema
        # Aplicamos la lógica de nombres a cada fila del indexador
        df_idx['sistema_detallado'] = df_idx.apply(get_detailed_system_name, axis=1)
        
        # Extraer Chi (tu lógica de regex original)
        def extract_chi(path):
            match = re.search(r"Chi_(\d+p\d+)_", str(path))
            return float(match.group(1).replace('p', '.')) if match else 0.0
        df_idx['chi'] = df_idx['path'].apply(extract_chi)

        # 3. Unir datos
        df = pd.merge(df_av, df_idx[['sim_hash', 'chi', 'sistema_detallado']], on='sim_hash')

        # 4. Generar un gráfico por cada tipo de sistema encontrado
        sistemas_unicos = df['sistema_detallado'].unique()
        
        print(f"--- Sistemas detectados: {sistemas_unicos} ---")

        for sistema in sistemas_unicos:
            print(f"Graficando sistema: {sistema}...")
            
            # Filtramos para que este gráfico sea PURO
            df_plot = df[df['sistema_detallado'] == sistema]
            
            # Ordenamos Chi para que la leyenda sea coherente
            df_plot = df_plot.sort_values('chi')

            plt.figure(figsize=(10, 6))
            
            # Graficamos la distribución de colas
            sns.kdeplot(data=df_plot, 
                        x='tamano_big', 
                        hue='chi', 
                        log_scale=True, 
                        common_norm=False, 
                        palette='viridis',
                        linewidth=2)

            plt.title(f'Distribución de Avalanchas: {sistema}', fontsize=14)
            plt.xlabel('Tamaño de Avalancha de Partículas Grandes ($S_{big}$)', fontsize=12)
            plt.ylabel('Densidad de Probabilidad $P(S)$', fontsize=12)
            plt.grid(True, which="both", ls="-", alpha=0.15)
            
            # Guardado con nombre descriptivo
            file_name = sistema.replace(" ", "_").replace("(", "").replace(")", "")
            save_path = os.path.join(output_dir, f"tail_{file_name}.png")
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

        print(f"\n--- PROCESO EXITOSO ---")
        print(f"Se generaron {len(sistemas_unicos)} gráficos en la carpeta '{output_dir}'.")

    except Exception as e:
        print(f"Error crítico en tail_distribution: {e}")

if __name__ == "__main__":
    main()