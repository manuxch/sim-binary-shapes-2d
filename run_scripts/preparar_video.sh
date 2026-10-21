#!/bin/bash
# Video de una simulacion para el material suplementario.
#
# Uso:
#   bash run_scripts/preparar_video.sh <carpeta_simulacion> [carpeta_salida]
#
# Modo "simular" (default): copia el params.in de la simulacion a la carpeta
# de salida, le cambia saveFrameFreq / maxAvalanchas / tMax, la vuelve a
# correr (misma semilla) y arma el video con granular_render + dovideo.sh,
# como renderizar_all.sh.
# Modo "existentes" (MODO=existentes): no simula; renderiza los frm_*.xy que
# ya tiene la simulacion original (cada saveFrameFreq de produccion, 2 s),
# util para ver toda la descarga acelerada (por ejemplo, segregacion).
#
# Variables (con su valor por defecto):
#   MODO=simular        simular | existentes
#   FRAMES_CADA=40      pasos entre frames (40 x 0.001 s = 0.04 s -> 25 fps en tiempo real)
#   AVALANCHAS=4        maxAvalanchas de la corrida nueva (3-4 atascos)
#   T_MAX=300           tMax de la corrida nueva (s), por seguridad
#   SIN_LLENADO=1       borra los frames del llenado (t < tFill) antes de renderizar
#   Y_MIN=-2  Y_MAX=20  ventana vertical del render (Y_MAX ~ 60-80 para ver el silo entero)
#   FPS=25              cuadros por segundo del video
#   EXE                 ejecutable del simulador (default simulation/bin/eo-silo del repo)
#   RENDER_EXE, DO_VIDEO  render y armado del video (default: los de renderizar_all.sh)
#   SOLO_PREPARAR=1     solo arma la carpeta y el params.in, no corre nada
#
# Ejemplos:
#   bash run_scripts/preparar_video.sh .../BARRIDO_WIDTHS_SQUARE_DISK/Ratio_0p1_Chi_0p2_W_2p0 ~/videos_sm/cuad_disco
#   MODO=existentes Y_MAX=70 FPS=15 bash run_scripts/preparar_video.sh .../Chi_0p2_W_2p0 ~/videos_sm/seg
set -euo pipefail

SIM=$(realpath "${1:?Falta la carpeta de la simulacion}")
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=$(realpath -m "${2:-$HOME/videos_sm/$(basename "$(dirname "$SIM")")_$(basename "$SIM")}")
MODO=${MODO:-simular}
FRAMES_CADA=${FRAMES_CADA:-40}
AVALANCHAS=${AVALANCHAS:-4}
T_MAX=${T_MAX:-300}
SIN_LLENADO=${SIN_LLENADO:-1}
Y_MIN=${Y_MIN:--2}
Y_MAX=${Y_MAX:-20}
FPS=${FPS:-25}
EXE=${EXE:-$REPO/simulation/bin/eo-silo}
RENDER_EXE=${RENDER_EXE:-/home/jmontero/box2d_2.4/silo-2d/render/bin/granular_render}
DO_VIDEO=${DO_VIDEO:-/home/jmontero/box2d_2.4/silo-2d/render/scripts/dovideo.sh}

[ -f "$SIM/params.in" ] || { echo "No hay params.in en $SIM"; exit 1; }
param() { grep -E "^$1:" "$2" | head -n 1 | sed -E "s/^$1:[[:space:]]*//; s/[[:space:]#].*//"; }

if [ "$MODO" = simular ]; then
    mkdir -p "$OUT"
    cp "$SIM/params.in" "$OUT/params.in"
    sed -i -E -e "s/^saveFrameFreq:.*/saveFrameFreq: $FRAMES_CADA/" \
              -e "s/^maxAvalanchas:.*/maxAvalanchas: $AVALANCHAS/" \
              -e "s/^tMax:.*/tMax: $T_MAX/" "$OUT/params.in"
    grep -q '^maxAvalanchas:' "$OUT/params.in" || echo "maxAvalanchas: $AVALANCHAS" >> "$OUT/params.in"
    echo "Simulacion: $SIM"
    echo "Salida:     $OUT"
    grep -E '^(saveFrameFreq|maxAvalanchas|tMax|tFill|timeStep|RandomSeed|dirID):' "$OUT/params.in" | sed 's/^/  /'
    [ "${SOLO_PREPARAR:-0}" = 1 ] && { echo "SOLO_PREPARAR=1: no se corre nada."; exit 0; }
    [ -x "$EXE" ] || { echo "No encuentro el simulador en $EXE (compilar con make -C simulation o pasar EXE=...)"; exit 1; }
    (cd "$OUT" && "$EXE" params.in > simulacion.log 2>&1)
    BASE="$OUT"
elif [ "$MODO" = existentes ]; then
    BASE="$SIM"
    mkdir -p "$OUT"
else
    echo "MODO tiene que ser simular o existentes"; exit 1
fi

FR=$(find "$BASE" -maxdepth 1 -type d -name 'frames_*' | head -n 1)
[ -n "$FR" ] || { echo "No hay carpeta frames_* en $BASE"; exit 1; }
if [ "$MODO" = existentes ]; then
    # Se trabaja sobre una copia de los frm_*.xy, para no tocar la simulacion original
    mkdir -p "$OUT/frames"
    find "$FR" -maxdepth 1 -name 'frm_*.xy' -exec cp {} "$OUT/frames/" \;
    FR="$OUT/frames"
fi
if [ "$SIN_LLENADO" = 1 ]; then
    t_fill=$(param tFill "$BASE/params.in"); dt=$(param timeStep "$BASE/params.in")
    paso_fill=$(awk -v a="$t_fill" -v b="$dt" 'BEGIN { printf "%d", a / b }')
    n=0
    for f in "$FR"/frm_*.xy; do
        paso=$(basename "$f" .xy); paso=$((10#${paso#frm_}))
        if [ "$paso" -lt "$paso_fill" ]; then rm -f "$f"; n=$((n + 1)); fi
    done
    echo "Borrados $n frames del llenado (paso < $paso_fill)."
fi
echo "Frames para el video: $(ls "$FR"/frm_*.xy | wc -l)"

radio=$(param Radio_silo "$BASE/params.in")
lim=$(echo "$radio + 1" | bc)
"$RENDER_EXE" -d "$FR" -x -"$lim" "$lim" "$Y_MIN" "$Y_MAX" < /dev/null
"$DO_VIDEO" "$FR" frm anim "$FPS" < /dev/null
echo "Video en: $FR"
