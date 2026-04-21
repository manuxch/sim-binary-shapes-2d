#!/bin/bash

# Define dónde está tu ejecutable (ajusta esto si la ruta cambia)
RENDER_EXE="/home/jmontero/box2d_2.4/silo-2d/render/bin/granular_render"
DO_VIDEO="/home/jmontero/box2d_2.4/silo-2d/render/scripts/dovideo.sh"

# Buscamos carpetas y empezamos el bucle
find . -maxdepth 2 -mindepth 1 -type d | while read carpeta; do
    echo "------------------------------------------------"
    echo "Procesando: $carpeta"

    (
        cd "$carpeta" || exit

        # 1. Extraer Radio
        # Nota: Asumo que en params.in dice algo como "Radio_silo 20" o "Radio_silo: 20"
        radio=$(grep "Radio_silo" params.in | head -n 1 | grep -oE "[0-9]+\.[0-9]+")

        # 2. Calcular límites (Radio + 1) usando bc para decimales
        # Si radio es 20, limite será 21. Si radio es 20.5, será 21.5
        limite=$(echo "$radio + 1" | bc)

        # 3. Encontrar la subcarpeta (ej: frames_SQUARE...)
        subcarpeta_path=$(find . -maxdepth 1 -mindepth 1 -type d | head -n 1)
        nombre_sub=$(basename "$subcarpeta_path")
        
        # 4. Construir la ruta absoluta para el flag -d
        # $(pwd) nos da la ruta actual absoluta. Le sumamos la subcarpeta.
        ruta_frames="$(pwd)/$nombre_sub"

        echo "   -> Datos: Radio=$radio | Limites= +/- $limite"
        echo "   -> Ejecutando render..."

        # 5. Ejecutar el comando final
        # Fíjate cómo paso el negativo: -$limite
        $RENDER_EXE -d "$ruta_frames" -x -$limite $limite -2 20 < /dev/null
        $DO_VIDEO "$ruta_frames" frm anim 25 < /dev/null
    )
done