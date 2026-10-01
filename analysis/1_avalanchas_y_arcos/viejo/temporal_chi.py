import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
from multiprocessing import Pool, cpu_count

# --- CONFIGURACIÓN ---
INDEX_FILE = "/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
WINDOW_SIZE = 10.0  # Tamaño del batch en segundos
CPU_CORES = cpu_count()

def calcular_area_unitaria(radio, lados=1):
    """
    Calcula el área física real que ocupa la partícula en el silo.
    Se usa la fórmula del círculo porque el área de los polígonos 
    está normalizada en el simulador.
    """
    return np.pi * (radio ** 2)

def analizar_flujo_temporal(row):
    path = row['path']
    flux_filename = row['fluxFile']
    sim_hash = row['sim_hash']
    tirada = row['tirada']
    
    # 1. Identificar Geometrías y Calcular Chi Nominal desde el JSON
    try:
        grain_info = json.loads(row['grain_json'])
        areas_unitarias = {}
        radios = []
        areas_totales_poblacion = {}
        
        for i, g in enumerate(grain_info):
            tipo_id = i
            a_uni = calcular_area_unitaria(g['radius'], g['sides'])
            areas_unitarias[tipo_id] = a_uni
            radios.append(g['radius'])
            areas_totales_poblacion[tipo_id] = g['count'] * a_uni
        
        tipo_chica = np.argmin(radios)
        area_total_sistema = sum(areas_totales_poblacion.values())
        chi_nominal = areas_totales_poblacion[tipo_chica] / area_total_sistema if area_total_sistema > 0 else 0
        
    except Exception as e:
        return None

    # 2. Leer flx.dat
    flux_path = os.path.join(path, flux_filename)
    if not os.path.exists(flux_path): 
        return None
    
    try:
        df_flux = pd.read_csv(flux_path, sep=r'\s+', comment='#', header=None, usecols=[1, 2])
        df_flux.columns = ['tipo', 'tiempo']
        
        # 3. Crear los Batches
        t_start = df_flux['tiempo'].min()
        t_end = df_flux['tiempo'].max()
        bins = np.arange(t_start, t_end + WINDOW_SIZE, WINDOW_SIZE)
        
        if len(bins) < 2: return None 
        
        df_flux['batch'] = pd.cut(df_flux['tiempo'], bins=bins, labels=bins[:-1])
        
        # 4. Calcular el Chi por ÁREA
        batch_results = []
        for label, group in df_flux.groupby('batch', observed=True):
            counts = group['tipo'].value_counts()
            a_chicas_out = counts.get(tipo_chica, 0) * areas_unitarias[tipo_chica]
            a_total_out = sum(counts.get(t, 0) * areas_unitarias[t] for t in areas_unitarias.keys())
            
            if a_total_out > 0:
                chi_out = a_chicas_out / a_total_out
                batch_results.append({'tiempo': float(label) + WINDOW_SIZE/2, 'chi_eff': chi_out})
        
        df_plot = pd.DataFrame(batch_results)
        if df_plot.empty: return None

        # 5. Generar Gráfica
        plt.figure(figsize=(10, 5))
        plt.plot(df_plot['tiempo'], df_plot['chi_eff'], marker='o', color='#2980b9', 
                 linestyle='-', linewidth=1.2, markersize=4, label=r'$\chi_{salida}$ (Batch 10s)')
        
        # Línea de referencia nominal
        plt.axhline(y=chi_nominal, color='#e74c3c', linestyle='--', linewidth=2, 
                    alpha=0.8, label=f'Nominal Objetivo: {chi_nominal:.3f}')

        # --- NUEVO: MARCADOR DE DIFERENCIA FINAL ---
        last_row = df_plot.iloc[-1]
        t_final = last_row['tiempo']
        chi_final = last_row['chi_eff']
        
        # Línea vertical punteada de conexión (en verde para que resalte)
        plt.plot([t_final, t_final], [chi_final, chi_nominal], color='#27ae60', linestyle=':', linewidth=2.5)
        
        # Cálculo del porcentaje de diferencia en el punto final
        if chi_nominal > 0:
            diff_pct = (chi_nominal - chi_final) / chi_nominal * 100
            
            # Etiqueta de texto al lado de la línea
            plt.text(t_final + 1, (chi_final + chi_nominal) / 2, 
                     f"Diferencia porcentual:\n{diff_pct:.1f}%", 
                     color='#27ae60', fontweight='bold', fontsize=9,
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # Estética
        plt.title(f"Dinámica de Descarga | Hash: {sim_hash} | T{tirada}\nMezcla: {row.get('system_type', 'Desconocido')}", fontsize=12)
        plt.xlabel("Tiempo de Simulación (s)", fontsize=10)
        plt.ylabel(r"Concentración de Salida ($\chi_{area}$)", fontsize=10)
        
        # Ajuste de límites para que el texto no se corte
        plt.ylim(0, min(1.0, max(chi_nominal * 2.5, df_plot['chi_eff'].max() * 1.3)))
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend(loc='upper right', frameon=True, shadow=True)
        plt.tight_layout()
        
        graph_name = f"dinamica_flujo_final_{sim_hash}_T{tirada}.svg"
        plt.savefig(os.path.join(path, graph_name), format='svg')
        plt.close()
        
        return True

    except Exception as e:
        print(f"Error procesando {flux_path}: {e}")
        return None

# --- AQUÍ ESTÁ EL CAMBIO PRINCIPAL ---
def main():
    if not os.path.exists(INDEX_FILE):
        print(f"Error: No se encontró {INDEX_FILE} para chi_temporal.")
        return

    df_idx = pd.read_csv(INDEX_FILE)
    print(f"Analizando flujos temporales (Chi)...")
    
    # Preparamos los argumentos para el Pool
    tasks = [row for _, row in df_idx.iterrows()]
    
    with Pool(CPU_CORES) as p:
        p.map(analizar_flujo_temporal, tasks)
    
    print("\n✅ Proceso de Chi Temporal terminado. Revisa los archivos .svg.")

if __name__ == "__main__":
    main()