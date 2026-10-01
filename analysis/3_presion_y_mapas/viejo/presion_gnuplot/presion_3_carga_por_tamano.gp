set terminal pngcairo size 800,600 enhanced font 'Arial,12'
set output '3_carga_por_tamano_arco.png'

set datafile separator ","

set title "Distribución de Carga en el Arco: Grandes vs Pequeñas" font ",14"
set xlabel "Fracción de partículas pequeñas ({/Symbol c})"
set ylabel "Presión Promedio Soportada"
set grid
set key top left

# Ploteamos dos series usando el mismo archivo.
# Una para grandes (mean_P_arco_B) y otra para chicas (mean_P_arco_S)
plot "resumen_presion_por_configuracion.csv" \
     using (stringcolumn("forma_chica") eq "Cuadrado" ? column("chi") : NaN):(column("mean_P_arco_B")) \
     with linespoints lw 2 pt 7 ps 1.5 lc rgb "dark-blue" title "Partículas Grandes", \
     "resumen_presion_por_configuracion.csv" \
     using (stringcolumn("forma_chica") eq "Cuadrado" ? column("chi") : NaN):(column("mean_P_arco_S")) \
     with linespoints lw 2 pt 5 ps 1.5 lc rgb "dark-orange" title "Partículas Pequeñas"