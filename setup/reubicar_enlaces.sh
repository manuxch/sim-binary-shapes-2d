#!/bin/bash
# Uso: bash setup/reubicar_enlaces.sh <prefijo_viejo> <prefijo_nuevo> [repo]
#
# Cuando la carpeta de datos de Windows cambia de lugar (ej. de
# C:\Users\Juli\work a C:\Users\Juli\OneDrive\work), cambia el destino de los
# enlaces simbolicos del repo que apuntaban al lugar viejo. No mueve datos.
# Por defecto solo muestra lo que haria; con REUBICAR=1 delante, lo hace:
#   bash setup/reubicar_enlaces.sh /mnt/c/Users/Juli/work /mnt/c/Users/Juli/OneDrive/work
#   REUBICAR=1 bash setup/reubicar_enlaces.sh /mnt/c/Users/Juli/work /mnt/c/Users/Juli/OneDrive/work
set -euo pipefail
VIEJO="${1:?Falta el prefijo viejo}"; NUEVO="${2:?Falta el prefijo nuevo}"
REPO=$(realpath "${3:-$(git rev-parse --show-toplevel)}")
VIEJO="${VIEJO%/}"; NUEVO="${NUEVO%/}"
n=0; faltan=0
while IFS= read -r -d '' l; do
    destino=$(readlink "$l")
    case "$destino" in "$VIEJO"/*) ;; *) continue ;; esac
    nuevo_destino="$NUEVO${destino#"$VIEJO"}"
    [ -e "$nuevo_destino" ] || { echo "  [!] no existe todavia: $nuevo_destino"; faltan=$((faltan+1)); }
    echo "  ${l#"$REPO"/}  ->  $nuevo_destino"
    if [ "${REUBICAR:-0}" = 1 ]; then ln -sfn "$nuevo_destino" "$l"; fi
    n=$((n+1))
done < <(find "$REPO" -path "$REPO/.git" -prune -o -type l -print0)
echo "$n enlaces apuntaban a $VIEJO ($faltan con destino que todavia no existe)."
if [ "${REUBICAR:-0}" = 1 ]; then echo "Enlaces actualizados."; else echo "No se cambio nada: repetir con REUBICAR=1 delante para aplicarlo."; fi
