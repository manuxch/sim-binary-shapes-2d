#!/bin/bash
# ==============================================================================
# Borra los archivos que los scripts de analisis dejan DENTRO de las carpetas
# de simulacion (se pueden regenerar en cualquier momento):
#
#   chi       dinamica_flujo_final_*.{pdf,png,svg}     (temporal_chi.py)
#   arcos     arco_y_fuerzas_contacto_*.{pdf,png,svg}  (2_fuerzas/graficar_arco_fuerza.py)
#   img       carpetas frames_*/img_debug/             (2_fuerzas/force_arch_v4.py --save-images)
#
# Nunca toca los datos de la simulacion (params.in, flx.dat, frames, atasco_*,
# etc.): solo esos nombres.
#
# Uso:
#   bash analysis/utils/limpiar_residuos.sh <carpeta> [<carpeta> ...]            # solo lista (no borra)
#   bash analysis/utils/limpiar_residuos.sh --borrar <carpeta> [<carpeta> ...]   # borra
#   bash analysis/utils/limpiar_residuos.sh --solo chi --borrar <carpeta>        # una sola categoria
# ==============================================================================
set -euo pipefail

BORRAR=0
SOLO=""
CARPETAS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --borrar) BORRAR=1 ;;
        --solo)   SOLO="$2"; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) CARPETAS+=("$1") ;;
    esac
    shift
done
[ ${#CARPETAS[@]} -gt 0 ] || { echo "Falta la carpeta. Uso: $0 [--borrar] [--solo chi|arcos|img] <carpeta>..."; exit 1; }
case "$SOLO" in ""|chi|arcos|img) ;; *) echo "--solo tiene que ser chi, arcos o img"; exit 1 ;; esac

LISTA=$(mktemp); trap 'rm -f "$LISTA"' EXIT
for c in "${CARPETAS[@]}"; do
    [ -d "$c" ] || { echo "No existe la carpeta: $c"; exit 1; }
    if [ -z "$SOLO" ] || [ "$SOLO" = chi ]; then
        find "$c" -type f \( -name 'dinamica_flujo_final_*.pdf' -o -name 'dinamica_flujo_final_*.png' \
             -o -name 'dinamica_flujo_final_*.svg' \) -print0 >> "$LISTA"
    fi
    if [ -z "$SOLO" ] || [ "$SOLO" = arcos ]; then
        find "$c" -type f \( -name 'arco_y_fuerzas_contacto_*.pdf' -o -name 'arco_y_fuerzas_contacto_*.png' \
             -o -name 'arco_y_fuerzas_contacto_*.svg' \) -print0 >> "$LISTA"
    fi
    if [ -z "$SOLO" ] || [ "$SOLO" = img ]; then
        find "$c" -type d -name 'img_debug' -path '*/frames_*/img_debug' -print0 >> "$LISTA"
    fi
done

N=$(tr -cd '\0' < "$LISTA" | wc -c)
if [ "$N" -eq 0 ]; then
    echo "No hay residuos para borrar."
    exit 0
fi
# tamano total (xargs puede partir la lista en varios du: se suma todo)
TOTAL_KB=$(xargs -0 du -sk < "$LISTA" | awk '{s += $1} END {print s + 0}')
TOTAL=$(awk -v k="$TOTAL_KB" 'BEGIN { split("K M G T", u); i = 1; while (k >= 1024 && i < 4) { k /= 1024; i++ }; printf "%.1f%s", k, u[i] }')
echo "Residuos encontrados: $N  (ocupan $TOTAL)"
# solo las primeras 20 (head corta la tuberia: "|| true" para que no corte el script)
{ tr '\0' '\n' < "$LISTA" | head -20 | sed 's/^/  /'; } || true
if [ "$N" -gt 20 ]; then echo "  ... y $((N - 20)) mas"; fi

if [ "$BORRAR" -eq 1 ]; then
    xargs -0 rm -rf < "$LISTA"
    echo "Borrados $N residuos ($TOTAL)."
else
    echo
    echo "No se borro nada. Para borrar, agregar --borrar."
fi
