#!/bin/bash

ARCHIVO_CSV="resumen_fuerza_normal_por_configuracion.csv"
CARPETA_SALIDA="graficos_fuerzas_pdf"

# 1. Crear carpeta para guardar los PDFs
mkdir -p "$CARPETA_SALIDA"

echo "==================================================="
echo " INICIANDO GENERACIÓN MASIVA DE GRÁFICOS"
echo "==================================================="

CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"
CMD_PYTHON="apptainer exec $CONTENEDOR python3"



# 2. Usar Python para extraer todas las combinaciones únicas de Geometría y Ratio
$CMD_PYTHON -c "
import pandas as pd
df = pd.read_csv('$ARCHIVO_CSV')
# Filtrar filas que tengan geometría y ratio válidos
df = df.dropna(subset=['geometry_label', 'area_ratio_nominal'])
# Obtener pares únicos
pares = df[['geometry_label', 'area_ratio_nominal']].drop_duplicates().values
for geom, ratio in pares:
    print(f'{geom},{ratio}')
" > combinaciones.tmp

# 3. Leer las combinaciones y llamar al script de Gnuplot en modo PDF
while IFS=, read -r geometria ratio; do
    
    # Ejecutamos graficar_fuerzas.sh en modo pdf
    ./graficar_fuerza.sh pdf "$geometria" "$ratio"
    
    # Movemos el PDF generado a la carpeta de salida
    PDF_GENERADO="fuerzas_${geometria}_ratio_${ratio}.pdf"
    if [ -f "$PDF_GENERADO" ]; then
        mv "$PDF_GENERADO" "$CARPETA_SALIDA/"
        echo "✅ Guardado en $CARPETA_SALIDA/$PDF_GENERADO"
    fi

done < combinaciones.tmp

# 4. Limpieza
rm combinaciones.tmp

echo "==================================================="
echo " PROCESO TERMINADO. Revisa la carpeta '$CARPETA_SALIDA'"
echo "==================================================="