#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BARRIDO DE N (CANTIDAD DE GRANOS) - VERSIÓN NO BLOQUEANTE
# Autodetecta la forma, lanza todas las simulaciones y libera la terminal.
# ==============================================================================

OUTLET=2.00
PARTICLE_COUNTS=(200 400 800 1000 1500 2500 3000)

DELAY=2             # Tiempo de espera entre lanzamientos
TEMPLATE_FILE="params_template.in" 

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- LÓGICA DE DETECCIÓN DE FORMA ---
SIDES=$(awk '/^[0-9]+[[:space:]]+0\.5/ {print $3}' "${BASE_DIR}/${TEMPLATE_FILE}" | head -n 1)

if [ "$SIDES" -eq "1" ]; then
    SHAPE_NAME="DISK"
elif [ "$SIDES" -eq "4" ]; then
    SHAPE_NAME="SQUARE"
else
    SHAPE_NAME="POLY${SIDES}"
fi

echo ">>> Detectado: Lados=${SIDES} -> Forma=${SHAPE_NAME}"
# ------------------------------------

# La carpeta principal tendrá el nombre de la forma
RUNS_DIR="${BASE_DIR}/barrido_N_${SHAPE_NAME}_outlet_R${OUTLET/./p}"
mkdir -p "${RUNS_DIR}"

echo ">>> Iniciando lanzamiento masivo de N para ${SHAPE_NAME}..."

for N in "${PARTICLE_COUNTS[@]}"; do
    H=180.0 

    # ID de la corrida individual
    RUNID="${SHAPE_NAME}_N${N}_R${OUTLET/./p}"
    RUN_DIR="${RUNS_DIR}/${RUNID}"
    mkdir -p "${RUN_DIR}"

    SEED=$(od -vAn -N4 -tu4 < /dev/urandom | tr -d '[:space:]')

    echo ">>> Lanzando ${RUNID} (Seed: ${SEED})..."

    # Sed: Cambia N, mantiene el resto de la línea (forma), cambia Seed y H
    sed -E \
        -e "s/@RHOLE@/${OUTLET}/g" \
        -e "s/@RUNID@/${RUNID}/g" \
        -e "s/@SEED@/${SEED}/g" \
        -e "s/^H:.*/H: ${H}/" \
        -e "s/^[0-9]+([[:space:]]+0\.5[[:space:]]+)/${N}\1/" \
        "${BASE_DIR}/${TEMPLATE_FILE}" > "${RUN_DIR}/params.in"

    # EJECUCIÓN EN BACKGROUND
    # Sin 'wait', sin control de MAXJOBS. Se lanza y se pasa al siguiente.
    (
        cd "${RUN_DIR}"
        time "${BASE_DIR}/eo-silo" params.in > log.txt 2>&1
    ) &

    # Pausa técnica para dar tiempo a crear archivos
    sleep "${DELAY}"
done

echo ">>> ¡Listo! Todas las simulaciones de N han sido lanzadas en segundo plano."
echo ">>> Puedes cerrar esta terminal si lo deseas."