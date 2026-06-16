#!/bin/bash

# --- 1. Leer argumentos ---
MODO=${1:-interactivo}
GEOMETRIA1=${2:-Pent-Disco}
RATIO1=${3:-0.1}
GEOMETRIA2=${4:-Disco-Disco}  # Si pasas 'none', solo grafica la Configuración 1
RATIO2=${5:-0.1}

ARCHIVO_IN="resumen_fuerza_normal_por_configuracion.csv"

# Definir títulos y nombres de archivo dinámicos
if [ "$GEOMETRIA2" != "none" ] && [ "$RATIO2" != "none" ]; then
    echo "Preparando COMPARACIÓN: $GEOMETRIA1 ($RATIO1) vs $GEOMETRIA2 ($RATIO2)..."
    ARCHIVO_OUT_PDF="fuerzas_${GEOMETRIA1}_${RATIO1}_vs_${GEOMETRIA2}_${RATIO2}.pdf"
    TITULO_GRAFICO="Comparación de Fuerzas: ${GEOMETRIA1} (${RATIO1}) vs ${GEOMETRIA2} (${RATIO2})"
else
    echo "Preparando datos: $GEOMETRIA1 (Ratio: $RATIO1)..."
    ARCHIVO_OUT_PDF="fuerzas_${GEOMETRIA1}_ratio_${RATIO1}.pdf"
    TITULO_GRAFICO="Desglose de Fuerzas - ${GEOMETRIA1} (Area Ratio ${RATIO1})"
fi

# --- 2. Preparar archivo usando Python+Pandas ---
python3 -c "
import pandas as pd
import sys

try:
    archivo = sys.argv[1]
    geom1 = sys.argv[2]
    ratio1 = float(sys.argv[3])
    geom2 = sys.argv[4]
    ratio2 = sys.argv[5]
    
    df = pd.read_csv(archivo)
    
    # Procesar Configuración 1
    df1 = df[(df['geometry_label'] == geom1) & (df['area_ratio_nominal'] == ratio1)].copy()
    if df1.empty:
        sys.exit(2)
    df1.groupby('chi').mean(numeric_only=True).reset_index().sort_values('chi').to_csv('temp_1.csv', index=False)
    
    # Procesar Configuración 2 (si existe)
    if geom2 != 'none' and ratio2 != 'none':
        ratio2 = float(ratio2)
        df2 = df[(df['geometry_label'] == geom2) & (df['area_ratio_nominal'] == ratio2)].copy()
        if df2.empty:
            sys.exit(3)
        df2.groupby('chi').mean(numeric_only=True).reset_index().sort_values('chi').to_csv('temp_2.csv', index=False)
        
except Exception as e:
    print('Error procesando CSV:', e)
    sys.exit(1)
" "$ARCHIVO_IN" "$GEOMETRIA1" "$RATIO1" "$GEOMETRIA2" "$RATIO2"

# Verificar salidas de Python
PY_STATUS=$?
if [ $PY_STATUS -eq 2 ]; then
    echo "  -> Error: No hay datos para la Configuración 1 ($GEOMETRIA1, $RATIO1)."
    exit 1
elif [ $PY_STATUS -eq 3 ]; then
    echo "  -> Error: No hay datos para la Configuración 2 ($GEOMETRIA2, $RATIO2)."
    rm -f temp_1.csv
    exit 1
elif [ $PY_STATUS -eq 1 ]; then
    echo "  -> Error crítico en Python."
    exit 1
fi

# --- 3. Construir comando dinámico de Gnuplot ---
# Comando para la Config 1
PLOT_CMD="plot 'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_BB\" with linespoints ls 1 title \"${GEOMETRIA1}(${RATIO1}) Arco BB\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_BS\" with linespoints ls 2 title \"${GEOMETRIA1}(${RATIO1}) Arco BS\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_arco_SS\" with linespoints ls 3 title \"${GEOMETRIA1}(${RATIO1}) Arco SS\", \\
         'temp_1.csv' using \"chi\":(column(\"mean_contrib_Fn_arco_BB\") + column(\"mean_contrib_Fn_arco_BS\") + column(\"mean_contrib_Fn_arco_SS\")) with linespoints ls 4 title \"${GEOMETRIA1} SUMA ARCO\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_BB\" with linespoints ls 5 title \"${GEOMETRIA1}(${RATIO1}) ROI BB\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_BS\" with linespoints ls 6 title \"${GEOMETRIA1}(${RATIO1}) ROI BS\", \\
         'temp_1.csv' using \"chi\":\"mean_contrib_Fn_roi_SS\" with linespoints ls 7 title \"${GEOMETRIA1}(${RATIO1}) ROI SS\", \\
         'temp_1.csv' using \"chi\":(column(\"mean_contrib_Fn_roi_BB\") + column(\"mean_contrib_Fn_roi_BS\") + column(\"mean_contrib_Fn_roi_SS\")) with linespoints ls 8 title \"${GEOMETRIA1} SUMA ROI\""

# Si existe Config 2, añadimos sus líneas al comando
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

# --- 4. Configurar Terminal Gnuplot ---
if [ "$MODO" == "pdf" ]; then
    TERM_CONFIG="set terminal pdfcairo size 12,8 enhanced font 'Arial,12'
set output '${ARCHIVO_OUT_PDF}'"
    PAUSE_CMD=""
else
    # wxt soluciona el problema de estirar la ventana en Linux/GTK
    TERM_CONFIG="set terminal qt size 1100,750 enhanced font 'Arial,10'
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
    
    set key outside right top
    
    # ESTILOS CONFIG 1 (Círculos: pt 7 y pt 6)
    set style line 1 lc rgb "red" pt 7 ps 0.8 lw 1.5
    set style line 2 lc rgb "forest-green" pt 7 ps 0.8 lw 1.5
    set style line 3 lc rgb "blue" pt 7 ps 0.8 lw 1.5
    set style line 4 lc rgb "black" pt 7 ps 1.2 lw 3
    set style line 5 lc rgb "red" pt 6 ps 0.8 lw 1.5 dt 2
    set style line 6 lc rgb "forest-green" pt 6 ps 0.8 lw 1.5 dt 2
    set style line 7 lc rgb "blue" pt 6 ps 0.8 lw 1.5 dt 2
    set style line 8 lc rgb "gray" pt 6 ps 1.2 lw 3 dt 2

    # ESTILOS CONFIG 2 (Cuadrados: pt 5 y pt 4)
    set style line 9 lc rgb "red" pt 5 ps 0.8 lw 1.5
    set style line 10 lc rgb "forest-green" pt 5 ps 0.8 lw 1.5
    set style line 11 lc rgb "blue" pt 5 ps 0.8 lw 1.5
    set style line 12 lc rgb "black" pt 5 ps 1.2 lw 3
    set style line 13 lc rgb "red" pt 4 ps 0.8 lw 1.5 dt 2
    set style line 14 lc rgb "forest-green" pt 4 ps 0.8 lw 1.5 dt 2
    set style line 15 lc rgb "blue" pt 4 ps 0.8 lw 1.5 dt 2
    set style line 16 lc rgb "gray" pt 4 ps 1.2 lw 3 dt 2

    $PLOT_CMD

    $PAUSE_CMD
EOF

# --- 6. Limpieza ---
rm -f temp_1.csv temp_2.csv