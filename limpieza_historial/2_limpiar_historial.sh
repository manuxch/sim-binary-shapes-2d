#!/bin/bash
# ==============================================================================
# PASO 2 de la limpieza del historial: borra del historial de git las rutas
# listadas por el paso 1 y sube el historial nuevo a GitHub (force-push).
#
#  - Antes de tocar nada hace un BACKUP COMPLETO del repo (git clone --mirror)
#    en la carpeta de arriba del repo: ../sim-binary-shapes-2d_BACKUP_<fecha>.git
#  - Trabaja sobre una copia temporal: tu carpeta de trabajo no se modifica.
#  - Pide confirmacion escribiendo SI antes del force-push.
#
# Requisitos: git-filter-repo  (sudo apt install git-filter-repo
#                              o  pip install --user git-filter-repo)
#
# Uso (desde la raiz del repo, despues del paso 1):
#     bash limpieza_historial/2_limpiar_historial.sh
# ==============================================================================
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"
LISTA="$REPO/processed_data/_historico/LISTA_RUTAS_BORRADAS.txt"
FECHA="$(date +%Y%m%d_%H%M)"
BACKUP="$(dirname "$REPO")/$(basename "$REPO")_BACKUP_${FECHA}.git"
TMP="$(dirname "$REPO")/$(basename "$REPO")_LIMPIO_${FECHA}.git"
URL_GITHUB="$(git remote get-url origin)"

echo "== Verificaciones =="
command -v git-filter-repo >/dev/null || git filter-repo --version >/dev/null 2>&1 || {
    echo "[!] Falta git-filter-repo: sudo apt install git-filter-repo  (o pip install --user git-filter-repo)"; exit 1; }
[ -s "$LISTA" ] || { echo "[!] No existe $LISTA. Corre primero el paso 1."; exit 1; }
[ "$(git branch --show-current)" = "main" ] || { echo "[!] Tenes que estar en la rama main."; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "[!] Hay cambios sin commitear. Commitealos o descartalos antes."; exit 1; }
git fetch -q origin
[ "$(git rev-parse main)" = "$(git rev-parse origin/main)" ] || {
    echo "[!] main local y origin/main no coinciden. Hace git pull / git push antes."; exit 1; }
echo "    OK: main limpio y sincronizado con GitHub ($URL_GITHUB)"
echo "    Rutas a borrar del historial: $(wc -l < "$LISTA")"

echo
echo "== 1/4 Backup completo del repo actual =="
git clone -q --mirror "$REPO" "$BACKUP"
echo "    Backup en: $BACKUP ($(du -sh "$BACKUP" | cut -f1))"

echo
echo "== 2/4 Limpiando una copia temporal =="
git clone -q --mirror "$REPO" "$TMP"
cd "$TMP"
# Solo las ramas locales y tags: las referencias remotas viejas no se suben
git for-each-ref --format='%(refname)' refs/remotes | xargs -r -n1 git update-ref -d
git filter-repo --force --invert-paths --paths-from-file "$LISTA"
git reflog expire --expire=now --all
git gc -q --prune=now --aggressive
echo "    Tamano antes: $(du -sh "$BACKUP" | cut -f1)   despues: $(du -sh "$TMP" | cut -f1)"

echo
echo "== 3/4 Verificando que el contenido actual no cambio =="
ARBOL_ANTES="$(git -C "$REPO" rev-parse 'main^{tree}')"
ARBOL_DESPUES="$(git rev-parse 'main^{tree}')"
if [ "$ARBOL_ANTES" != "$ARBOL_DESPUES" ]; then
    echo "[!] El contenido de main cambio ($ARBOL_ANTES -> $ARBOL_DESPUES). Abortando, no se subio nada."
    exit 1
fi
echo "    OK: los archivos de main son identicos byte a byte."
echo "    Commits en main: antes $(git -C "$REPO" rev-list --count main), despues $(git rev-list --count main)"

echo
echo "== 4/4 Subir a GitHub (reescribe el historial) =="
OTRAS=$(git ls-remote --heads "$URL_GITHUB" | awk '{print $2}' | sed 's#refs/heads/##' | grep -vx main || true)
echo "    Se va a reemplazar la rama main de GitHub por la version limpia."
if [ -n "$OTRAS" ]; then
    echo "    Y se van a BORRAR de GitHub estas ramas (tienen el historial viejo; si quedan, el repo sigue pesando):"
    for r in $OTRAS; do echo "      - $r"; done
fi
read -r -p "    Escribi SI para continuar: " RESP
if [ "$RESP" != "SI" ]; then
    echo "    Cancelado. No se subio nada. Podes borrar $TMP; el backup queda en $BACKUP"
    exit 0
fi
git remote add origin "$URL_GITHUB" 2>/dev/null || git remote set-url origin "$URL_GITHUB"
git push --force origin main:main
for r in $OTRAS; do git push origin --delete "$r"; done
git push --force --tags origin 2>/dev/null || true

echo
echo "Listo. GitHub tiene el historial limpio."
echo "  - Backup del historial completo: $BACKUP  (guardalo hasta estar seguro; despues se puede borrar)"
echo "  - Copia temporal (ya no hace falta): $TMP"
echo "Siguiente: correr limpieza_historial/3_actualizar_clon.sh en esta carpeta y en cada maquina donde tengas el repo."
