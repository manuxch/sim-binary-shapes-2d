# Raiz del repo (correr gnuplot desde cualquier carpeta dentro del repo)
REPO = system("git rev-parse --show-toplevel")

set terminal qt size 800,600 font "Arial,11"
set datafile separator ","
set title "Tamaño de Avalancha vs Tortuosidad del Arco"
set xlabel "Tortuosidad"
set ylabel "Tamaño de Avalancha (total_mix)"
set grid

# Definimos el hash del experimento específico que quieras analizar
target_hash = "85bba77841e4"

# Comando en tubería (pipe) para combinar los archivos sobre la marcha y filtrar por el experimento
cmd = sprintf("< paste -d, ".REPO."/processed_data/1_avalanche_data/resultados_completos_arcos.csv ".REPO."/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv | grep '%s'", target_hash)

# Graficar Tortuosidad (Columna 23) vs Tamaño de Avalancha (Columna 31)
plot cmd using 23:31 with points pt 7 lc rgb "blue" title sprintf("Simulación: %s", target_hash)