#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PASO 1 de la limpieza del historial: exporta a disco TODAS las versiones de
los archivos pesados (figuras, .npz, .tar, binarios...) que ya no estan en
el repo pero siguen ocupando lugar en el historial de git.

No modifica el repo: solo lee el historial y escribe en
processed_data/_historico/ (ignorado por git).

    processed_data/_historico/<ruta original>                     ultima version
    processed_data/_historico/_versiones_anteriores/<ruta>__<fecha>_<commit>.<ext>
    processed_data/_historico/LISTA_RUTAS_BORRADAS.txt            lo que el paso 2 borra del historial

Los archivos que ya recuperaste con migrar_datos_locales.sh (frames
heatmaps_*_v4, .npz de mapas, lista_atascos*, binarios) no se vuelven a
exportar en su ultima version, porque ya estan en tu disco; si tuvieron
versiones anteriores, esas si se exportan.

Uso (desde la raiz del repo, solo necesita python3 sin librerias extra):
    python3 limpieza_historial/1_exportar_historico.py
"""
import os
import re
import subprocess
import sys

PESADO = re.compile(
    r'\.(png|npz|pdf|svg|jpg|jpeg|gif|mp4|tar|zip|gz|ipynb)$'
    r'|(^|/)lista_atascos[^/]*\.txt$'
    r'|^simulation/(bin|obj)/'
    r'|(^|/)eo-silo$', re.I)

# Ultima version ya recuperada en disco por migrar_datos_locales.sh
YA_EN_DISCO = re.compile(
    r'^analysis_scripts/heatmaps_[A-Za-z]+_v4/'
    r'|^analysis_scripts/heatmap_[^/]*\.npz$'
    r'|^analysis_scripts/resultados_viejos/[^/]*\.npz$'
    r'|^lista_atascos[^/]*\.txt$'
    r'|^simulation/(bin|obj)/')


def git(*args):
    return subprocess.run(['git', '-c', 'core.quotePath=false', *args], check=True, capture_output=True,
                          text=True, encoding='utf-8', errors='surrogateescape').stdout


def main():
    repo = git('rev-parse', '--show-toplevel').strip()
    os.chdir(repo)
    destino = os.path.join('processed_data', '_historico')
    if os.path.isdir(destino) and os.listdir(destino):
        sys.exit(f"[!] {destino} ya existe y no esta vacia. Revisala/borrala antes de volver a correr.")

    en_head = set(git('ls-tree', '-r', '--name-only', 'HEAD').split('\n'))

    # Una sola pasada por el historial: todas las versiones (blob) de cada ruta
    print("[1/3] Recorriendo el historial (puede tardar unos minutos)...", flush=True)
    log = git('log', '--all', '--reverse', '--no-renames', '--raw', '--no-abbrev',
              '--format=C %H %ad', '--date=short')
    versiones = {}  # ruta -> [(blob, fecha, commit)] en orden cronologico, sin repetir blob
    fecha = commit = None
    for linea in log.split('\n'):
        if linea.startswith('C '):
            _, commit, fecha = linea.split(' ', 2)
        elif linea.startswith(':'):
            meta, _, ruta = linea.partition('\t')
            campos = meta.split()
            blob, estado = campos[-2], campos[-1]
            if estado.startswith('D') or set(blob) == {'0'}:
                continue
            if ruta in en_head or not PESADO.search(ruta):
                continue
            lst = versiones.setdefault(ruta, [])
            if all(b != blob for b, _, _ in lst):
                lst.append((blob, fecha, commit[:7]))

    # Que exportar
    tareas = []  # (blob, ruta_destino)
    for ruta, lst in versiones.items():
        *anteriores, ultima = lst
        if not YA_EN_DISCO.search(ruta):
            tareas.append((ultima[0], os.path.join(destino, ruta)))
        for blob, f, c in anteriores:
            base, ext = os.path.splitext(ruta)
            tareas.append((blob, os.path.join(destino, '_versiones_anteriores', f"{base}__{f}_{c}{ext}")))

    print(f"      {len(versiones)} rutas pesadas fuera del repo, {len(tareas)} archivos para exportar", flush=True)

    # Escribir los blobs con un solo proceso git cat-file
    print("[2/3] Exportando...", flush=True)
    os.makedirs(destino, exist_ok=True)
    proc = subprocess.Popen(['git', 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    total = 0
    for i, (blob, ruta_dst) in enumerate(tareas, 1):
        proc.stdin.write((blob + '\n').encode())
        proc.stdin.flush()
        cabecera = proc.stdout.readline().split()
        tam = int(cabecera[2])
        datos = proc.stdout.read(tam)
        proc.stdout.read(1)  # salto de linea final
        os.makedirs(os.path.dirname(ruta_dst), exist_ok=True)
        with open(ruta_dst, 'wb') as fh:
            fh.write(datos)
        total += tam
        if i % 200 == 0 or i == len(tareas):
            print(f"      {i}/{len(tareas)} archivos, {total / 1e6:.0f} MB", flush=True)
    proc.stdin.close()
    proc.wait()

    with open(os.path.join(destino, 'LISTA_RUTAS_BORRADAS.txt'), 'w', encoding='utf-8',
              errors='surrogateescape') as fh:
        for ruta in sorted(versiones):
            fh.write(ruta + '\n')

    print(f"[3/3] Listo: {len(tareas)} archivos ({total / 1e6:.0f} MB) en {destino}/")
    print(f"      Lista de rutas que el paso 2 va a borrar del historial: {destino}/LISTA_RUTAS_BORRADAS.txt")


if __name__ == '__main__':
    main()
