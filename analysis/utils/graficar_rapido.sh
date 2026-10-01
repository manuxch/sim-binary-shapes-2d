#!/bin/bash

# Valores por defecto
CSV="presion_por_particula.csv"
OUT="presion_atasco.svg"

# Parsear los mismos argumentos que usa el script de Python para mantener la costumbre
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --csv) CSV="$2"; shift ;;
        --sim_path) SIM_PATH="$2"; shift ;;
        --jam_id) JAM_ID="$2"; shift ;;
        --out) OUT="$2"; shift ;;
        *) echo "Parámetro desconocido: $1"; exit 1 ;;
    esac
    shift
done

if [ -z "$SIM_PATH" ] || [ -z "$JAM_ID" ]; then
    echo "Error: Faltan argumentos requeridos."
    echo "Uso: ./graficar_rapido.sh --csv archivo.csv --sim_path /ruta/... --jam_id 95 --out salida.svg"
    exit 1
fi

# Rellenar el jam_id con ceros a la izquierda (ej: 95 -> 00095)
JAM_ID_PADDED=$(printf "%05d" "$JAM_ID")

# Crear un archivo temporal nativo de forma segura
TEMP_CSV=$(mktemp)

echo "⏳ Extrayendo datos para jam_id=$JAM_ID_PADDED..."

# 1. Extraer el encabezado del CSV
head -n 1 "$CSV" > "$TEMP_CSV"

# 2. Filtrar a máxima velocidad usando grep optimizado de C (LC_ALL=C).
# Usamos -F para buscar la cadena de texto exacta en lugar de expresiones regulares.
LC_ALL=C grep -F "$SIM_PATH" "$CSV" | LC_ALL=C grep -F "$JAM_ID_PADDED" >> "$TEMP_CSV"

# 3. Comprobar si se encontraron resultados
LINEAS=$(wc -l < "$TEMP_CSV")
if [ "$LINEAS" -le 1 ]; then
    echo "❌ Error: No se encontraron datos para esa combinación."
    rm -f "$TEMP_CSV"
    exit 1
fi

echo "✅ Datos filtrados ($((LINEAS - 1)) partículas). Generando gráfico..."


CONTENEDOR="${CONTENEDOR:-/home/juli/work/lab/containers/workstation_full.sif}"  # se puede cambiar con: export CONTENEDOR=/ruta/al.sif
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"




# 4. Ejecutar el script original sobre el CSV temporal que pesa solo unos kilobytes.
apptainer exec "$CONTENEDOR" python3 "$DIR/../3_presion_y_mapas/graficar_presion_atasco.py"     --csv "$TEMP_CSV"     --sim_path "$SIM_PATH"     --jam_id "$JAM_ID"     --out "$OUT"

# 5. Limpiar el entorno eliminando el temporal
rm -f "$TEMP_CSV"
echo "🎉 ¡Gráfico guardado en $OUT!"