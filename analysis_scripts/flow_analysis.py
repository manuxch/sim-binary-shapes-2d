import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
import os
import json

def get_detailed_system_name(row):
    """Identifica el sistema: Disco, Triangulo, Cuadrado, Pentagono, etc."""
    try:
        grains = json.loads(row['grain_json'])
        grains_sorted = sorted(grains, key=lambda x: x['radius'], reverse=True)
        big, small = grains_sorted[0], grains_sorted[1]
        
        nombres = {1: "Disco", 3: "Triangulo", 4: "Cuadrado", 5: "Pentagono"}
        
        n1 = nombres.get(big['sides'], f"Polig({big['sides']})")
        n2 = nombres.get(small['sides'], f"Polig({small['sides']})")
        
        return f"{n1}(G)-{n2}(C)"
    except: 
        return "Otros"

def main(av_path="../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv", idx_path="../master_sim_index.csv"):
    # Carga de datos
    df_av = pd.read_csv(av_path)
    df_idx = pd.read_csv(idx_path)
    
    # Bautismo detallado
    df_idx['sistema'] = df_idx.apply(get_detailed_system_name, axis=1)
    
    def extract_chi(path):
        match = re.search(r"Chi_(\d+p\d+)_", str(path))
        return float(match.group(1).replace('p', '.')) if match else 0.0
        
    df_idx['chi'] = df_idx['path'].apply(extract_chi)

    # Merge de datos
    df = pd.merge(df_av, df_idx[['sim_hash', 'chi', 'sistema']], on='sim_hash')

    # --- PROCESAMIENTO Y GUARDADO DE CSV ---
    # Agrupamos por SISTEMA y por CHI, pidiendo media, SEM y conteo de avalanchas
    stats = df.groupby(['sistema', 'chi']).agg(
        tamano_big_mean=('tamano_big', 'mean'),
        tamano_big_sem=('tamano_big', 'sem'),
        n_avalanchas=('tamano_big', 'count')
    ).reset_index()
    
    # Manejo de NaNs en caso de que un grupo tenga una sola muestra (el SEM da NaN)
    stats['tamano_big_sem'] = stats['tamano_big_sem'].fillna(0)

    # Calculamos el logaritmo y propagamos su error: d(ln(x)) = dx / (x + 1)
    stats['y_log'] = np.log(stats['tamano_big_mean'] + 1)
    stats['y_log_err'] = stats['tamano_big_sem'] / (stats['tamano_big_mean'] + 1)
    
    # Aseguramos que la carpeta exista por las dudas
    out_dir = "../processed_data/1_avalanche_data"
    os.makedirs(out_dir, exist_ok=True)
    
    # Guardamos el archivo CSV con la información procesada
    output_csv = os.path.join(out_dir, "datos_curvas_atascamiento.csv")
    stats.to_csv(output_csv, index=False)
    print(f"Datos exportados correctamente a: {output_csv}")
    # ---------------------------------------

    # Graficamos curvas separadas
    plt.figure(figsize=(10, 7))
    for sis in stats['sistema'].unique():
        data_sis = stats[stats['sistema'] == sis]
        # Ordenamos por chi para que la línea no se cruce
        data_sis = data_sis.sort_values('chi')
        
        # Usamos errorbar en lugar de plot para graficar con el error calculado
        plt.errorbar(
            x=data_sis['chi'], 
            y=data_sis['y_log'], 
            yerr=data_sis['y_log_err'], 
            fmt='o-',          # Marcadores circulares unidos por línea
            capsize=4,         # Topes horizontales en la barra de error
            capthick=1.5,      # Grosor de los topes
            elinewidth=1.5,    # Grosor de la línea de error
            label=sis
        )

    plt.xlabel(r"Concentración de aditivo $\chi$", fontsize=12)
    plt.ylabel(r"$\ln(\langle S_{big} \rangle + 1)$", fontsize=12)
    plt.title("Análisis de Atascamiento y Tamaño de Avalancha", fontsize=14)
    plt.legend(title="Sistemas")
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Guardamos la imagen
    out_img = "analisis_atascamiento_comparativo.jpg"
    plt.savefig(out_img, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Gráfico exportado correctamente a: {out_img}")

if __name__ == "__main__":
    main()