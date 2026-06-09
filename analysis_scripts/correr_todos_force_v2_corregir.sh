#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

# =============================================================================
# CONFIGURACIÓN DE ARCHIVOS Y DIRECTORIOS
# =============================================================================
# Reemplaza "tu_indice.csv" con el nombre real de tu archivo de índice
IDX_FILE="tu_indice.csv" 

# Directorios de salida para cada etapa
OUT_DIR_IMG="resultados_visuales"
OUT_DIR_FULL="resultados_completos_estadistica"

# Script de Python a ejecutar
PYTHON_SCRIPT="force_arch_v2.py"

echo "====================================================================="
echo " INICIANDO PIPELINE DE ANÁLISIS DE FUERZAS EN SISTEMAS GRANULARES"
echo "====================================================================="

# =============================================================================
# ETAPA 1: Muestreo visual (Todas las configs, max 5 atascos, guarda imágenes)
# =============================================================================
echo ""
echo "[ETAPA 1/2] Ejecutando pasada visual rápida..."
echo " - Límite: 5 atascos por simulación"
echo " - Imágenes: ACTIVADAS"
echo " - Destino: $OUT_DIR_IMG"

python3 "$PYTHON_SCRIPT" \
    --idx "$IDX_FILE" \
    --out "$OUT_DIR_IMG" \
    --save-images \
    --max-jams-per-sim 5 \
    --overwrite

echo "[✓] Etapa 1 completada con éxito."

# =============================================================================
# ETAPA 2: Análisis completo (Todas las configs, todos los atascos, sin imágenes)
# =============================================================================
echo ""
echo "[ETAPA 2/2] Ejecutando análisis estadístico completo..."
echo " - Límite: SIN LÍMITE (Todos los atascos)"
echo " - Imágenes: DESACTIVADAS"
echo " - Destino: $OUT_DIR_FULL"

python3 "$PYTHON_SCRIPT" \
    --idx "$IDX_FILE" \
    --out "$OUT_DIR_FULL" \
    --overwrite

echo ""
echo "[✓] Etapa 2 completada con éxito."
echo "====================================================================="
echo " PROCESAMIENTO FINALIZADO"
echo "====================================================================="