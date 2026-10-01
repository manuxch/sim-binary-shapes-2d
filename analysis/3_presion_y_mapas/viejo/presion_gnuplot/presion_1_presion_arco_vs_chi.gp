set terminal qt size 800,600 enhanced font 'Arial,12' persist
set datafile separator ","

set title "Presión en Arco: Grandes vs Chicas (Cuadrados)" font ",14"
set xlabel "Fracción de partículas pequeñas ({/Symbol c})"
set ylabel "Presión Promedio (P_{arco})"
set grid ytics xtics
set key bottom right

# Definimos el filtro de AWK para los cuadrados
FILTER = "< awk -F',' '$1==\"Disco\" && $2==\"Disco\" && $4<0.18'"

# Graficamos ambas columnas simultáneamente
plot FILTER." resumen_presion_por_configuracion.csv" using 3:11 smooth unique with linespoints lw 2 pt 7 title "Grandes (P_arco_B)", \
     FILTER." resumen_presion_por_configuracion.csv" using 3:12 smooth unique with linespoints lw 2 pt 5 title "Chicas (P_arco_S)"