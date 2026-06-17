#!/bin/bash

# --- 1. Leer argumentos ---
MODO=${1:-interactivo}
GEOMETRIA1=${2:-Pent-Disco}
RATIO1=${3:-0.1}
GEOMETRIA2=${4:-none}
RATIO2=${5:-none}
GEOMETRIA3=${6:-none}
RATIO3=${7:-none}
GEOMETRIA4=${8:-none}
RATIO4=${9:-none}

# Disco-Disco, Cuad-Disco, Tri-Disco, Pent-Disco

ARCHIVO_IN="resumen_fuerza_normal_por_configuracion.csv"

# --- Función para determinar el tipo de punto de Gnuplot ---
obtener_puntos() {
    local geom=$1
    if [ "$geom" == "none" ]; then
        echo "7 6"
        return
    fi
    local forma_grande=$(echo "$geom" | cut -d'-' -f1 | tr '[:upper:]' '[:lower:]')

    case "$forma_grande" in
        disco|circ)       echo "7 6"   ;; # Círculos
        cuad|cuadrado)    echo "5 4"   ;; # Cuadrados
        tri|triangulo)    echo "9 8"   ;; # Triángulos hacia arriba
        rombo|diamante)   echo "13 12" ;; # Rombos/Diamantes
        pent|pentagono)   echo "15 14" ;; # Pentágonos
        *)                echo "7 6"   ;; # Círculos por defecto
    esac
}

# Obtener los tipos de puntos para las configuraciones existentes
read PT_LLENO_1 PT_VACIO_1 <<< $(obtener_puntos "$GEOMETRIA1")
[ "$GEOMETRIA2" != "none" ] && read PT_LLENO_2 PT_VACIO_2 <<< $(obtener_puntos "$GEOMETRIA2")
[ "$GEOMETRIA3" != "none" ] && read PT_LLENO_3 PT_VACIO_3 <<< $(obtener_puntos "$GEOMETRIA3")
[ "$GEOMETRIA4" != "none" ] && read PT_LLENO_4 PT_VACIO_4 <<< $(obtener_puntos "$GEOMETRIA4")

# Definir títulos y nombres de archivo dinámicos
if [ "$GEOMETRIA2" != "none" ]; then
    echo "Preparando COMPARACIÓN MÚLTIPLE..."
    ARCHIVO_OUT_PDF="fuerzas_comparacion_multiple.pdf"
    TITULO_GRAFICO="Comparación de Fuerzas Multigeometría"
else
    echo "Preparando datos: $GEOMETRIA1 (Ratio: $RATIO1)..."
    ARCHIVO_OUT_PDF="fuerzas_${GEOMETRIA1}_ratio_${RATIO1}.pdf"
    TITULO_GRAFICO="Desglose de Fuerzas - ${GEOMETRIA1} (Area Ratio ${RATIO1})"
fi

# --- 2. Preparar archivo usando Python+Pandas ---
CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"
CMD_PYTHON="apptainer exec $CONTENEDOR python3"

$CMD_PYTHON -c "
import pandas as pd
import sys

try:
    archivo = sys.argv[1]
    configs = [
        (sys.argv[2], sys.argv[3], 'temp_1.csv', 2),
        (sys.argv[4], sys.argv[5], 'temp_2.csv', 3),
        (sys.argv[6], sys.argv[7], 'temp_3.csv', 4),
        (sys.argv[8], sys.argv[9], 'temp_4.csv', 5)
    ]
    
    df = pd.read_csv(archivo)
    
    for geom, ratio, out_file, exit_code in configs:
        if geom != 'none' and ratio != 'none':
            ratio_val = float(ratio)
            df_sub = df[(df['geometry_label'] == geom) & (df['area_ratio_nominal'] == ratio_val)].copy()
            if df_sub.empty:
                sys.exit(exit_code)
            df_sub.groupby('chi').mean(numeric_only=True).reset_index().sort_values('chi').to_csv(out_file, index=False)
            
except Exception as e:
    print('Error procesando CSV:', e)
    sys.exit(1)
" "$ARCHIVO_IN" "$GEOMETRIA1" "$RATIO1" "$GEOMETRIA2" "$RATIO2" "$GEOMETRIA3" "$RATIO3" "$GEOMETRIA4" "$RATIO4"

# Verificar salidas de Python
PY_STATUS=$?
if [ $PY_STATUS -ne 0 ]; then
    echo "Error en extracción de datos. Código de salida Python: $PY_STATUS"
    rm -f temp_*.csv
    exit 1
fi

# --- 3. Construir comando dinámico de Gnuplot ---
# Config 1
PLOT_CMD="plot 'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_BB\" with linespoints ls 1 title \"${GEOMETRIA1}(${RATIO1}) Arco BB\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_BS\" with linespoints ls 2 title \"${GEOMETRIA1}(${RATIO1}) Arco BS\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_SS\" with linespoints ls 3 title \"${GEOMETRIA1}(${RATIO1}) Arco SS\", \\
         'temp_1.csv' using \"chi\":(column(\"mean_contrib_Fn_arco_BB\") + column(\"mean_contrib_Fn_arco_BS\") + column(\"mean_contrib_Fn_arco_SS\")) with linespoints ls 4 title \"${GEOMETRIA1} SUMA ARCO\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_BB\" with linespoints ls 5 title \"${GEOMETRIA1}(${RATIO1}) ROI BB\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_BS\" with linespoints ls 6 title \"${GEOMETRIA1}(${RATIO1}) ROI BS\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_SS\" with linespoints ls 7 title \"${GEOMETRIA1}(${RATIO1}) ROI SS\", \\
         'temp_1.csv' using \"chi\":(column(\"mean_contrib_Fn_roi_BB\") + column(\"mean_contrib_Fn_roi_BS\") + column(\"mean_contrib_Fn_roi_SS\")) with linespoints ls 8 title \"${GEOMETRIA1} SUMA ROI\""

# Config 2
if [ "$GEOMETRIA2" != "none" ]; then
    PLOT_CMD="${PLOT_CMD}, \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_arco_BB\" with linespoints ls 9 title \"${GEOMETRIA2}(${RATIO2}) Arco BB\", \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_arco_BS\" with linespoints ls 10 title \"${GEOMETRIA2}(${RATIO2}) Arco BS\", \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_arco_SS\" with linespoints ls 11 title \"${GEOMETRIA2}(${RATIO2}) Arco SS\", \\
         'temp_2.csv' using \"chi\":(column(\"mean_contrib_Fn_arco_BB\") + column(\"mean_contrib_Fn_arco_BS\") + column(\"mean_contrib_Fn_arco_SS\")) with linespoints ls 12 title \"${GEOMETRIA2} SUMA ARCO\", \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_roi_BB\" with linespoints ls 13 title \"${GEOMETRIA2}(${RATIO2}) ROI BB\", \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_roi_BS\" with linespoints ls 14 title \"${GEOMETRIA2}(${RATIO2}) ROI BS\", \\
         'temp_2.csv' using \"chi\":\"mean_contrib_Fn_roi_SS\" with linespoints ls 15 title \"${GEOMETRIA2}(${RATIO2}) ROI SS\", \\
         'temp_2.csv' using \"chi\":(column(\"mean_contrib_Fn_roi_BB\") + column(\"mean_contrib_Fn_roi_BS\") + column(\"mean_contrib_Fn_roi_SS\")) with linespoints ls 16 title \"${GEOMETRIA2} SUMA ROI\""
fi

# Config 3
if [ "$GEOMETRIA3" != "none" ]; then
    PLOT_CMD="${PLOT_CMD}, \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_arco_BB\" with linespoints ls 17 title \"${GEOMETRIA3}(${RATIO3}) Arco BB\", \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_arco_BS\" with linespoints ls 18 title \"${GEOMETRIA3}(${RATIO3}) Arco BS\", \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_arco_SS\" with linespoints ls 19 title \"${GEOMETRIA3}(${RATIO3}) Arco SS\", \\
         'temp_3.csv' using \"chi\":(column(\"mean_contrib_Fn_arco_BB\") + column(\"mean_contrib_Fn_arco_BS\") + column(\"mean_contrib_Fn_arco_SS\")) with linespoints ls 20 title \"${GEOMETRIA3} SUMA ARCO\", \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_roi_BB\" with linespoints ls 21 title \"${GEOMETRIA3}(${RATIO3}) ROI BB\", \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_roi_BS\" with linespoints ls 22 title \"${GEOMETRIA3}(${RATIO3}) ROI BS\", \\
         'temp_3.csv' using \"chi\":\"mean_contrib_Fn_roi_SS\" with linespoints ls 23 title \"${GEOMETRIA3}(${RATIO3}) ROI SS\", \\
         'temp_3.csv' using \"chi\":(column(\"mean_contrib_Fn_roi_BB\") + column(\"mean_contrib_Fn_roi_BS\") + column(\"mean_contrib_Fn_roi_SS\")) with linespoints ls 24 title \"${GEOMETRIA3} SUMA ROI\""
fi

# Config 4
if [ "$GEOMETRIA4" != "none" ]; then
    PLOT_CMD="${PLOT_CMD}, \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_arco_BB\" with linespoints ls 25 title \"${GEOMETRIA4}(${RATIO4}) Arco BB\", \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_arco_BS\" with linespoints ls 26 title \"${GEOMETRIA4}(${RATIO4}) Arco BS\", \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_arco_SS\" with linespoints ls 27 title \"${GEOMETRIA4}(${RATIO4}) Arco SS\", \\
         'temp_4.csv' using \"chi\":(column(\"mean_contrib_Fn_arco_BB\") + column(\"mean_contrib_Fn_arco_BS\") + column(\"mean_contrib_Fn_arco_SS\")) with linespoints ls 28 title \"${GEOMETRIA4} SUMA ARCO\", \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_roi_BB\" with linespoints ls 29 title \"${GEOMETRIA4}(${RATIO4}) ROI BB\", \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_roi_BS\" with linespoints ls 30 title \"${GEOMETRIA4}(${RATIO4}) ROI BS\", \\
         'temp_4.csv' using \"chi\":\"mean_contrib_Fn_roi_SS\" with linespoints ls 31 title \"${GEOMETRIA4}(${RATIO4}) ROI SS\", \\
         'temp_4.csv' using \"chi\":(column(\"mean_contrib_Fn_roi_BB\") + column(\"mean_contrib_Fn_roi_BS\") + column(\"mean_contrib_Fn_roi_SS\")) with linespoints ls 32 title \"${GEOMETRIA4} SUMA ROI\""
fi

# --- 4. Configurar Terminal Gnuplot ---
if [ "$MODO" == "pdf" ]; then
    TERM_CONFIG="set terminal pdfcairo size 14,9 enhanced font 'Arial,12'
set output '${ARCHIVO_OUT_PDF}'"
    PAUSE_CMD=""
else
    TERM_CONFIG="set terminal qt size 1200,800 enhanced font 'Arial,10'
set mouse"
    PAUSE_CMD="pause mouse close"
fi

# --- 5. Ejecutar Gnuplot ---
gnuplot <<-EOF
    $TERM_CONFIG
    
    set datafile separator ','
    set datafile columnheaders
    set decimalsign '.'
    
    set xlabel "Chi"
    set ylabel "Aporte a la Fuerza Normal Promedio"
    set title "$TITULO_GRAFICO"
    
    # Ajustamos la leyenda para que no se salga si hay 32 líneas
    set key outside right top font ",9" spacing 0.9 maxrows 16
    
    set xrange[0:0.2]
    
    # ESTILOS CONFIG 1
    set style line 1 lc rgb "red" pt $PT_LLENO_1 ps 0.8 lw 1.5
    set style line 2 lc rgb "forest-green" pt $PT_LLENO_1 ps 0.8 lw 1.5
    set style line 3 lc rgb "blue" pt $PT_LLENO_1 ps 0.8 lw 1.5
    set style line 4 lc rgb "black" pt $PT_LLENO_1 ps 1.2 lw 3
    set style line 5 lc rgb "red" pt $PT_VACIO_1 ps 0.8 lw 1.5 dt 2
    set style line 6 lc rgb "forest-green" pt $PT_VACIO_1 ps 0.8 lw 1.5 dt 2
    set style line 7 lc rgb "blue" pt $PT_VACIO_1 ps 0.8 lw 1.5 dt 2
    set style line 8 lc rgb "gray" pt $PT_VACIO_1 ps 1.2 lw 3 dt 2

    # ESTILOS CONFIG 2
    set style line 9 lc rgb "red" pt ${PT_LLENO_2:-7} ps 0.8 lw 1.5
    set style line 10 lc rgb "forest-green" pt ${PT_LLENO_2:-7} ps 0.8 lw 1.5
    set style line 11 lc rgb "blue" pt ${PT_LLENO_2:-7} ps 0.8 lw 1.5
    set style line 12 lc rgb "black" pt ${PT_LLENO_2:-7} ps 1.2 lw 3
    set style line 13 lc rgb "red" pt ${PT_VACIO_2:-6} ps 0.8 lw 1.5 dt 2
    set style line 14 lc rgb "forest-green" pt ${PT_VACIO_2:-6} ps 0.8 lw 1.5 dt 2
    set style line 15 lc rgb "blue" pt ${PT_VACIO_2:-6} ps 0.8 lw 1.5 dt 2
    set style line 16 lc rgb "gray" pt ${PT_VACIO_2:-6} ps 1.2 lw 3 dt 2

    # ESTILOS CONFIG 3
    set style line 17 lc rgb "red" pt ${PT_LLENO_3:-7} ps 0.8 lw 1.5
    set style line 18 lc rgb "forest-green" pt ${PT_LLENO_3:-7} ps 0.8 lw 1.5
    set style line 19 lc rgb "blue" pt ${PT_LLENO_3:-7} ps 0.8 lw 1.5
    set style line 20 lc rgb "black" pt ${PT_LLENO_3:-7} ps 1.2 lw 3
    set style line 21 lc rgb "red" pt ${PT_VACIO_3:-6} ps 0.8 lw 1.5 dt 2
    set style line 22 lc rgb "forest-green" pt ${PT_VACIO_3:-6} ps 0.8 lw 1.5 dt 2
    set style line 23 lc rgb "blue" pt ${PT_VACIO_3:-6} ps 0.8 lw 1.5 dt 2
    set style line 24 lc rgb "gray" pt ${PT_VACIO_3:-6} ps 1.2 lw 3 dt 2

    # ESTILOS CONFIG 4
    set style line 25 lc rgb "red" pt ${PT_LLENO_4:-7} ps 0.8 lw 1.5
    set style line 26 lc rgb "forest-green" pt ${PT_LLENO_4:-7} ps 0.8 lw 1.5
    set style line 27 lc rgb "blue" pt ${PT_LLENO_4:-7} ps 0.8 lw 1.5
    set style line 28 lc rgb "black" pt ${PT_LLENO_4:-7} ps 1.2 lw 3
    set style line 29 lc rgb "red" pt ${PT_VACIO_4:-6} ps 0.8 lw 1.5 dt 2
    set style line 30 lc rgb "forest-green" pt ${PT_VACIO_4:-6} ps 0.8 lw 1.5 dt 2
    set style line 31 lc rgb "blue" pt ${PT_VACIO_4:-6} ps 0.8 lw 1.5 dt 2
    set style line 32 lc rgb "gray" pt ${PT_VACIO_4:-6} ps 1.2 lw 3 dt 2

    $PLOT_CMD

    $PAUSE_CMD
EOF

# --- 6. Limpieza ---
rm -f temp_1.csv temp_2.csv temp_3.csv temp_4.csv