"""
Rutas del proyecto, calculadas a partir de la ubicacion de este archivo
(analysis/rutas.py), asi los scripts funcionan sin importar donde este
clonado el repo (/home/juli/work/..., /mnt/e/work/..., el cluster, etc.).

Uso desde un script en analysis/<carpeta>/:

    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
    import rutas

    pd.read_csv(rutas.MASTER_INDEX)

Los datos crudos de las simulaciones pueden vivir fuera del repo: en ese
caso, definir la variable de entorno SIM_DATA_DIR antes de correr, ej.:

    export SIM_DATA_DIR=/mnt/h/work/lab/project/sim-binary-shapes-2d/datos_simulaciones/simulation_data/R_2.0
"""
import os

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Datos crudos de simulacion (carpetas BARRIDO_*/Chi_*_W_*/frames_*)
SIM_DATA_DIR = os.environ.get(
    "SIM_DATA_DIR",
    os.path.join(REPO_DIR, "datos_simulaciones", "simulation_data", "R_2.0"),
)

# Indice maestro de simulaciones (lo genera indexer.py)
MASTER_INDEX = os.path.join(REPO_DIR, "master_sim_index.csv")

# Resultados
PROCESSED_DIR = os.path.join(REPO_DIR, "processed_data")
AVALANCHE_DIR = os.path.join(PROCESSED_DIR, "1_avalanche_data")
SPATIAL_MAPS_DIR = os.path.join(PROCESSED_DIR, "2_spatial_maps")
ARCH_HIST_DIR = os.path.join(PROCESSED_DIR, "4_arch_histograms")
GRAFICOS_FINALES_DIR = os.path.join(PROCESSED_DIR, "5_graficos_finales")
FUERZAS_DIR = os.path.join(PROCESSED_DIR, "fuerzas")
PRESION_DIR = os.path.join(PROCESSED_DIR, "presion")
MAPAS_CALOR_DIR = os.path.join(PROCESSED_DIR, "mapas_calor")
