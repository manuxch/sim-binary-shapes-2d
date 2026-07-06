# Configuración del terminal y formato
set terminal qt size 800,600 font "Arial,11"
set datafile separator ","
set title "Evolución de la Fuerza Normal Bulk en función de Chi"
set xlabel "Chi (χ)"
set ylabel "Fuerza Normal Bulk (Media +/- Desviación Estándar)"

set xrange [0:1]  # Ajusta según el rango de chi que desees mostrar

# Definir estilos de línea y puntos para cada geometría
set style line 1 lc rgb "#E41A1C" lw 2 pt 7 ps 1.2  # Rojo para Cuadrado
set style line 2 lc rgb "#377EB8" lw 2 pt 5 ps 1.2  # Azul para Triángulo
set style line 3 lc rgb "#4DAF4A" lw 2 pt 9 ps 1.2  # Verde para Disco
set style line 4 lc rgb "#4DAF4A" lw 2 pt 9 ps 1.2  # Verde para Disco

# Graficamos usando yerrorlines (puntos con barras de error conectados por líneas)
# Filtramos simultáneamente por la forma (Columna 7) y por r_ratio_nominal (Columna 4)
plot "forces/resumen_fuerza_normal_por_configuracion.csv" using ( $7 == 4 && $3 == 0.1 ? $5 : 1/0 ):15:($15-$16):($15+$16) with yerrorlines ls 1 title "Cuadrado", \
     "forces/resumen_fuerza_normal_por_configuracion.csv" using ( $7 == 3 && $3 == 0.1 ? $5 : 1/0 ):15:($15-$16):($15+$16) with yerrorlines ls 2 title "Triángulo", \
     "forces/resumen_fuerza_normal_por_configuracion.csv" using ( $7 == 5 && $3 == 0.1 ? $5 : 1/0 ):15:($15-$16):($15+$16) with yerrorlines ls 4 title "Pentagono", \
     "forces/resumen_fuerza_normal_por_configuracion.csv" using ( $7 == 1 && $3 == 0.1 ? $5 : 1/0 ):15:($15-$16):($15+$16) with yerrorlines ls 3 title "Disco"