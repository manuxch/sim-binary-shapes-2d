#!/bin/bash
# Uso: bash setup/renombrar_carpetas_cluster.sh <carpeta>
#
# Renombra las carpetas de simulacion con el formato de
# run_scripts/run_slurm_cluster_utn.sh (<FORMA>_R0p1_X0p2_W2p0) al formato que
# leen los scripts de analisis (Ratio_0p1_Chi_0p2_W_2p0): chi, relacion de
# areas y orificio salen del nombre de la carpeta. Busca en <carpeta> y sus
# subcarpetas. No toca el contenido (frames_*, flx.dat, params.in).
#
# Por defecto solo muestra lo que haria; con RENOMBRAR=1 delante, lo hace:
#   bash setup/renombrar_carpetas_cluster.sh /mnt/c/Users/Juli/Downloads/resultados_octogonos/simulation_data
#   RENOMBRAR=1 bash setup/renombrar_carpetas_cluster.sh /mnt/c/Users/Juli/Downloads/resultados_octogonos/simulation_data
#
# Despues hay que volver a indexar/analizar esas simulaciones: los resultados
# guardan la ruta de cada carpeta.
set -euo pipefail
BASE="${1:?Falta la carpeta}"
n=0; choque=0
while IFS= read -r -d '' d; do
    nombre=$(basename "$d")
    case "$nombre" in frames_*) continue ;; esac   # las frames_* se dejan como estan
    if [[ "$nombre" =~ _R([0-9]+p[0-9]+)_X([0-9]+p[0-9]+)_W([0-9]+p[0-9]+)$ ]]; then
        nuevo="Ratio_${BASH_REMATCH[1]}_Chi_${BASH_REMATCH[2]}_W_${BASH_REMATCH[3]}"
        destino="$(dirname "$d")/$nuevo"
        if [ -e "$destino" ]; then
            echo "  [!] ya existe, no se toca: $destino"; choque=$((choque+1)); continue
        fi
        echo "  $nombre  ->  $nuevo"
        [ "${RENOMBRAR:-0}" = 1 ] && mv "$d" "$destino"
        n=$((n+1))
    fi
done < <(find "$BASE" -depth -type d -name '*_R*_X*_W*' -print0)
echo "$n carpetas con formato del cluster ($choque con destino ya existente)."
if [ "${RENOMBRAR:-0}" = 1 ]; then echo "Renombradas."; else echo "No se cambio nada: repetir con RENOMBRAR=1 delante para aplicarlo."; fi
