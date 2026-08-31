#!/bin/bash
# Genera un PDF por cada combinacion (geometry_label, area_ratio_nominal)
# presente en resumen_fuerza_normal_por_configuracion.csv, usando
# plot_fuerza_por_tipo_contacto.sh (Mg, errorbar con SEM pooled, w_salida=2.0).
# Analogo a graficar_todas_configuraciones.sh de forces_old/, adaptado al
# nuevo script/columnas.

ARCHIVO_CSV="resumen_fuerza_normal_por_configuracion.csv"
CARPETA_SALIDA="graficos_fuerzas_pdf"
CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$DIR/$CARPETA_SALIDA"
cd "$DIR" || exit 1

echo "==================================================="
echo " INICIANDO GENERACION MASIVA DE GRAFICOS"
echo "==================================================="

# Combinaciones unicas de geometria+ratio, restringidas a w_salida=2.0
# (excluye COMPARACION-GOLDBERG, igual que hace el propio script de ploteo).
apptainer exec "$CONTENEDOR" python3 -c "
import pandas as pd, numpy as np
df = pd.read_csv('$ARCHIVO_CSV')
df = df[np.isclose(df['w_salida'].astype(float), 2.0, atol=0.01)]
df = df.dropna(subset=['geometry_label', 'area_ratio_nominal'])
pares = df[['geometry_label', 'area_ratio_nominal']].drop_duplicates().sort_values(['geometry_label', 'area_ratio_nominal']).values
for geom, ratio in pares:
    print(f'{geom},{ratio}')
" > combinaciones.tmp

n_total=$(wc -l < combinaciones.tmp)
echo "[+] $n_total combinaciones geometria/ratio encontradas."

n_ok=0
while IFS=, read -r geometria ratio; do
    ./plot_fuerza_por_tipo_contacto.sh pdf "$geometria" "$ratio"

    PDF_GENERADO="fuerzas_por_tipo_${geometria}_ratio_${ratio}.pdf"
    if [ -f "$PDF_GENERADO" ]; then
        mv "$PDF_GENERADO" "$CARPETA_SALIDA/"
        echo "OK: $CARPETA_SALIDA/$PDF_GENERADO"
        n_ok=$((n_ok + 1))
    else
        echo "FALTA: no se genero $PDF_GENERADO (geometria=$geometria ratio=$ratio)"
    fi
done < combinaciones.tmp

rm combinaciones.tmp

echo "==================================================="
echo " PROCESO TERMINADO: $n_ok/$n_total graficos generados en '$CARPETA_SALIDA/'"
echo "==================================================="
