#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BARRIDO DOBLE: ANCHO DE ORIFICIO (W) y FRACCIÓN DE ÁREA (CHI)
# ==============================================================================

# 1. Configuración
# ------------------------------------------------------------------------------
N_REF=2000          # Cantidad total de partículas de referencia (para el área total)

# --- DEFINICIÓN DE LOS BARRIDOS ---
# Lista de valores de Chi (Fracción de área de pequeñas)
CHIS=(0.01 0.02 0.04 0.06 0.08 0.1 0.12 0.14 0.16 0.18 0.2)  

# Lista de anchos de orificio
WIDTHS=(2.0)

# Radio de las pequeñas (Las grandes se leen del template)
R_SMALL=0.158      

# Propiedades Físicas de las PEQUEÑAS (Densidad, Fricción, Restitución)
# NOTA: El "1" (forma de disco) se agrega automáticamente por código.
PHYSICS_SMALL="1.27324 0.5 0.1" 

DELAY=2 # Tiempo de espera entre lanzamientos para no saturar CPU al inicio
TEMPLATE_FILE="params_template.in"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ==============================================================================
# 2. ANÁLISIS AUTOMÁTICO DEL TEMPLATE (Solo se hace una vez)
# ==============================================================================

# Buscamos la línea que define los granos en el template.
RAW_LINE=$(grep -E "^[0-9]+[[:space:]]+[0-9.]+" "${BASE_DIR}/${TEMPLATE_FILE}" | head -n 1)

if [ -z "$RAW_LINE" ]; then
    echo "ERROR: No encontré la línea de definición de partículas en ${TEMPLATE_FILE}."
    exit 1
fi

# Extraemos datos de esa línea para cálculos de área
R_BIG=$(echo "$RAW_LINE" | awk '{print $2}')
SIDES_BIG=$(echo "$RAW_LINE" | awk '{print $3}')
PROPS_BIG_REST=$(echo "$RAW_LINE" | awk '{for(i=3;i<=NF;i++) printf $i (i==NF?"":" ")}')

# Definimos nombre de la forma para la carpeta
if [ "$SIDES_BIG" == "1" ]; then SHAPE_NAME="DISK"; elif [ "$SIDES_BIG" == "4" ]; then SHAPE_NAME="SQUARE"; else SHAPE_NAME="POLY${SIDES_BIG}"; fi

# Preparamos el patrón de búsqueda para SED (escapamos puntos)
SEARCH_PATTERN=$(echo "$RAW_LINE" | sed 's/\./\\./g')

echo ">>> Template Analizado: ${SHAPE_NAME} (R_BIG=${R_BIG})"
echo ">>> Iniciando Barrido Doble..."

# Carpeta contenedora general
PARENT_DIR="${BASE_DIR}/BARRIDO_2D_${SHAPE_NAME}"
mkdir -p "${PARENT_DIR}"

# ==============================================================================
# 3. BUCLES DE BARRIDO (CHI -> WIDTH)
# ==============================================================================

for CHI in "${CHIS[@]}"; do

    # 3.1. Calcular N_BIG y N_SMALL para este CHI específico
    # --------------------------------------------------------------------------
    read N_BIG N_SMALL <<< $(awk -v nref="$N_REF" -v chi="$CHI" -v rb="$R_BIG" -v rs="$R_SMALL" 'BEGIN {
        # Relación de áreas (geométrica)
        ratio_geom = (rb / rs)^2;
        
        # Si Chi es 0 o 1, forzamos enteros exactos para evitar errores de redondeo
        if (chi <= 0.0001) {
            n_big = nref;
            n_small = 0;
        } else if (chi >= 0.9999) {
            n_big = 0;
            n_small = int(nref * ratio_geom);
        } else {
            n_big = int((1.0 - chi) * nref);
            n_small = int(chi * nref * ratio_geom);
        }
        print n_big, n_small
    }')

    CHI_STR="${CHI/./p}" # Formato para nombre de carpeta (0.2 -> 0p2)

    echo "=== Procesando CHI=${CHI} (Big: ${N_BIG}, Small: ${N_SMALL}) ==="

    # 3.2. Bucle interno de Anchos
    # --------------------------------------------------------------------------
    for W in "${WIDTHS[@]}"; do
        
        W_STR="${W/./p}"
        
        # Nombre de carpeta único: Chi_0p2_Width_1p5
        RUNID="Chi_${CHI_STR}_W_${W_STR}" 
        RUN_DIR="${PARENT_DIR}/${RUNID}"
        
        mkdir -p "${RUN_DIR}"
        
        # Generar semilla aleatoria única
        SEED=$(od -vAn -N4 -tu4 < /dev/urandom | tr -d '[:space:]')

        echo "   -> Generando: ${RUNID} (Seed: ${SEED})"

        # Copiamos el template
        cp "${BASE_DIR}/${TEMPLATE_FILE}" "${RUN_DIR}/params.in"

        # --- A. REEMPLAZOS BÁSICOS ---
        sed -i -E \
            -e "s/@RHOLE@/${W}/g" \
            -e "s/@RUNID@/${RUNID}/g" \
            -e "s/@SEED@/${SEED}/g" \
            "${RUN_DIR}/params.in"

        # --- B. INYECCIÓN DE PARTÍCULAS (Manejo de Monodisperso vs Bidisperso) ---
        
        LINEA_BIG="${N_BIG} ${R_BIG} ${PROPS_BIG_REST}"
        LINEA_SMALL="${N_SMALL} ${R_SMALL} 1 ${PHYSICS_SMALL}"

        if [ "$N_SMALL" -gt "0" ] && [ "$N_BIG" -gt "0" ]; then
            # === CASO MEZCLA (CHI 0.1 - 0.9) ===
            sed -i -E "s/noTipoGranos:[[:space:]]*1/noTipoGranos: 2/" "${RUN_DIR}/params.in"
            sed -i -E "s/${SEARCH_PATTERN}/${LINEA_BIG}\n${LINEA_SMALL}/" "${RUN_DIR}/params.in"
            
        elif [ "$N_SMALL" -gt "0" ]; then
            # === CASO SOLO PEQUEÑAS (CHI = 1.0) ===
            # Mantenemos noTipoGranos: 1, pero reemplazamos la línea original con la de las pequeñas
            sed -i -E "s/${SEARCH_PATTERN}/${LINEA_SMALL}/" "${RUN_DIR}/params.in"
            
        else
            # === CASO SOLO GRANDES (CHI = 0.0) ===
            # Mantenemos noTipoGranos: 1 y usamos la línea de grandes calculada (o la original)
            sed -i -E "s/${SEARCH_PATTERN}/${LINEA_BIG}/" "${RUN_DIR}/params.in"
        fi

        # --- C. EJECUCIÓN ---
        (
            cd "${RUN_DIR}"
            "${BASE_DIR}/eo-silo" params.in > log.txt 2>&1
        ) &

        sleep "${DELAY}"
    done
done

echo ">>> ¡Barrido completo finalizado!"