#!/bin/bash
# Uso: bash setup/enlazar_datos.sh <carpeta_del_proyecto_en_windows> [repo_en_wsl]
#
# Enlaza en el repo de WSL todo lo que git ignora en la carpeta de Windows
# (datos_simulaciones, master_sim_index.csv, parquet, etc.): crea enlaces
# simbolicos que apuntan a Windows. No mueve ni copia datos. Usa el .git del
# repo de WSL, asi que funciona aunque la carpeta de Windows no tenga .git.
# Se puede volver a correr: saltea lo que ya existe.
set -euo pipefail
VIEJO=$(realpath "$1")
REPO=$(realpath "${2:-$(git rev-parse --show-toplevel)}")
n=0
while IFS= read -r -d '' p; do
    p=${p%/}
    case "$p" in venv|*/venv|*__pycache__*|*.ipynb_checkpoints*|simulation/bin|simulation/obj) continue;; esac
    [ -e "$REPO/$p" ] && { echo "  ya existe en el repo, lo salteo: $p"; continue; }
    mkdir -p "$REPO/$(dirname "$p")"
    ln -s "$VIEJO/$p" "$REPO/$p"
    grep -qxF "/$p" "$REPO/.git/info/exclude" || echo "/$p" >> "$REPO/.git/info/exclude"
    n=$((n+1))
done < <(git -C "$REPO" --work-tree="$VIEJO" ls-files -z -o -i --exclude-standard --exclude-from="$REPO/.gitignore" --directory)
echo "$n enlaces creados. git status deberia estar limpio:"
git -C "$REPO" status --short
