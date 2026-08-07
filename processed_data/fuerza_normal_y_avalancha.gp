set terminal qt size 800,600 font "Arial,11"
set datafile separator ","
set title "Fuerza Normal del Arco vs. Tamaño de Avalancha Previo"



# 1. Definimos la simulación - Discos (Disco-Disco)
#target_hash_chi_00 = "07d2ba88b922"
#target_hash_chi_02 = "376ffcf511ce"
# Nota: Para Disco-Disco con area_ratio 0.1 no hay chi mayores a 0.2 en el dataset
# target_hash_chi_04 = ""
# target_hash_chi_06 = ""

# 2. Definimos la simulación - Triangulos (Triangulo-Disco)
#target_hash_chi_00 = "cae41fa55054"
#target_hash_chi_02 = "1da42fea31a0"
#target_hash_chi_04 = "9f68d60fd6af"
#target_hash_chi_06 = "ef398b05bd75"

# 3. Definimos la simulación - Cuadrados (Cuadrado-Disco)
target_hash_chi_00 = "edb58a19dfc2"
target_hash_chi_02 = "070dc76dade3"
target_hash_chi_04 = "c4a075849a66"
target_hash_chi_06 = "5f019851509c"

# 4. Definimos la simulación - Pentagonos (Pentagono-Disco)
#target_hash_chi_00 = "0185f5e7cbc9"
#target_hash_chi_02 = "09af3e994eaa"
#target_hash_chi_04 = "c8bc2bf54720"
#target_hash_chi_06 = "95fc9021d833"



# 2. Unimos el ESQUELETO y las FUERZAS y filtramos
cmd_00 = sprintf("< paste -d, /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/forces/resumen_fuerza_normal_por_atasco.csv | awk 'NR==1 || /%s/'", target_hash_chi_00)
cmd_02 = sprintf("< paste -d, /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/forces/resumen_fuerza_normal_por_atasco.csv | awk 'NR==1 || /%s/'", target_hash_chi_02)
cmd_04 = sprintf("< paste -d, /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/forces/resumen_fuerza_normal_por_atasco.csv | awk 'NR==1 || /%s/'", target_hash_chi_04)
cmd_06 = sprintf("< paste -d, /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv /home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/forces/resumen_fuerza_normal_por_atasco.csv | awk 'NR==1 || /%s/'", target_hash_chi_06)

# 3. Inicializamos memoria
old = NaN

# 4. Formato
set logscale xy
set xlabel "Tamaño de Avalancha Previa (n_{t-1})"
set ylabel "Fuerza Normal Media del Arco Actual (<F_n>)"

# 5. GRAFICAMOS
# old = $5 guarda el tamaño de avalancha anterior
# :32 usa la fuerza del arco actual
plot cmd_00 using (val = old, old = $5, val):32 with points pt 6 ps 0.6 lc rgb "black" title "Chi=0.0", \
cmd_02 using (val = old, old = $5, val):32 with points pt 6 ps 0.6 lc rgb "red" title "Chi=0.2", \
cmd_04 using (val = old, old = $5, val):32 with points pt 6 ps 0.6 lc rgb "blue" title "Chi=0.4", \
cmd_06 using (val = old, old = $5, val):32 with points pt 6 ps 0.6 lc rgb "dark-green" title "Chi=0.7"