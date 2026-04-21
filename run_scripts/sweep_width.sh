#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BARRIDO DE ANCHO DE SILO (VERSIÓN NO BLOQUEANTE)
# Autodetecta la forma, escala N, lanza todo y libera la terminal.
# ==============================================================================

REF_R="10.25"    # Radio original
REF_N="1500"     # Granos base para ese radio
OUTLET="2.00"
MULTIPLIERS=(1.5 2.0 2.5 3.0 3.5 4.0)

DELAY=2          # Tiempo de espera entre lanzamientos
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

RUNS_DIR="${BASE_DIR}/barrido_width_${SHAPE_NAME}"
mkdir -p "${RUNS_DIR}"

echo ">>> Iniciando lanzamiento masivo de ANCHO para ${SHAPE_NAME}..."

for MULT in "${MULTIPLIERS[@]}"; do
    
    # Cálculos matemáticos
    CURRENT_R=$(awk -v ref="$REF_R" -v mult="$MULT" 'BEGIN { print ref * mult }')
    CURRENT_N=$(awk -v ref="$REF_N" -v mult="$MULT" 'BEGIN { printf "%.0f", ref * mult }')

    # ID incluye la forma y el ancho
    RUNID="${SHAPE_NAME}_Width_x${MULT/./p}_R${CURRENT_R}_N${CURRENT_N}"
    RUN_DIR="${RUNS_DIR}/${RUNID}"
    mkdir -p "${RUN_DIR}"

    SEED=$(od -vAn -N4 -tu4 < /dev/urandom | tr -d '[:space:]')

    echo ">>> Lanzando ${RUNID} (Seed: ${SEED})..."

    # Sed: Cambia N y Radio_silo, mantiene el resto de la línea (forma)
    sed -E \
        -e "s/@RHOLE@/${OUTLET}/g" \
        -e "s/@RUNID@/${RUNID}/g" \
        -e "s/@SEED@/${SEED}/g" \
        -e "s/^Radio_silo:.*/Radio_silo: ${CURRENT_R}/" \
        -e "s/^[0-9]+([[:space:]]+0\.5[[:space:]]+)/${CURRENT_N}\1/" \
        "${BASE_DIR}/${TEMPLATE_FILE}" > "${RUN_DIR}/params.in"

    # EJECUCIÓN EN BACKGROUND
    # No usamos 'wait' ni bucles de control.
    (
        cd "${RUN_DIR}"
        time "${BASE_DIR}/eo-silo" params.in > log.txt 2>&1
    ) &

    # Pequeña pausa para no atragantar el disco duro al crear archivos
    sleep "${DELAY}"
done

echo ">>> ¡Listo! Todas las simulaciones han sido lanzadas en segundo plano."
echo ">>> Puedes cerrar esta terminal si lo deseas."