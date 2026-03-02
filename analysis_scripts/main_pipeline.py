import os
import pandas as pd
import json

# Importamos tus scripts corregidos
import indexer
import processor
import plot_profiles
import flow_analysis
import tail_distribution_chi
import density_map
import shutil
import temporal_chi
#import wall_chi_variation
#import plot_wall_chi

def main():
    print("="*60)
    print("   PIPELINE DE ANÁLISIS MEJORADO   ")
    print("="*60)

    # 1. INDEXACIÓN: Crea la base de datos maestra
    indexer.main()
    if not os.path.exists("../master_sim_index.csv"):
        print("[-] Error: No se pudo generar el índice. Abortando.")
        return

    # 2. PROCESAMIENTO: Genera NPZ y el CSV global de avalanchas
    # (Este ya guarda los datos en 0_mapa_prepro y 1_avalanche_data)
    processor.main()

    # 3. ANÁLISIS ESTADÍSTICO (Versiones corregidas que separan por sistema)
    print("\n[+] Ejecutando análisis estadístico por tipo de partícula...")
    
    # Genera las curvas ln(S+1) comparativas (Disco-Disco vs Disco-Cuadrado)
    flow_analysis.main(
        av_path="../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv",
        idx_path="../master_sim_index.csv"
    )
    
    # Genera los gráficos de colas de distribución (uno para cada sistema)
    tail_distribution_chi.main(
        av_path="../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv",
        idx_path="../master_sim_index.csv"
    )

    # 4. MAPAS Y PERFILES: Loop detallado por simulación
    print("\n[+] Generando mapas visuales y perfiles transversales...")
    df_idx = pd.read_csv("../master_sim_index.csv")
    
    for _, row in df_idx.iterrows():
        s_hash = row['sim_hash']
        t = row['tirada']
        
        # Obtenemos la identificación exacta del sistema para el nombre del archivo
        # Reutilizamos la lógica del indexer para saber qué mezcla es
        try:
            grains = json.loads(row['grain_json'])
            grains_sorted = sorted(grains, key=lambda x: x['radius'], reverse=True)
            big_name = "Disco" if grains_sorted[0]['sides'] == 1 else "Cuad"
            small_name = "Disco" if grains_sorted[1]['sides'] == 1 else "Cuad"
            sistema_id = f"{big_name}_G-{small_name}_C"
        except:
            sistema_id = "Desconocido"

        # Buscamos el archivo de datos espaciales
        npz_file = f"0_mapa_prepro/mapas_{s_hash}_T{t}.npz"
        
        if os.path.exists(npz_file):
            print(f" > Procesando {sistema_id} | Hash: {s_hash} (T{t})")
            
            # Extraemos el Chi de la fila para que los mapas tengan la escala correcta
            # Intentamos obtenerlo de la columna 'chi', si no, de la ruta
            chi_val = row.get('chi', 0.1) 

            # A. Perfiles transversales
            plot_profiles.plot_perfil_horizontal(npz_file, altura_y=10)
            
            # C. Mapas de Segregación
            density_map.plot_segregation_analysis(npz_file, chi_global=chi_val)
        else:
            print(f" [!] No se encontró el .npz para {s_hash}")


    # 5. LIMPIEZA DE ARCHIVOS TEMPORALES
    print("\n[+] Limpiando archivos temporales...")
    temp_folder = "0_mapa_prepro"
    
    if os.path.exists(temp_folder):
        try:
            shutil.rmtree(temp_folder) # Borra la carpeta y todo su contenido
            print(f" [-] Carpeta '{temp_folder}' eliminada correctamente.")
        except Exception as e:
            print(f" [!] Error al intentar borrar '{temp_folder}': {e}")
    else:
        print(f" [.] La carpeta '{temp_folder}' ya no existe.")


    temporal_chi.main()
    #wall_chi_variation.main()
    #plot_wall_chi.main()

    print("\n" + "="*60)
    print("   ANÁLISIS COMPLETADO   ")
    print("="*60)

if __name__ == "__main__":
    main()