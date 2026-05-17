#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Empaquetado limpio de simulaciones por geometría
# - No modifica los datos originales
# - Excluye únicamente frm_*.xy
# - Genera .tar.xz
# - Borra STAGING_ROOT al finalizar
# ============================================================

BASE_DIR="${1:-$(pwd)}"
STAGING_ROOT="${BASE_DIR}/paquetes_limpios"
OUTPUT_DIR="${BASE_DIR}/paquetes_comprimidos"

declare -A GRUPOS=(
  ["TRIANGULOS"]="MEZCLA_TRIANGLE_DISK"
  ["CUADRADOS"]="MEZCLA_SQUARE_DISK"
  ["PENTAGONOS"]="MEZCLA_PENTAGON_DISK"
)

mkdir -p "${OUTPUT_DIR}"

echo "============================================================"
echo "Empaquetado limpio de simulaciones"
echo "BASE_DIR      = ${BASE_DIR}"
echo "STAGING_ROOT  = ${STAGING_ROOT}"
echo "OUTPUT_DIR    = ${OUTPUT_DIR}"
echo "Formato       = .tar.xz"
echo "============================================================"

# Limpieza preventiva del staging
rm -rf "${STAGING_ROOT}"
mkdir -p "${STAGING_ROOT}"

for NOMBRE_GRUPO in TRIANGULOS CUADRADOS PENTAGONOS; do
    SRC_DIR="${BASE_DIR}/${GRUPOS[$NOMBRE_GRUPO]}"
    CLEAN_DIR="${STAGING_ROOT}/${NOMBRE_GRUPO}"
    TAR_FILE="${OUTPUT_DIR}/${NOMBRE_GRUPO}.tar.xz"

    echo
    echo "------------------------------------------------------------"
    echo "Procesando grupo: ${NOMBRE_GRUPO}"
    echo "Origen:      ${SRC_DIR}"
    echo "Copia limpia:${CLEAN_DIR}"
    echo "Salida:      ${TAR_FILE}"
    echo "------------------------------------------------------------"

    if [[ ! -d "${SRC_DIR}" ]]; then
        echo "AVISO: no existe ${SRC_DIR}. Se omite este grupo."
        continue
    fi

    rm -rf "${CLEAN_DIR}"
    mkdir -p "${CLEAN_DIR}"

    rsync -a \
        --exclude='frm_*.xy' \
        "${SRC_DIR}/" "${CLEAN_DIR}/"

    TOTAL_FRM_ORIG=$(find "${SRC_DIR}" -type f -name 'frm_*.xy' | wc -l)
    TOTAL_FRM_CLEAN=$(find "${CLEAN_DIR}" -type f -name 'frm_*.xy' | wc -l)
    TOTAL_FILES_CLEAN=$(find "${CLEAN_DIR}" -type f | wc -l)

    echo "frm_*.xy en origen:      ${TOTAL_FRM_ORIG}"
    echo "frm_*.xy en copia limpia:${TOTAL_FRM_CLEAN}"
    echo "archivos copiados:       ${TOTAL_FILES_CLEAN}"

    rm -f "${TAR_FILE}"
    tar -cJf "${TAR_FILE}" -C "${STAGING_ROOT}" "${NOMBRE_GRUPO}"

    echo "OK: comprimido generado en ${TAR_FILE}"
done

echo
echo "Limpiando staging..."
rm -rf "${STAGING_ROOT}"

echo "============================================================"
echo "Proceso finalizado."
echo "Los archivos quedaron en: ${OUTPUT_DIR}"
echo "El staging fue eliminado."
echo "============================================================"