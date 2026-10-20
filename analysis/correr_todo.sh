#!/bin/bash
# Corre toda la cadena de analisis, de los datos crudos a las figuras.
#
# Uso (desde cualquier carpeta):
#     bash analysis/correr_todo.sh                 # todos los pasos
#     bash analysis/correr_todo.sh avalanchas      # solo algunos pasos
#     bash analysis/correr_todo.sh fuerzas presion
#
# Pasos (en este orden):
#   avalanchas  main_pipeline.py: indice, avalanchas, arcos, estadisticas de flujo
#   extras      masa de avalancha (grandes, chicos, total)
#   figuras     graficos_finales.py (todas las figuras 2-15)
#   segregacion temporal_chi.py --ranking
#   fuerzas     force_arch_v4.py + un pdf por geometria/ratio
#   presion     presion_tensor_arch.py + comparacion vs chi + mapas de calor
#
# De donde lee y donde escribe (ver analysis/rutas.py):
#   SIM_DATA_DIR    carpetas con las simulaciones, varias separadas por ':'
#   RESULTADOS_DIR  donde van master_sim_index.csv y processed_data/
#                   (sin definir: el repo)
#   CONTENEDOR      contenedor de Apptainer
#   APPTAINER_BIND  carpetas que ve el contenedor (ej. /mnt/c)
set -euo pipefail

CONTENEDOR="${CONTENEDOR:-$HOME/work/lab/containers/workstation_full.sif}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$DIR/.." && pwd)"
RESULTADOS_DIR="${RESULTADOS_DIR:-$REPO_DIR}"
export RESULTADOS_DIR
PROC="$RESULTADOS_DIR/processed_data"
PRESION_OUT="${PRESION_OUT:-$PROC/presion/tensor}"
FORMAS="${FORMAS:-Disco Triangulo Cuadrado Pentagono Octogono}"

py() { apptainer exec "$CONTENEDOR" python3 "$@"; }

titulo() { echo; echo "=================================================="; echo " $*"; echo "=================================================="; }

PASOS=("$@")
[ ${#PASOS[@]} -eq 0 ] && PASOS=(avalanchas extras figuras segregacion fuerzas presion)
quiere() { local p; for p in "${PASOS[@]}"; do [ "$p" = "$1" ] && return 0; done; return 1; }

echo "Datos:      ${SIM_DATA_DIR:-(los del repo)}"
echo "Resultados: $RESULTADOS_DIR"
echo "Pasos:      ${PASOS[*]}"
mkdir -p "$PROC"
inicio=$(date +%s)

if quiere avalanchas; then
    titulo "1. Avalanchas y arcos (main_pipeline.py)"
    py "$DIR/1_avalanchas_y_arcos/main_pipeline.py"
fi

if quiere extras; then
    titulo "2. Masa de avalancha"
    py "$DIR/1_avalanchas_y_arcos/graficar_masa_avalancha.py" \
        --sistemas Disco-Disco Tri-Disco Cuad-Disco Pent-Disco Oct-Disco --area_ratio 0.1
fi

if quiere figuras; then
    titulo "3. Figuras finales (graficos_finales.py)"
    # graficos_finales.py busca figs.mplstyle en la carpeta desde la que se corre
    (cd "$DIR/1_avalanchas_y_arcos" && py graficos_finales.py)
fi

if quiere segregacion; then
    titulo "4. Segregacion en el tiempo (temporal_chi.py --ranking)"
    py "$DIR/1_avalanchas_y_arcos/temporal_chi.py" --ranking
fi

if quiere fuerzas; then
    titulo "5. Fuerzas (force_arch_v4.py)"
    py "$DIR/2_fuerzas/force_arch_v4.py" --idx "$RESULTADOS_DIR/master_sim_index.csv" \
        --out "$PROC/fuerzas/datos_v4"
    CONTENEDOR="$CONTENEDOR" bash "$DIR/2_fuerzas/graficar_todas_configuraciones.sh"
fi

if quiere presion; then
    titulo "6. Presion y tensor (presion_tensor_arch.py)"
    IFS=':' read -r -a DATOS <<< "${SIM_DATA_DIR:-$REPO_DIR/datos_simulaciones/simulation_data/R_2.0}"
    py "$DIR/3_presion_y_mapas/presion_tensor_arch.py" --dir "${DATOS[@]}" \
        --master "$RESULTADOS_DIR/master_sim_index.csv" --out "$PRESION_OUT" --reanudar
    py "$DIR/3_presion_y_mapas/comparar_presion_por_chi.py" \
        --csv "$PRESION_OUT/resumen_presion_por_atasco.csv" --out "$PRESION_OUT/comparacion_chi.pdf"
    # shellcheck disable=SC2086
    py "$DIR/3_presion_y_mapas/hacer_mapas.py" --datos "$PRESION_OUT" \
        --salida "$PROC/mapas_calor" --formas $FORMAS --reanudar
fi

fin=$(date +%s)
titulo "Listo en $(( (fin - inicio) / 60 )) min. Resultados en $RESULTADOS_DIR"
