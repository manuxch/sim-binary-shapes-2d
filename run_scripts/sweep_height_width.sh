#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# SIMULACIÓN ÚNICA: ESCALADO 2D - EJECUCIÓN EN BACKGROUND
# Escala radio/altura linealmente y partículas cuadráticamente.
# ==============================================================================

# 1. Configuración
# ------------------------------------------------------------------------------
FACTOR="2.0"         # El factor de multiplicación solicitado

REF_R="10.25"        # Radio/Ancho original del template
REF_N="1500"         # Número de partículas original del template
REF_H="120.0"        # Altura original del template

OUTLET="2.00"        # Tamaño del orificio
TEMPLATE_FILE="params_template.in"
BASE_DIR="$(cd "$(dirname "../${BASH_SOURCE[0]}")" && pwd)"

# 2. Detección de Forma
# ------------------------------------------------------------------------------
SIDES=$(awk '/^[0-9]+[[:space:]]+0\.5/ {print $3}' "${BASE_DIR}/${TEMPLATE_FILE}" | head -n 1)

if [ "$SIDES" -eq "1" ]; then
    SHAPE_NAME="DISK"
elif [ "$SIDES" -eq "4" ]; then
    SHAPE_NAME="SQUARE"
else
    SHAPE_NAME="POLY${SIDES}"
fi

echo ">>> Detectado: Forma=${SHAPE_NAME}"

# 3. Cálculos de Escalado (Área 2D)
# ------------------------------------------------------------------------------
# N_nuevo = N_ref * factor^2
CURRENT_N=$(awk -v ref="$REF_N" -v mult="$FACTOR" 'BEGIN { printf "%.0f", ref * mult * mult }')

# R_nuevo = R_ref * factor
CURRENT_R=$(awk -v ref="$REF_R" -v mult="$FACTOR" 'BEGIN { print ref * mult }')

# H_nuevo = H_ref * factor
CURRENT_H=$(awk -v ref="$REF_H" -v mult="$FACTOR" 'BEGIN { print ref * mult }')

echo "--------------------------------------------------"
echo " Factor de Escala: $FACTOR"
echo " -> Radio Nuevo:   $CURRENT_R (Base: $REF_R)"
echo " -> Altura Nueva:  $CURRENT_H (Base: $REF_H)"
echo " -> N Partículas:  $CURRENT_N (Base: $REF_N - Escalado x$FACTOR^2)"
echo "--------------------------------------------------"

# 4. Preparación y Ejecución
# ------------------------------------------------------------------------------
RUNID="${SHAPE_NAME}_SCALED_2D_x${FACTOR/./p}_N${CURRENT_N}"
RUN_DIR="${BASE_DIR}/${RUNID}"

mkdir -p "${RUN_DIR}"
SEED=$(od -vAn -N4 -tu4 < /dev/urandom | tr -d '[:space:]')

echo ">>> Configurando ${RUNID} (Seed: ${SEED})..."

# Aplicamos los cambios con SED
sed -E \
    -e "s/@RHOLE@/${OUTLET}/g" \
    -e "s/@RUNID@/${RUNID}/g" \
    -e "s/@SEED@/${SEED}/g" \
    -e "s/^Radio_silo:.*/Radio_silo: ${CURRENT_R}/" \
    -e "s/^H:.*/H: ${CURRENT_H}/" \
    -e "s/^[0-9]+([[:space:]]+0\.5[[:space:]]+)/${CURRENT_N}\1/" \
    "${BASE_DIR}/${TEMPLATE_FILE}" > "${RUN_DIR}/params.in"

# --- EJECUCIÓN EN SEGUNDO PLANO ---
echo ">>> Lanzando simulación en BACKGROUND..."

(
    cd "${RUN_DIR}"
    # Redirigimos stdout y stderr al archivo log.txt
    # Usamos 'time' para que al final del log quede registrado cuánto tardó
    time "${BASE_DIR}/eo-silo" params.in > log.txt 2>&1
) &

# Capturamos el ID del proceso recién lanzado
PID=$!

echo "--------------------------------------------------"
echo ">>> ¡Simulación lanzada exitosamente!"
echo ">>> PID del proceso: $PID"
echo ">>> La terminal ha sido liberada."
echo ">>> Para ver el progreso usa:  tail -f ${RUN_DIR}/log.txt"
echo "--------------------------------------------------"