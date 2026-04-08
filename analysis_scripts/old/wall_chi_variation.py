import numpy as np
import pandas as pd
import glob
import os
import json
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count

# --- CONFIGURACIÓN ---
INDEX_FILE = "../master_sim_index.csv"
D_PARED = 2.0  # Zona de influencia de la pared (metros)
CPU_CORES = cpu_count()
OUTPUT_FOLDER = "../processed_data/5_segregation_analysis"  # Carpeta de salida para el reporte global

def calcular_area_unitaria(radio, lados):
    """Calcula el área exacta según la geometría"""
    if lados == 1:   # DISCO
        return np.pi * (radio ** 2)
    elif lados == 4: # CUADRADO (asumiendo que R es la mitad del lado o el radio circunscrito, ajusta si es necesario)
        return 4.0 * (radio ** 2) 
    else:            # POLÍGONOS REGULARES (3, 5, 6, etc.)
        # Fórmula del área usando el radio de la circunferencia circunscrita
        return (lados * (radio ** 2) * np.sin(2 * np.pi / lados)) / 2

def analizar_simulacion(row):
    path = row['path']
    dir_id = row['dirID']
    radio_silo = row['Radio_silo']
    sim_hash = row['sim_hash']
    tirada = row['tirada']
    
    # 1. Identificar Geometrías y el Tipo Chica (0-indexed)
    try:
        grain_info = json.loads(row['grain_json'])
        areas = {}
        radios = []
        for i, g in enumerate(grain_info):
            areas[i] = calcular_area_unitaria(g['radius'], g['sides'])
            radios.append(g['radius'])
        
        tipo_chica = np.argmin(radios)
        area_chica = areas[tipo_chica]
    except Exception as e:
        return None

    # 2. Buscar archivos .xy
    pattern = os.path.join(path, f"frames_{dir_id}", "**", "*.xy")
    archivos = sorted(glob.glob(pattern, recursive=True))
    if not archivos: return None

    stats_sim = []
    
    # 3. Procesar Frames
    for arc in archivos:
        try:
            counts_total = {t: 0 for t in areas.keys()}
            counts_nucleo = {t: 0 for t in areas.keys()}
            
            with open(arc, 'r') as f:
                for linea in f:
                    p = linea.split()
                    if not p or not p[0].replace('-','').isdigit(): continue
                    if int(p[0]) < 0: continue # Ignorar paredes
                    
                    n_verts = int(p[1])
                    tipo = int(p[-1]) # Tipo en Box2D (0, 1, ...)
                    
                    # Centroide X
                    ix = range(2, 2 + 2 * n_verts, 2)
                    x = np.mean([float(p[i]) for i in ix])
                    
                    if tipo in counts_total:
                        counts_total[tipo] += 1
                        if (radio_silo - abs(x)) >= D_PARED:
                            counts_nucleo[tipo] += 1
            
            # Cálculo de Chi por ÁREA
            a_chica_tot = counts_total[tipo_chica] * area_chica
            a_total = sum(counts_total[t] * areas[t] for t in areas)
            chi_f = a_chica_tot / a_total if a_total > 0 else 0
            
            a_chica_nuc = counts_nucleo[tipo_chica] * area_chica
            a_total_nuc = sum(counts_nucleo[t] * areas[t] for t in areas)
            chi_eff_f = a_chica_nuc / a_total_nuc if a_total_nuc > 0 else 0
            
            stats_sim.append((chi_f, chi_eff_f))
        except:
            continue

    if not stats_sim: return None
    
    # 4. Estadísticas y Gráfica
    df_res = pd.DataFrame(stats_sim, columns=['chi', 'chi_eff'])
    estables = df_res.tail(int(len(df_res)*0.2)) # Último 20%
    
    chi_nom = estables['chi'].mean()
    chi_eff = estables['chi_eff'].mean()
    secuestro = (chi_nom - chi_eff) / chi_nom * 100 if chi_nom > 0.001 else 0

    # --- GENERAR GRÁFICA ---
    plt.figure(figsize=(8, 5))
    plt.plot(df_res['chi'], label='$\chi$ Total (Frame)', color='gray', alpha=0.3)
    plt.plot(df_res['chi_eff'], label='$\chi$ Efectivo (Núcleo)', color='#e74c3c', linewidth=1.5)
    
    plt.axhline(y=chi_nom, color='black', linestyle='--', alpha=0.6, label=f'Nominal: {chi_nom:.3f}')
    plt.axhline(y=chi_eff, color='#c0392b', linestyle=':', label=f'Efectivo: {chi_eff:.3f}')
    
    plt.title(f"Análisis de Segregación | Hash: {sim_hash}\nSecuestro: {secuestro:.1f}%", fontsize=12)
    plt.xlabel("Número de Frame")
    plt.ylabel("Fracción de Área (Chicas / Total)")
    plt.legend(loc='upper right', frameon=True, facecolor='white', framealpha=0.9)
    plt.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    
    # Guardar en la carpeta de la simulación
    graph_name = f"plot_segregacion_{sim_hash}_T{tirada}.svg"
    plt.savefig(os.path.join(path, graph_name), format='svg')
    plt.close()

    return {
        'sim_hash': sim_hash,
        'tirada': tirada,
        'chi_nominal': chi_nom,
        'chi_efectivo': chi_eff,
        'secuestro_porcentaje': secuestro,
        'ruta_grafica': graph_name
    }

# --- FUNCIÓN MAIN AGREGADA ---
def main():
    if not os.path.exists(INDEX_FILE):
        print(f"[-] Error: No se encontró {INDEX_FILE}")
        return

    # Crear carpeta de salida si no existe
    if not os.path.exists(OUTPUT_FOLDER):
        try:
            os.makedirs(OUTPUT_FOLDER)
        except OSError:
            pass # Si ya existe, ignoramos

    df_idx = pd.read_csv(INDEX_FILE)
    print(f"Iniciando análisis de segregación en {CPU_CORES} hilos...")
    
    # Preparar tareas para el Pool
    tasks = [row for _, row in df_idx.iterrows()]
    
    with Pool(CPU_CORES) as p:
        reporte = p.map(analizar_simulacion, tasks)
    
    # Limpiar resultados nulos y exportar
    resultados_validos = [r for r in reporte if r is not None]
    
    if resultados_validos:
        df_final = pd.DataFrame(resultados_validos)
        df_final = df_final.sort_values(['sim_hash', 'tirada'])
        
        output_csv = os.path.join(OUTPUT_FOLDER, "reporte_segregacion_final.csv")
        df_final.to_csv(output_csv, index=False)
        
        print(f"\n✅ PROCESO COMPLETADO")
        print(f"Reporte: {output_csv}")
        print(f"Gráficos SVG generados en cada subdirectorio.")
    else:
        print("\n[!] No se generaron resultados válidos.")

if __name__ == "__main__":
    main()