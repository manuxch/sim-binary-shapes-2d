#!/bin/bash
# Habilitar la expansión de alias en el script
shopt -s expand_aliases
# Cargar tu configuración de usuario (ajusta la ruta si usas otro archivo, como .bash_aliases)
source ~/.bashrc

# 1. Define aquí los valores de area-ratio que quieres analizar, separados por espacio:
for AR in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0; do

  # 2. Reemplaza automáticamente el punto por una 'p' para el nombre de la carpeta (ej: 0.1 se vuelve 0p1)
  SUFIJO_CARPETA="${AR//./p}"
  RUTA_SALIDA="../processed_data/resultados_disco_ar${SUFIJO_CARPETA}"

  echo "=========================================================="
  echo "🚀 Iniciando procesamiento para Area Ratio: $AR"
  echo "📁 Carpeta de salida: $RUTA_SALIDA"
  echo "=========================================================="

  # 3. Ejecuta el script inyectando las variables
  python-contenedor force_arch_v2.py \
    --idx ../master_sim_index.csv \
    --out "$RUTA_SALIDA" \
    --geometry-label "Disco-Disco" \
    --area-ratio "$AR" \
    --roi-xmin -3.5 \
    --roi-xmax 3.5 \
    --roi-ymin 0.0 \
    --roi-ymax 5.0 \
    --verbose-filters \
    --workers 0

done

echo "✅ ¡Todas las simulaciones han sido procesadas!"
