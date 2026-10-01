#!/bin/bash

# =====================================================================
# CONFIGURACIÓN: Elige qué dos cosas quieres comparar aquí
# =====================================================================

# Configuración 1 (Líneas Sólidas)
FILE1="filtrado_disco_disco.csv"
TAM1="0.1"
LABEL1="Disco"
PT_ARCO1=7  # Círculo lleno
PT_ROI1=6   # Círculo vacío

# Configuración 2 (Líneas Discontinuas / Dashed)
FILE2="filtrado_cuadrados_disco.csv"
TAM2="0.1"
LABEL2="Cuadrado"
PT_ARCO2=5  # Cuadrado lleno
PT_ROI2=4   # Cuadrado vacío

# Nombre del archivo PDF de salida
OUTPUT_PDF="comparativa_${LABEL1}_vs_${LABEL2}_area_${TAM1}.pdf"

# =====================================================================
# PROCESAMIENTO Y GRAFICACIÓN (No necesitas tocar esto)
# =====================================================================

# Verificar que ambos archivos existan
if [ ! -f "$FILE1" ] || [ ! -f "$FILE2" ]; then
    echo "⚠️ Error: Uno o ambos archivos CSV no existen en esta carpeta."
    exit 1
fi

echo "📊 Generando comparativa en PDF: $OUTPUT_PDF ..."

gnuplot <<-EOF
    # Configuramos un tamaño un poco más ancho (6.5 x 4.5) para dar espacio a la leyenda
    set terminal pdfcairo size 6.5,4.5 enhanced font 'Arial,10'
    set output '$OUTPUT_PDF'
    set datafile separator ','
    
    set xlabel 'Chi'
    set ylabel 'Fuerza'
    
    # Título dinámico sin interpretar guiones bajos
    set title 'Comparativa de Fuerzas: $LABEL1 (area=$TAM1) vs $LABEL2 (area=$TAM2)' noenhanced
    
    # Colocar la leyenda fuera a la derecha para que no tape las curvas
    set key outside right enhanced vertical samplen 3
    
    # Filtros para AWK
    datos1="< awk -F, '\$3==$TAM1' $FILE1"
    datos2="< awk -F, '\$3==$TAM2' $FILE2"
    
    # Definición de colores base estilo tu gráfico anterior
    c_fn_arco = '#9400D3'  # Morado
    c_ft_arco = '#008B45'  # Verde oscuro
    c_fn_roi  = '#1E90FF'  # Azul claro
    c_ft_roi  = '#FF8C00'  # Naranja
    
    # Graficamos las 8 curvas superpuestas
    # dt 1 = Línea sólida, dt 2 = Línea de trazo (dashed)
    plot datos1 using 5:22 smooth unique with linespoints pt $PT_ARCO1 ps 0.7 dt 1 lc rgb c_fn_arco title 'Fn Arco ($LABEL1)', \
         datos1 using 5:27 smooth unique with linespoints pt $PT_ARCO1 ps 0.7 dt 1 lc rgb c_ft_arco title 'Ft Arco ($LABEL1)', \
         datos1 using 5:30 smooth unique with linespoints pt $PT_ROI1  ps 0.7 dt 1 lc rgb c_fn_roi  title 'Fn ROI ($LABEL1)', \
         datos1 using 5:33 smooth unique with linespoints pt $PT_ROI1  ps 0.7 dt 1 lc rgb c_ft_roi  title 'Ft ROI ($LABEL1)', \
         datos2 using 5:22 smooth unique with linespoints pt $PT_ARCO2 ps 0.7 dt 2 lc rgb c_fn_arco title 'Fn Arco ($LABEL2)', \
         datos2 using 5:27 smooth unique with linespoints pt $PT_ARCO2 ps 0.7 dt 2 lc rgb c_ft_arco title 'Ft Arco ($LABEL2)', \
         datos2 using 5:30 smooth unique with linespoints pt $PT_ROI2  ps 0.7 dt 2 lc rgb c_fn_roi  title 'Fn ROI ($LABEL2)', \
         datos2 using 5:33 smooth unique with linespoints pt $PT_ROI2  ps 0.7 dt 2 lc rgb c_ft_roi  title 'Ft ROI ($LABEL2)'
EOF

echo "✅ ¡Gráfico comparativo generado con éxito!"
