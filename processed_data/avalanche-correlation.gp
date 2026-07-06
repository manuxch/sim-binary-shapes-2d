set terminal qt size 700,700 font "Arial,11"
set datafile separator ","
set title "Mapa de Retorno: Correlación de Tamaños de Avalanchas Consecutivas"
set xlabel "Tamaño de Avalancha Actual, n_t"
set ylabel "Tamaño de Avalancha Siguiente, n_{t+1}"

# Ajuste de escalas logarítmicas en ambos ejes (igual que la Fig 3.b de Zuriguel)
set logscale xy
set grid xtics ytics mxtics mytics

# Mantener la proporción del gráfico cuadrada para evaluar simetría en la diagonal
set size square

# Filtrar para una simulación específica
target_hash = "edb58a19dfc2"
cmd_esqueleto = sprintf("< grep '%s' /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv", target_hash)

# Inicializar la variable que guardará el estado de la fila anterior
old = NaN

# El truco:
# En el eje X evaluamos la expresión (val = old, old = $6, val). 
# Esto guarda el valor anterior en 'val', actualiza 'old' con el valor de la fila presente ($6), y devuelve 'val'.
# El eje Y simplemente grafica el valor actual ($6).
plot cmd_esqueleto using (val = old, old = $6, val):6 with points pt 6 lc rgb "dark-red" title "Datos de simulación", \
     x with lines lt 2 lc rgb "gray" title "Línea de identidad (n_t = n_{t+1})"