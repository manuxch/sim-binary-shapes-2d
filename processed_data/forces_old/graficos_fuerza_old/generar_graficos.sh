#!/bin/bash

# 1. Definimos la lista de archivos a procesar
archivos=(
    "filtrado_disco_disco.csv"
    "filtrado_cuadrados_disco.csv"
    "filtrado_pentagonos_disco.csv"
    "filtrado_triangulos_disco.csv"
)

for archivo in "${archivos[@]}"; do
    
    if [ ! -f "$archivo" ]; then
        echo "⚠️ Archivo $archivo no encontrado, saltando..."
        continue
    fi

    nombre_base="${archivo%.csv}"

    # 2. Asignamos los estilos de punto (pt) dependiendo del nombre del archivo
    # pt_arco = lleno, pt_roi = vacío
    if [[ "$archivo" == *"cuadrados"* ]]; then
        pt_arco=5   # Cuadrado lleno
        pt_roi=4    # Cuadrado vacío
    elif [[ "$archivo" == *"triangulos"* ]]; then
        pt_arco=9   # Triángulo lleno
        pt_roi=8    # Triángulo vacío
    elif [[ "$archivo" == *"pentagonos"* ]]; then
        pt_arco=15  # Pentágono lleno
        pt_roi=14   # Pentágono vacío
    else
        pt_arco=7   # Círculo lleno (por defecto para discos)
        pt_roi=6    # Círculo vacío
    fi

    tamanos=$(awk -F, 'NR>1 {print $3}' "$archivo" | sort -u)

    for tamano in $tamanos; do
        
        imagen_salida="${nombre_base}_area_${tamano}.pdf"
        echo "📄 Generando gráfico PDF: $imagen_salida ..."

        # 3. Gnuplot
        gnuplot <<-EOF
            set terminal pdfcairo size 5,4 enhanced font 'Arial,10'
            set output '$imagen_salida'
            set datafile separator ','
            
            set xlabel 'Chi'
            set ylabel 'Fuerza'
            
            # Usamos 'noenhanced' para que los guiones bajos (_) no se vuelvan subíndices
            set title 'Fuerzas para area_ratio = $tamano ($nombre_base)' noenhanced
            
            datos="< awk -F, '\$3==$tamano' $archivo"
            
            # Graficamos forzando los tipos de punto (pt) y un tamaño ligeramente mayor (ps 0.8)
            plot datos using 5:22 smooth unique with linespoints pt $pt_arco ps 0.8 title 'Fn Arco', \
                 '' using 5:30 smooth unique with linespoints pt $pt_roi ps 0.8 title 'Fn ROI'
EOF
    done
done

echo "✅ ¡Gráficos mejorados generados con éxito!"
