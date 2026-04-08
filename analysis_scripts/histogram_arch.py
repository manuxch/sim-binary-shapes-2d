import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import matplotlib

matplotlib.use('Agg') # Para ejecución en servidor/headless

# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================
MEGA_DATASET_PATH = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv"
OUTPUT_DIR = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/4_arch_histograms"

def plot_arch_histograms(dataset_path=MEGA_DATASET_PATH, output_dir=OUTPUT_DIR):
    print(f"\n[+] Generando análisis avanzado de composición de arcos (Multivariable)...")
    
    if not os.path.exists(dataset_path):
        print(f"  -> [!] Error: No se encontró el dataset en {dataset_path}")
        return

    # 1. Cargar datos (Usamos los nombres de columna del nuevo consolidator)
    df = pd.read_csv(dataset_path)
    
    # Verificación de columnas (Senior safety check)
    required_cols = ['system_type', 'chi', 'r_ratio', 'Particulas_Tipo_1', 'Total_Particulas_Arco']
    if not all(col in df.columns for col in required_cols):
        print(f"  -> [!] Error: El CSV no tiene las columnas necesarias: {required_cols}")
        return

    df = df[df['Total_Particulas_Arco'] > 0].copy()
    df['Fraccion_Tipo_1'] = df['Particulas_Tipo_1'] / df['Total_Particulas_Arco']

    # 2. Organización de carpetas
    os.makedirs(output_dir, exist_ok=True)

    # 3. Análisis por Sistema, Chi y Ratio (El corazón del cambio)
    # Agrupamos por las 3 variables para no mezclar datos de distintos radios
    grouped = df.groupby(['system_type', 'chi', 'r_ratio'])
    graficos_generados = 0

    for (sistema, chi, ratio), df_plot in grouped:
        sis_safe = sistema.replace(" ", "_").replace("(", "").replace(")", "")
        chi_safe = str(chi).replace(".", "p")
        rat_safe = str(ratio).replace(".", "p")
        
        # Creamos subcarpeta por sistema para no tener miles de archivos juntos
        subfolder = os.path.join(output_dir, sis_safe)
        os.makedirs(subfolder, exist_ok=True)

        # --- GRÁFICO 1: Histograma de Composición (Conteo Absoluto) ---
        plt.figure(figsize=(10, 6))
        bins = np.arange(0, df_plot['Total_Particulas_Arco'].max() + 2) - 0.5
        
        plt.hist(df_plot['Particulas_Tipo_0'], bins=bins, alpha=0.5, label='Grandes (Matriz)', color='#1f77b4')
        plt.hist(df_plot['Particulas_Tipo_1'], bins=bins, alpha=0.7, label='Chicas (Aditivo)', color='#ff7f0e')
        
        plt.title(f"Composición de Arcos: {sistema}\n$\\chi$={chi} | Ratio={ratio}", fontsize=13)
        plt.xlabel("Cantidad de partículas en el arco")
        plt.ylabel("Frecuencia")
        plt.xticks(np.arange(0, df_plot['Total_Particulas_Arco'].max() + 1))
        plt.legend()
        plt.grid(axis='y', linestyle='--', alpha=0.4)
        
        plt.savefig(os.path.join(subfolder, f"hist_{chi_safe}_R{rat_safe}.png"), dpi=200)
        plt.close()

        # --- GRÁFICO 2: Fracción vs Tamaño del Arco ---
        plt.figure(figsize=(9, 5))
        sns.boxplot(data=df_plot, x='Total_Particulas_Arco', y='Fraccion_Tipo_1', color='lightgrey', showfliers=False)
        sns.stripplot(data=df_plot, x='Total_Particulas_Arco', y='Fraccion_Tipo_1', alpha=0.3, jitter=True)
        
        plt.axhline(chi, color='red', linestyle='--', label=fr'Nominal $\chi$={chi}')
        plt.title(f"Fracción de Aditivos por Tamaño de Arco\n{sistema} | Ratio={ratio}")
        plt.ylim(-0.05, 1.05)
        plt.legend()
        
        plt.savefig(os.path.join(subfolder, f"fraccion_{chi_safe}_R{rat_safe}.png"), dpi=200)
        plt.close()
        
        graficos_generados += 2

    # 4. GRÁFICO DE TENDENCIAS (Barrido de Radios a Chi Fijo)
    # Este es el gráfico que pediste específicamente
    print("  -> Generando comparativa de barrido de radios...")
    for (sistema, chi), df_trend in df.groupby(['system_type', 'chi']):
        plt.figure(figsize=(10, 6))
        
        # Calculamos la media de fracción para cada ratio de tamaño
        stats = df_trend.groupby('r_ratio')['Fraccion_Tipo_1'].agg(['mean', 'std']).reset_index()
        
        plt.errorbar(stats['r_ratio'], stats['mean'], yerr=stats['std'], fmt='o-', capsize=5, label='Composición Media')
        plt.axhline(chi, color='red', linestyle=':', label=fr'Mezcla Nominal ($\chi$={chi})')
        
        plt.title(f"Composición de Arcos vs Tamaño de Aditivo\n{sistema} | $\\chi$ fijo = {chi}")
        plt.xlabel("Ratio de Radios ($R_{large}/R_{small}$)")
        plt.ylabel("Fracción de Aditivos en Arcos")
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        plt.savefig(os.path.join(output_dir, f"tendencia_radio_{sistema}_{str(chi).replace('.','p')}.png"))
        plt.close()

    print(f"  -> ¡Éxito! Se generaron {graficos_generados} gráficos individuales y comparativas de tendencia.")

if __name__ == "__main__":
    plot_arch_histograms()