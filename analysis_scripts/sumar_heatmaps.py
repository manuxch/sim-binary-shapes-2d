#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combina muchas imágenes generadas con `graficar_presion_atasco.py --heatmap`
(mismo xlim/ylim/vmin/vmax para todas, de la MISMA geometría) en un único
mapa de calor de presión promedio por ubicación espacial.

Por qué no promedia los colores directamente: un píxel "verde" no es la
mitad de un píxel "azul" más la mitad de uno "amarillo" en términos de
presión real (la colormap no es lineal). Este script hace lo correcto:
decodifica cada píxel de vuelta a su valor de presión (usando la MISMA
colormap/escala con la que se generaron las imágenes), promedia esos
valores de presión reales, y recién al final los vuelve a colorear una
sola vez para mostrar el resultado.

Uso:
    python3 sumar_heatmaps.py --patron "heatmap_Disco_*.png" \
        --vmin 1 --vmax 500 --out heatmap_promedio_Disco.png

Importante: --vmin/--vmax tienen que ser EXACTAMENTE los mismos que
usaste al generar las imágenes individuales con --heatmap, si no la
decodificación da presiones incorrectas.
"""
import argparse
import glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image
from scipy.spatial import cKDTree


def construir_lut(cmap_nombre='viridis', n=256):
    """Tabla de n colores RGB (0-1) que recorre la colormap de punta a
    punta, para poder buscar 'que valor normalizado t produjo este color'
    por vecino mas cercano."""
    cmap = plt.get_cmap(cmap_nombre)
    t = np.linspace(0, 1, n)
    rgb = cmap(t)[:, :3]
    return t, rgb


def decodificar_imagen(path, arbol, t_lut, norm):
    """Lee un PNG RGBA y devuelve (P_decodificada, alpha), ambos arrays
    2D del mismo shape que la imagen. P_decodificada solo tiene sentido
    donde alpha > 0 (fuera de eso es fondo transparente)."""
    img = np.asarray(Image.open(path).convert('RGBA'), dtype=np.float32) / 255.0
    rgb = img[:, :, :3]
    alpha = img[:, :, 3]

    h, w = alpha.shape
    rgb_flat = rgb.reshape(-1, 3)
    _, idx = arbol.query(rgb_flat, k=1)
    t_flat = t_lut[idx]

    # Invertimos la norma (LogNorm) para volver de t normalizado a presion real
    vmin, vmax = norm.vmin, norm.vmax
    P_flat = vmin * (vmax / vmin) ** t_flat
    P = P_flat.reshape(h, w)
    return P, alpha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--patron', required=True,
                         help='Patron glob de las imagenes a combinar, ej. "heatmap_Disco_*.png"')
    parser.add_argument('--vmin', type=float, required=True,
                         help='Mismo --vmin usado al generar las imagenes con --heatmap')
    parser.add_argument('--vmax', type=float, required=True,
                         help='Mismo --vmax usado al generar las imagenes con --heatmap')
    parser.add_argument('--out', default='heatmap_promedio.png')
    parser.add_argument('--min_ocupacion', type=float, default=0.0,
                         help='Fraccion minima de imagenes que deben cubrir un pixel para '
                              'mostrarlo (0-1). Util para recortar bordes con pocas muestras.')
    args = parser.parse_args()

    archivos = sorted(glob.glob(args.patron))
    if not archivos:
        raise SystemExit(f"Ningun archivo matcheo el patron {args.patron!r}")
    print(f"Combinando {len(archivos)} imagenes...")

    norm = mcolors.LogNorm(vmin=args.vmin, vmax=args.vmax)
    t_lut, rgb_lut = construir_lut()
    arbol = cKDTree(rgb_lut)

    suma_P_ponderada = None
    suma_alpha = None

    for i, path in enumerate(archivos):
        P, alpha = decodificar_imagen(path, arbol, t_lut, norm)
        if suma_P_ponderada is None:
            suma_P_ponderada = np.zeros_like(P)
            suma_alpha = np.zeros_like(alpha)
        suma_P_ponderada += P * alpha
        suma_alpha += alpha
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(archivos)}...")

    n_imagenes = len(archivos)
    ocupacion = suma_alpha / n_imagenes
    with np.errstate(invalid='ignore', divide='ignore'):
        P_media = np.where(suma_alpha > 0, suma_P_ponderada / suma_alpha, np.nan)
    P_media = np.where(ocupacion >= args.min_ocupacion, P_media, np.nan)

    # --- Grafico final: presion promedio recolorizada UNA sola vez ---
    fig, (ax_p, ax_ocup) = plt.subplots(1, 2, figsize=(11, 9))

    im1 = ax_p.imshow(P_media, origin='lower', cmap='viridis', norm=norm)
    fig.colorbar(im1, ax=ax_p, label='Presión reducida media $\\langle P/g \\rangle$ (escala log)',
                 fraction=0.05, pad=0.02, extend='both')
    ax_p.set_title(f'Presión promedio ({n_imagenes} atascos)')
    ax_p.axis('off')

    im2 = ax_ocup.imshow(ocupacion, origin='lower', cmap='magma', vmin=0, vmax=1)
    fig.colorbar(im2, ax=ax_ocup, label='Fracción de atascos con partícula en ese punto',
                 fraction=0.05, pad=0.02)
    ax_ocup.set_title('Ocupación espacial')
    ax_ocup.axis('off')

    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    print(f"Guardado: {args.out}")

    # Tambien guardo los arrays crudos, por si despues los quieren re-usar
    # sin tener que re-procesar todas las imagenes de nuevo.
    npz_path = args.out.rsplit('.', 1)[0] + '.npz'
    np.savez_compressed(npz_path, P_media=P_media.astype(np.float32),
                         ocupacion=ocupacion.astype(np.float32),
                         n_imagenes=n_imagenes, vmin=args.vmin, vmax=args.vmax)
    print(f"Datos crudos guardados en: {npz_path}")


if __name__ == '__main__':
    main()
