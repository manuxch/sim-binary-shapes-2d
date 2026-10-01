#!/bin/bash
# ==============================================================================
# PASO 3 de la limpieza del historial: actualiza un clon existente al
# historial nuevo SIN re-clonar (asi no hay que mover los datos locales:
# processed_data/, datos_simulaciones/, etc. quedan intactos).
#
# Correrlo en CADA maquina donde tengas el repo (WSL, workstation, cluster),
# despues de que el paso 2 subio el historial limpio a GitHub.
#
#  - Si el clon tiene commits que no estan en GitHub, se detiene y avisa.
#  - Los archivos del repo no cambian (el contenido de main es identico).
#  - Borra las ramas locales y referencias viejas, y libera el espacio.
#
# Uso (desde la raiz del repo):
#     bash limpieza_historial/3_actualizar_clon.sh
# ==============================================================================
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

[ -z "$(git status --porcelain --untracked-files=no)" ] || {
    echo "[!] Hay cambios sin commitear en archivos del repo. Guardalos aparte antes (git stash no sirve: se borra)."; exit 1; }

ANTES="$(du -sh .git | cut -f1)"
VIEJO_MAIN="$(git rev-parse main)"
ARBOL_LOCAL="$(git rev-parse 'main^{tree}')"

git fetch -q --force origin '+refs/heads/*:refs/remotes/origin/*' --prune
ARBOL_GITHUB="$(git rev-parse 'origin/main^{tree}')"

if [ "$ARBOL_LOCAL" != "$ARBOL_GITHUB" ]; then
    echo "[!] Tu main local tiene contenido distinto al de GitHub."
    echo "    Probablemente hay commits sin subir. No toco nada."
    echo "    Commits locales: $(git log --oneline -3 "$VIEJO_MAIN" | tr '\n' ';')"
    exit 1
fi

git checkout -q main
git reset -q --hard origin/main

# Borrar ramas locales y referencias que apuntan al historial viejo
for r in $(git for-each-ref --format='%(refname:short)' refs/heads); do
    [ "$r" = "main" ] || { echo "    borrando rama local vieja: $r"; git branch -q -D "$r"; }
done
git for-each-ref --format='%(refname)' refs/original refs/stash 2>/dev/null | xargs -r -n1 git update-ref -d
git tag -l | xargs -r git tag -d >/dev/null
git fetch -q --tags origin 2>/dev/null || true

git reflog expire --expire=now --all
git gc -q --prune=now --aggressive

echo "Listo: .git paso de $ANTES a $(du -sh .git | cut -f1)."
echo "Tus archivos no cambiaron. Ultimo commit: $(git log --oneline -1)"
