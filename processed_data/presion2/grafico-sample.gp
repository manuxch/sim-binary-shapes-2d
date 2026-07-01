set datafile separator ","
plot "nuevo_archivo_2.csv" u 3:8 title "mean P bulk" w lp, "nuevo_archivo_2.csv" u 3:9 title "mean P bulk B" w lp, "nuevo_archivo_2.csv" u 3:10 title "mean P bulk S" w lp
plot "nuevo_archivo_2.csv" u 3:11 title "mean P arco" w lp, "nuevo_archivo_2.csv" u 3:12 title "mean P arco B" w lp, "nuevo_archivo_2.csv" u 3:13 title "mean P arco S" w lp