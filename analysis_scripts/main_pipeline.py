import os
import shutil

# --- Módulos  ---
import indexer
import processor
import flow_analysis
import tail_distribution_chi
import density_map
import temporal_chi
import generar_csv_arcos
import arch_consolidator
import histogram_arch

# El filtro del chi lo aplica flow_analysis

def main():
    print("="*60)
    print("   PIPELINE DE ANÁLISIS MEJORADO Y ARCOS   ")
    print("="*60)

    # ==========================================================
    # 1. INDEXACIÓN: Crea la base de datos maestra
    # ==========================================================
    indexer.main()
    idx_path = "/home/juli/work/lab/project/sim-binary-shapes-2d/master_sim_index.csv"
    if not os.path.exists(idx_path):
        print("[-] Error: No se pudo generar el índice. Abortando.")
        return

    # ==========================================================
    # 2. PROCESAMIENTO: Genera NPZ y el CSV global de avalanchas
    # ==========================================================
    processor.main()

    # ==========================================================
    # 3. ANÁLISIS DE ARCOS ESPACIALES (NUEVO)
    # ==========================================================
    print("\n[+] Extrayendo estadísticas espaciales de los arcos...")
    df_idx = pd.read_csv(idx_path)
    
    # a. Generar micro-csvs de arcos localmente en cada simulación
    for index, row in df_idx.iterrows():
        sim_path = row.get('path', '')
        if os.path.exists(sim_path):
            print(f"  -> Buscando arcos en {row.get('sim_hash', 'unk')}...", end='\r')
            generar_csv_arcos.procesar_directorio(sim_path)
    print("\n  -> Extracción de arcos local finalizada.")

    # b. Consolidar todos los micro-csv en un Mega Dataset
    exito_cons = arch_consolidator.consolidate_arcs(idx_path=idx_path)
    
    # c. Generar los histogramas usando el Mega Dataset
    if exito_cons:
        histogram_arch.plot_arch_histograms()

    # ==========================================================
    # 4. ANÁLISIS ESTADÍSTICO TRADICIONAL
    # ==========================================================
    print("\n[+] Ejecutando análisis estadístico global de flujo y avalanchas...")
    
    # Podés modificar fixed_val y target_system desde acá mismo
    # flow_analysis.main(
    #     mode='ratio_sweep',
    #     fixed_val=0.01,
    #     normalize=True,
    #     target_system='Disco(G)-Disco(C)',  # <- Elegir el sistema (o poné None para ver todos)
    #     av_path="../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv",
    #     idx_path=idx_path
    # )
    flow_analysis.main(
        av_path="/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv",
        idx_path=idx_path
    )
    
    tail_distribution_chi.main(
        av_path="/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv",
        idx_path=idx_path
    )
    # ==========================================================
    # 5. MAPAS ESPACIALES Y PERFILES
    # ==========================================================
    print("\n[+] Generando mapas espaciales y perfiles de flujo...")
    temporal_chi.main()
    
    for index, row in df_idx.iterrows():
        s_hash = row['sim_hash']
        t = row.get('tirada', 0)
        
        npz_file = f"0_mapa_prepro/mapas_{s_hash}_T{t}.npz"
        
        if os.path.exists(npz_file):
            chi_val = row.get('chi', 0.1) 
            # plot_profiles.plot_perfil_horizontal(npz_file, altura_y=10) # Comentado si no lo pasaste
            density_map.plot_segregation_analysis(npz_file, chi_global=chi_val)

    # ==========================================================
    # 6. LIMPIEZA DE ARCHIVOS TEMPORALES
    # ==========================================================
    print("\n[+] Limpiando archivos temporales...")
    temp_folder = "0_mapa_prepro"
    if os.path.exists(temp_folder):
        try:
            shutil.rmtree(temp_folder)
            print(f" [-] Carpeta '{temp_folder}' eliminada correctamente.")
        except Exception as e:
            print(f" [!] Error al intentar borrar '{temp_folder}': {e}")
            
    print("\n[+] PIPELINE COMPLETADO EXITOSAMENTE.")

if __name__ == "__main__":
    # Importante para multiprocesamiento local en windows/mac
    import multiprocessing
    multiprocessing.freeze_support()
    import pandas as pd
    main()