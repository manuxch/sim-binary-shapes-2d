#!/bin/bash
# ==============================================================================
# MIGRAR DATOS LOCALES A LA NUEVA ESTRUCTURA (correr UNA vez, despues del pull)
#
# Al reorganizar el repo, varios archivos pesados dejaron de estar en git
# (frames de heatmaps, .npz, lista_atascos*, binarios del simulador). Cuando
# hagas `git pull`, git los BORRA de tu disco porque ya no los sigue. Este
# script los recupera del historial (commit BASE, anterior a la
# reorganizacion) y los pone en su nueva ubicacion, que ahora esta en
# .gitignore.
#
# Ademas mueve los datos locales que nunca estuvieron en git (CSV, parquet,
# etc.) desde las carpetas viejas a las nuevas.
#
# Nunca pisa un archivo que ya exista en el destino (mv -n): si hay
# conflictos los lista al final y no borra el original.
#
# Uso (desde cualquier carpeta):
#     bash migrar_datos_locales.sh
# ==============================================================================
set -u

BASE=38761bb70ed7e55ae1b7fd00c18524ff0a1281bc
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO" || exit 1

CONFLICTOS=()

# mover <origen> <carpeta_destino>: mueve un archivo o el CONTENIDO de una
# carpeta (fusionando subcarpetas) sin pisar nada.
mover() {
    local src="$1" dst="$2"
    [ -e "$src" ] || return 0
    mkdir -p "$dst"
    if [ -d "$src" ]; then
        local e
        for e in "$src"/* "$src"/.[!.]*; do
            [ -e "$e" ] || continue
            if [ -d "$e" ] && [ -d "$dst/$(basename "$e")" ]; then
                mover "$e" "$dst/$(basename "$e")"
            else
                mv -n "$e" "$dst/"
                [ -e "$e" ] && CONFLICTOS+=("$e -> $dst/")
            fi
        done
        rmdir "$src" 2>/dev/null
    else
        mv -n "$src" "$dst/"
        [ -e "$src" ] && CONFLICTOS+=("$src -> $dst/")
    fi
    return 0
}

echo "[1/3] Recuperando archivos pesados del commit $BASE ..."
if ! git cat-file -e "$BASE^{commit}" 2>/dev/null; then
    echo "  [!] No encuentro el commit $BASE. Hace 'git fetch' y volve a correr."
    exit 1
fi
TMP="$(mktemp -d)"
git archive "$BASE" -- \
    analysis_scripts/heatmaps_Cuadrado_v4 analysis_scripts/heatmaps_Disco_v4 \
    analysis_scripts/heatmaps_Pentagono_v4 analysis_scripts/heatmaps_Triangulo_v4 \
    analysis_scripts/resultados_viejos \
    lista_atascos.txt lista_atascos_H.txt simulation/bin simulation/obj \
    | tar -x -C "$TMP"
git archive "$BASE" -- analysis_scripts | tar -x -C "$TMP" --wildcards 'analysis_scripts/heatmap_*.npz'

# Primero lo que todavia este en disco (si git no lo borro, ej. si corres
# esto antes del pull); despues se completa lo que falte desde el historial
# (cp -n: nunca pisa).
for F in Cuadrado Disco Pentagono Triangulo; do
    mover "analysis_scripts/heatmaps_${F}_v4" "processed_data/mapas_calor/frames_v4/heatmaps_${F}_v4"
done
for f in analysis_scripts/heatmap_*.npz; do mover "$f" processed_data/mapas_calor; done
for f in analysis_scripts/resultados_viejos/*.npz; do mover "$f" processed_data/mapas_calor/viejo_npz; done

# "no pisar": coreutils nuevos piden --update=none; los viejos solo tienen -n
if cp --update=none /dev/null "$(mktemp -u)" 2>/dev/null; then NO_PISAR="--update=none"; else NO_PISAR="-n"; fi
restaurar() {  # restaurar <origen_en_TMP> <destino>
    [ -e "$1" ] || return 0
    mkdir -p "$2"
    if [ -d "$1" ]; then cp -r $NO_PISAR "$1/." "$2/"; else cp $NO_PISAR "$1" "$2/"; fi
}
for d in "$TMP"/analysis_scripts/heatmaps_*_v4; do
    restaurar "$d" "processed_data/mapas_calor/frames_v4/$(basename "$d")"
done
for f in "$TMP"/analysis_scripts/heatmap_*.npz; do restaurar "$f" processed_data/mapas_calor; done
for f in "$TMP"/analysis_scripts/resultados_viejos/*.npz; do restaurar "$f" processed_data/mapas_calor/viejo_npz; done
restaurar "$TMP/lista_atascos.txt" .
restaurar "$TMP/lista_atascos_H.txt" .
restaurar "$TMP/simulation/bin" simulation/bin
restaurar "$TMP/simulation/obj" simulation/obj
rm -rf "$TMP"

echo "[2/3] Moviendo datos locales que no estaban en git ..."
mover analysis_scripts/por_forma                 processed_data/presion/por_forma
mover processed_data/forces_new_19-08            processed_data/fuerzas/datos_v4
mover processed_data/forces_old                  processed_data/fuerzas/datos_viejo
mover processed_data/correlation                 processed_data/correlaciones
mover processed_data/old_para_borrar             processed_data/_sin_clasificar/old_para_borrar
rm -rf analysis_scripts/__pycache__ analysis_scripts/resultados_viejos 2>/dev/null
mover analysis_scripts                           processed_data/_sin_clasificar/analysis_scripts

echo "[3/3] Listo."
if [ -d processed_data/_sin_clasificar ]; then
    echo "  Revisa a mano lo que quedo en processed_data/_sin_clasificar/:"
    find processed_data/_sin_clasificar -maxdepth 3 | head -50
fi
if [ ${#CONFLICTOS[@]} -gt 0 ]; then
    echo "  [!] No se movieron (ya existia un archivo con ese nombre en el destino):"
    printf '      %s\n' "${CONFLICTOS[@]}"
fi
