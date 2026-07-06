set terminal qt size 800,600 font "Arial,11"
set datafile separator ","
set title "Tamaño de Avalancha vs Tortuosidad del Arco"
set xlabel "Tortuosidad"
set ylabel "Tamaño de Avalancha (total_mix)"
set grid

# Definimos el hash del experimento específico que quieras analizar
target_hash = "edb58a19dfc2"

# Comando en tubería (pipe) para combinar los archivos sobre la marcha y filtrar por el experimento
cmd = sprintf("< paste -d, sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv | grep '%s'", target_hash)

# Graficar Tortuosidad (Columna 23) vs Tamaño de Avalancha (Columna 31)
plot cmd using 23:31 with points pt 7 lc rgb "blue" title sprintf("Simulación: %s", target_hash)