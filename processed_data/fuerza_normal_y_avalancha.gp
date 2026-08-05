set terminal qt size 800,600 font "Arial,11"
set datafile separator ","
set title "Fuerza Normal del Arco vs. Tamaño de Avalancha Previo"
set xlabel "Tamaño de Avalancha Previo (n_{t-1})"
set ylabel "Fuerza Normal del Arco"

# Escalas y grilla (puedes ajustar logscale según la dispersión de tus datos)
set logscale x
set grid xtics ytics mxtics mytics

# Definir el hash del experimento específico a analizar
target_hash = "85bba77841e4"

# Comando en tubería (pipe) para combinar los archivos de arcos y esqueleto, filtrando por hash
cmd = sprintf("< paste -d, /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv | grep '%s'", target_hash)

# Inicializar la variable que almacenará el tamaño de avalancha anterior
old = NaN

# Explicación del 'using':
# 1. Eje X: (val = old, old = $COL_AVALANCHA, val) -> Guarda el valor previo en 'val', actualiza 'old' con el valor actual y grafica 'val' (el anterior).
# 2. Eje Y: COL_FUERZA -> Fuerza normal del arco correspondiente a ese mismo evento.
# (Reemplaza COL_AVALANCHA y COL_FUERZA por los números de columna reales tras el 'paste')
plot cmd using (val = old, old = $31, val):15 with points pt 7 lc rgb "dark-red" title sprintf("Simulación: %s", target_hash)