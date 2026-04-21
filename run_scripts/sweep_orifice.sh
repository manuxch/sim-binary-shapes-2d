#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BARRIDO DE ANCHO DE ORIFICIO (WIDTH / RHOLE)
# ==============================================================================

# 1. Configuración Fija
N_PARTICLES=2000       # Número de partículas fijo para todas las simulaciones

# 2. Variable a barrer: Anchos del orificio
# Nota: Asegúrate de que estos valores tengan sentido físico con el radio de tus partículas
WIDTHS=(1.5)

DELAY=5
TEMPLATE_FILE="params_template.in"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- AUTO-DETECCIÓN DE FORMA ---
# Lee el template para ver si es DISK o SQUARE basado en el número de lados (última col)
SIDES=$(awk '/^[0-9]+[[:space:]]+0\.5/ {print $3}' "${BASE_DIR}/${TEMPLATE_FILE}" | head -n 1)

if [ "$SIDES" -eq "1" ]; then SHAPE="DISK"; elif [ "$SIDES" -eq "4" ]; then SHAPE="SQUARE"; else SHAPE="POLY${SIDES}"; fi
echo ">>> Detectado: ${SHAPE}"

# Directorio Principal del Barrido
RUNS_DIR="${BASE_DIR}/barrido_width_${SHAPE}"
mkdir -p "${RUNS_DIR}"

echo ">>> Iniciando barrido de anchos para N=${N_PARTICLES}..."

for W in "${WIDTHS[@]}"; do
    # Formatear el nombre del ancho para la carpeta (reemplazar punto por 'p')
    # Ejemplo: 1.5 -> 1p5
    W_STR="${W/./p}"
    
    # Nombre único de la simulación
    # Ejemplo: DISK_Width_1p5_N2250
    RUNID="${SHAPE}_Width_${W_STR}_N${N_PARTICLES}"
    RUN_DIR="${RUNS_DIR}/${RUNID}"
    
    mkdir -p "${RUN_DIR}"

    SEED=$(od -vAn -N4 -tu4 < /dev/urandom | tr -d '[:space:]')
    echo ">>> Lanzando ${RUNID} (Width=${W})..."

    # Crear params.in usando sed
    # CAMBIOS CLAVE AQUI:
    # 1. @RHOLE@ ahora recibe la variable ${W} (el ancho actual del loop)
    # 2. La línea que define N ahora recibe la constante ${N_PARTICLES}
    sed -E \
        -e "s/@RHOLE@/${W}/g" \
        -e "s/@RUNID@/${RUNID}/g" \
        -e "s/@SEED@/${SEED}/g" \
        -e "s/^[0-9]+([[:space:]]+0\.5[[:space:]]+)/${N_PARTICLES}\1/" \
        "${BASE_DIR}/${TEMPLATE_FILE}" > "${RUN_DIR}/params.in"

    # Ejecutar en background
    (
        cd "${RUN_DIR}"
        # Asegúrate de que 'eo-silo' esté en la carpeta base y sea ejecutable
        "${BASE_DIR}/eo-silo" params.in > log.txt 2>&1
    ) &

    # Espera para no saturar el arranque
    sleep "${DELAY}"
done

echo ">>> ¡Listo! Barrido de Width finalizado."
echo ">>> Las simulaciones corren en background en: ${RUNS_DIR}"