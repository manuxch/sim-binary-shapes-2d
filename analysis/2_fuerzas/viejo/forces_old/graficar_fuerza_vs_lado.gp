# ====================================================================
# SCRIPT: SUPERPOSICIÓN DE DATOS (BULK VS ARCO) POR GEOMETRÍA
# ====================================================================
set datafile separator ","

# --- 1. CONFIGURACIÓN DE FILTROS ---
target_area = 0.1
target_chi = 0.2
eps = 1e-4             # Tolerancia para flotantes

# --- 2. CONFIGURACIÓN DE LA PANTALLA Y EJES ---
set xtics ("Disco" 1, "Triangulo" 2, "Cuadrado" 3, "Pentágono" 4)
set xrange [0:5]
set yrange [* : *]     
set title sprintf("Fuerza Normal Promedio (Bulk vs Arco)\nÁrea = %g | Chi = %g", target_area, target_chi) font ",12"
set xlabel "Forma Geométrica" font ",11"
set ylabel "Fuerza Normal Promedio" font ",11"
set grid

# --- 3. CÁLCULO DE PROMEDIOS (BULK EN COL 15 | ARCO EN COL 22) ---

# --- DISCO ---
undefine STATS_mean
stats "filtrado_disco_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Disco") > 0 ? column(15) : 1/0) nooutput
mean_disco_bulk = (exists("STATS_mean")) ? STATS_mean : NaN

undefine STATS_mean
stats "filtrado_disco_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Disco") > 0 ? column(22) : 1/0) nooutput
mean_disco_arco = (exists("STATS_mean")) ? STATS_mean : NaN


# --- CUADRADO ---
undefine STATS_mean
stats "filtrado_cuadrados_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Cuad") > 0 ? column(15) : 1/0) nooutput
mean_cuadrado_bulk = (exists("STATS_mean")) ? STATS_mean : NaN

undefine STATS_mean
stats "filtrado_cuadrados_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Cuad") > 0 ? column(22) : 1/0) nooutput
mean_cuadrado_arco = (exists("STATS_mean")) ? STATS_mean : NaN


# --- TRIÁNGULO ---
undefine STATS_mean
stats "filtrado_triangulos_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Tri") > 0 ? column(15) : 1/0) nooutput
mean_triangulo_bulk = (exists("STATS_mean")) ? STATS_mean : NaN

undefine STATS_mean
stats "filtrado_triangulos_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Tri") > 0 ? column(22) : 1/0) nooutput
mean_triangulo_arco = (exists("STATS_mean")) ? STATS_mean : NaN


# --- PENTÁGONO ---
undefine STATS_mean
stats "filtrado_pentagonos_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Pent") > 0 ? column(15) : 1/0) nooutput
mean_pentagono_bulk = (exists("STATS_mean")) ? STATS_mean : NaN

undefine STATS_mean
stats "filtrado_pentagonos_disco.csv" using (abs(column(3)-target_area) < eps && abs(column(5)-target_chi) < eps && strstrt(strcol(2), "Pent") > 0 ? column(22) : 1/0) nooutput
mean_pentagono_arco = (exists("STATS_mean")) ? STATS_mean : NaN


# --- 4. BLOQUE DE DATOS INTERNO Y MAPEOS ---
$BLOQUE_PROMEDIOS << EOD
1
2
3
4
EOD

obtener_bulk(x) = (x == 1) ? mean_disco_bulk : \
                  (x == 2) ? mean_triangulo_bulk : \
                  (x == 3) ? mean_cuadrado_bulk : \
                  (x == 4) ? mean_pentagono_bulk : NaN

obtener_arco(x) = (x == 1) ? mean_disco_arco : \
                  (x == 2) ? mean_triangulo_arco : \
                  (x == 3) ? mean_cuadrado_arco : \
                  (x == 4) ? mean_pentagono_arco : NaN


# --- 5. COMANDO PARA GRAFICAR SUPERPUESTO ---
# Separamos ambas series con una coma "," para dibujarlas juntas.
# pt 7 = Círculo relleno (Bulk) | pt 9 = Cuadrado relleno (Arco)

plot $BLOQUE_PROMEDIOS using 1:(obtener_bulk($1)) with points pt 7 ps 2 lc rgb "#e74c3c" title "Bulk (Col 15)", \
     $BLOQUE_PROMEDIOS using 1:(obtener_arco($1)) with points pt 9 ps 2 lc rgb "#3498db" title "Arco (Col 22)"