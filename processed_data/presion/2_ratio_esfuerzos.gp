set terminal pngcairo size 800,600 enhanced font 'Arial,12'
set output '2_concentracion_esfuerzos.png'

set datafile separator ","

set title "Concentración de Esfuerzos: Arco vs Bulk" font ",14"
set xlabel "Fracción de partículas pequeñas ({/Symbol c})"
set ylabel "Ratio P_{arco} / P_{bulk}"
set grid

# Aquí calculamos el ratio matemáticamente en el vuelo (mean_P_arco / mean_P_bulk)
plot "resumen_presion_por_configuracion.csv" \
     using (stringcolumn("forma_chica") eq "Cuadrado" ? column("chi") : NaN):(column("mean_P_arco")/column("mean_P_bulk")) \
     with linespoints lw 2 pt 7 ps 1.5 lc rgb "red" title "P_{arco} / P_{bulk} (Cuadrados)"