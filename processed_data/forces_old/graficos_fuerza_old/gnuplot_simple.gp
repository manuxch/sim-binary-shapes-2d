# Configuración básica
set terminal pdfcairo size 6,4 enhanced font 'Arial,10'
set output "grafico_disco_01.pdf"
set datafile separator ','
set datafile columnheaders

# Etiquetas
set xlabel "Chi"
set ylabel "Fuerza Normal"
set title "Fuerzas en Disco-Disco (Area Ratio = 0.1)"

# Comando de filtrado:
# awk filtra el archivo antes de que Gnuplot lo lea
FILE_DATA = "< awk -F, 'NR==1 || $3==0.1' filtrado_disco_disco.csv"

# Graficamos usando los nombres de las columnas directamente
plot FILE_DATA using "chi":"mean_Fn_arco_SS" with linespoints pt 7 title "Arco SS", \
     FILE_DATA using "chi":"mean_Fn_roi_SS" with linespoints pt 6 title "ROI SS"