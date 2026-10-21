import os
import shutil
import multiprocessing
import pandas as pd

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))  # rutas.py vive en analysis/
import rutas
import indexer
import processor
import flow_analysis
import density_map
import temporal_chi
import generar_csv_arcos
import arch_consolidator
import histogram_arch


def main():
    print("=" * 60)
    print("   PIPELINE DE ANÁLISIS MEJORADO Y ARCOS   ")
    print("=" * 60)

    # 1. INDEXACIÓN
    idx_path = rutas.MASTER_INDEX
    if not indexer.main() or not os.path.exists(idx_path):
        print("[-] Error: No se pudo generar el índice. Abortando.")
        return False

    # 2. PROCESAMIENTO DE AVALANCHAS
    processor.main()

    # 3. ARCOS POR SIMULACIÓN
    print("\n[+] Extrayendo estadísticas espaciales de los arcos...")
    df_idx = pd.read_csv(idx_path)

    for _, row in df_idx.iterrows():
        sim_path = row.get('path', '')
        if os.path.exists(sim_path):
            print(f"  -> Buscando arcos en {row.get('sim_hash', 'unk')}...", end='\r')
            generar_csv_arcos.procesar_directorio(sim_path)

    print("\n  -> Extracción de arcos local finalizada.")

    # 4. CONSOLIDAR ARCOS
    exito_cons = arch_consolidator.consolidate_arcs(idx_path=idx_path)

    # 5. ESTADÍSTICA DE FLUJO
    print("\n[+] Ejecutando análisis estadístico global de flujo y avalanchas...")
    flow_analysis.main(idx_path=idx_path)

    # 6. HISTOGRAMAS DE ARCOS OPCIONALES
    # if exito_cons:
    #     histogram_arch.plot_arch_histograms()

    # 7. OTROS ANÁLISIS OPCIONALES
    # temporal_chi.main()

    print("\n[+] PIPELINE COMPLETADO EXITOSAMENTE.")
    return True


if __name__ == "__main__":
    import sys
    multiprocessing.freeze_support()
    sys.exit(0 if main() else 1)
