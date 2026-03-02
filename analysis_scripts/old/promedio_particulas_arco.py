import pandas as pd
import os
import glob
import re

# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================
# Ajusté la ruta según tu captura (PENTAGON)
BASE_FOLDER = "/home/juli/simulaciones/silo_2d_mixtures/datos_pesados/simulation_data/R_2.0/TIRADA2/BARRIDO_2D_DISK_PENTAGON"
OUTPUT_FILE = "resumen_chi_w_promedios.csv"

def extraer_parametros(nombre_carpeta):
    match_chi = re.search(r"Chi_(\d+p\d+)", nombre_carpeta)
    match_w = re.search(r"W_(\d+p\d+)", nombre_carpeta)
    chi_val = float(match_chi.group(1).replace('p', '.')) if match_chi else 0.0
    w_val = float(match_w.group(1).replace('p', '.')) if match_w else 0.0
    return chi_val, w_val

def generar_resumen_global():
    if not os.path.exists(BASE_FOLDER):
        print(f"Error: No se encuentra la carpeta {BASE_FOLDER}")
        return

    sim_folders = sorted([d for d in os.listdir(BASE_FOLDER) 
                         if os.path.isdir(os.path.join(BASE_FOLDER, d))])
    
    resultados_finales = []

    for sim_name in sim_folders:
        sim_path = os.path.join(BASE_FOLDER, sim_name)
        
        # --- NUEVA LÓGICA DE BÚSQUEDA ---
        # 1. Intentamos buscarlo en la raíz de la simulación (como en tu imagen)
        csv_path = os.path.join(sim_path, "estadisticas_arcos.csv")
        
        # 2. Si no existe ahí, buscamos dentro de frames_*
        if not os.path.exists(csv_path):
            stats_files = glob.glob(os.path.join(sim_path, "frames_*", "estadisticas_arcos.csv"))
            if stats_files:
                csv_path = stats_files[0]
            else:
                continue # Si no aparece en ningún lado, saltamos la carpeta
        
        try:
            df = pd.read_csv(csv_path)
            if df.empty: continue

            chi_val, w_val = extraer_parametros(sim_name)

            resultados_finales.append({
                'chi': chi_val,
                'W': w_val,
                'particulas_tipo_1_avg': df['Particulas_Tipo_1'].mean(),
                'particulas_tipo_0_avg': df['Particulas_Tipo_0'].mean(),
                'particulas_totales_avg': df['Total_Particulas_Arco'].mean(),
                'n_atascos': len(df),
                'folder': sim_name
            })
            print(f" [+] Procesado: {sim_name}")

        except Exception as e:
            print(f" [X] Error en {sim_name}: {e}")

    if resultados_finales:
        df_final = pd.DataFrame(resultados_finales).sort_values(by=['W', 'chi'])
        output_path = os.path.join(BASE_FOLDER, OUTPUT_FILE)
        df_final.to_csv(output_path, index=False)
        print(f"\n✅ Archivo guardado en: {output_path}")
    else:
        print("\n❌ No se encontró ningún 'estadisticas_arcos.csv'.")

if __name__ == "__main__":
    generar_resumen_global()