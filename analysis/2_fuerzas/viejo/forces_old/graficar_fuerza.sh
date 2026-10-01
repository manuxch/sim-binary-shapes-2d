#!/bin/bash

# =============================================================================
# ESTE ES UN WRAPPER DE BASH, NO UN SCRIPT DE GNUPLOT.
# Su único trabajo es: (1) definir qué contenedor usar, y (2) pasarle el
# código Python (matplotlib) que viene después vía heredoc, junto con los
# argumentos que recibió este script bash.
# =============================================================================

# --- 1. Definir contenedor ---
# Ruta a la imagen Singularity/Apptainer que tiene Python + numpy/pandas/matplotlib
# ya instalados, para no depender del entorno del sistema.
CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"

# --- 2. Ejecutar Python dentro del contenedor ---
# "python3 -" le dice a Python que lea el script desde stdin (el heredoc de abajo)
# en vez de desde un archivo .py. "$@" son los argumentos que le pasaste a ESTE
# script bash (ej: ./plot.sh pdf Disco-Disco 0.1) y se los reenvía a Python,
# donde aparecerán como sys.argv dentro del bloque Python.
apptainer exec $CONTENEDOR python3 - "$@" << 'EOF'
import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================================
# 1. LECTURA DE ARGUMENTOS (Heredados desde Bash)
# =============================================================================
# Formato esperado: modo geom1 ratio1 [geom2 ratio2] [geom3 ratio3] [geom4 ratio4]
# "modo" es 'pdf' (guarda archivo) o cualquier otra cosa (muestra en pantalla).
# Podés comparar hasta 4 configuraciones (geometría, area_ratio) en el mismo gráfico.
args = sys.argv[1:]
mode = args[0] if len(args) > 0 else 'interactivo'
g1 = args[1] if len(args) > 1 else 'none'
r1 = args[2] if len(args) > 2 else 'none'
g2 = args[3] if len(args) > 3 else 'none'
r2 = args[4] if len(args) > 4 else 'none'
g3 = args[5] if len(args) > 5 else 'none'
r3 = args[6] if len(args) > 6 else 'none'
g4 = args[7] if len(args) > 7 else 'none'
r4 = args[8] if len(args) > 8 else 'none'

# Arma una lista de tuplas (geometria, area_ratio) descartando los pares
# que no se completaron (quedaron en 'none').
configs = []
for g, r in [(g1, r1), (g2, r2), (g3, r3), (g4, r4)]:
    if g != 'none' and r != 'none':
        configs.append((g, float(r)))

if not configs:
    print("Error: No se proporcionaron configuraciones válidas.")
    sys.exit(1)

# Este CSV es la salida de "por configuración" de force_arch_v3.py
# (una fila por combinación de category/geometry_label/area_ratio/chi/etc.,
# ya promediada entre atascos).
archivo_in = "resumen_fuerza_normal_por_configuracion.csv"
if not os.path.exists(archivo_in):
    print(f"Error: No se encuentra el archivo {archivo_in}")
    sys.exit(1)

df = pd.read_csv(archivo_in)

# =============================================================================
# 2. CONFIGURACIÓN DE ESTÉTICA MATPLOTLIB
# =============================================================================
# Estilo tipo "paper": fuente STIX (similar a Times, buena para matemática),
# ticks hacia adentro y también arriba/derecha (look de journal de física).
plt.rcParams.update({
    'font.family': 'STIXGeneral',
    'mathtext.fontset': 'stix',
    'text.usetex': False,
    'axes.labelsize': 28,
    'xtick.labelsize': 22,
    'ytick.labelsize': 22,
    'legend.fontsize': 18,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.top': True,
    'ytick.right': True,
    'axes.linewidth': 1.2,
})

# Traduce las etiquetas internas (en español) a nombres en inglés para la leyenda,
# ya que el paper/figura final se presenta en inglés.
geom_names = {
    'Disco-Disco': 'Disk-Disk',
    'Cuad-Disco': 'Square-Disk',
    'Tri-Disco': 'Triangle-Disk',
    'Pent-Disco': 'Pentagon-Disk'
}

# Le asigna una forma de marcador distinta a cada geometría, para que las
# curvas se distingan incluso si el gráfico se imprime en blanco y negro.
def get_marker(geom):
    g = geom.lower()
    if 'tri' in g: return '^'
    if 'cuad' in g: return 's'
    if 'pent' in g: return 'p'
    return 'o'

# =============================================================================
# 3. GRAFICACIÓN
# =============================================================================
fig, ax = plt.subplots(figsize=(10, 7))

# Se usa para calcular el límite superior del eje Y al final, después de
# haber graficado TODAS las configuraciones pedidas.
max_y_global = 0

for g, r in configs:
    # Filtra las filas del CSV que matchean esta geometría y este area_ratio.
    # Se usa np.isclose con atol=0.03 porque area_ratio_nominal es un valor
    # redondeado/real que puede no coincidir exactamente con el "r" pedido.
    mask = (df["geometry_label"] == g) & np.isclose(df["area_ratio_nominal"].astype(float), r, atol=0.03)
    df_sub = df[mask].copy()
    
    if df_sub.empty:
        print(f"Advertencia: No hay datos para {g} con ratio {r}")
        continue
    
    # Si hay más de una fila por valor de chi (por ejemplo por distintos
    # sides_large/sides_small, o pequeñas variaciones de area_ratio dentro
    # de la tolerancia), las colapsa promediando. OJO: es un promedio simple
    # sin ponderar por cuántos atascos/contactos aporta cada fila.
    df_sub = df_sub.groupby("chi").mean(numeric_only=True).reset_index().sort_values("chi")
    chi = df_sub["chi"]
    
    geom_en = geom_names.get(g, g)
    marker = get_marker(g)
    
    # Paleta apta para daltónicos (Wong): azul=BB, naranja=BS, verde=SS.
    c_bb, c_bs, c_ss = '#0072B2', '#D55E00', '#009E73'
    c_sum = '#000000'       # negro para el total del Arco
    c_sum_roi = '#666666'   # gris para el total del ROI
    
    # --- ARCOS (Línea sólida, marcadores llenos) ---
    # mean_Fn_arco_{TIPO}: fuerza normal promedio SOLO entre los contactos
    # de ese tipo, es decir sum(f_norm de ese tipo) / n_contactos de ese tipo.
    # NO usar mean_contrib_Fn_arco_{TIPO} acá: esa columna divide por el
    # total de contactos de la región (BB+BS+SS), no por su propio n.
    arch_bb = df_sub["mean_Fn_arco_BB"]
    arch_bs = df_sub["mean_Fn_arco_BS"]
    arch_ss = df_sub["mean_Fn_arco_SS"]
    # Fuerza normal promedio real del arco (todos los contactos, sin
    # distinguir tipo). Se toma directo del CSV, NO como bb+bs+ss:
    # con estas columnas esa suma ya no representa el total.
    arch_total = df_sub["mean_Fn_arco"]
    
    ax.plot(chi, arch_bb, label=f"{geom_en}({r}) Arch BB", color=c_bb, marker=marker, ls='-', mfc=c_bb, mec=c_bb, lw=2, ms=8)
    ax.plot(chi, arch_bs, label=f"{geom_en}({r}) Arch BS", color=c_bs, marker=marker, ls='-', mfc=c_bs, mec=c_bs, lw=2, ms=8)
    ax.plot(chi, arch_ss, label=f"{geom_en}({r}) Arch SS", color=c_ss, marker=marker, ls='-', mfc=c_ss, mec=c_ss, lw=2, ms=8)
    ax.plot(chi, arch_total, label=f"{geom_en} Total Arch", color=c_sum, marker=marker, ls='-', mfc=c_sum, mec=c_sum, lw=2.5, ms=10)
    
    # --- ROI (Línea punteada, marcadores vacíos) ---
    # Mismo esquema que el arco, pero para la región de interés (ROI).
    # ls='--' y mfc='none' (marcador vacío) para diferenciar visualmente
    # del arco sin necesitar más colores.
    roi_bb = df_sub["mean_Fn_roi_BB"]
    roi_bs = df_sub["mean_Fn_roi_BS"]
    roi_ss = df_sub["mean_Fn_roi_SS"]
    roi_total = df_sub["mean_Fn_roi"]
    
    ax.plot(chi, roi_bb, label=f"{geom_en}({r}) ROI BB", color=c_bb, marker=marker, ls='--', mfc='none', mec=c_bb, lw=2, ms=8)
    ax.plot(chi, roi_bs, label=f"{geom_en}({r}) ROI BS", color=c_bs, marker=marker, ls='--', mfc='none', mec=c_bs, lw=2, ms=8)
    ax.plot(chi, roi_ss, label=f"{geom_en}({r}) ROI SS", color=c_ss, marker=marker, ls='--', mfc='none', mec=c_ss, lw=2, ms=8)
    ax.plot(chi, roi_total, label=f"{geom_en} Total ROI", color=c_sum_roi, marker=marker, ls='--', mfc='none', mec=c_sum_roi, lw=2.5, ms=10)

    # Actualiza el máximo global mirando las 8 curvas de esta configuración
    # por separado (no alcanza con mirar el total: mean_Fn_BB puede superar
    # a mean_Fn_total si los contactos BB son, en promedio, más fuertes).
    max_actual = max(
        arch_bb.max(), arch_bs.max(), arch_ss.max(), arch_total.max(),
        roi_bb.max(), roi_bs.max(), roi_ss.max(), roi_total.max()
    )
    if max_actual > max_y_global:
        max_y_global = max_actual

# Configuraciones de ejes
ax.set_xlabel(r"Concentration $\chi$")
ax.set_ylabel("Average Normal Force")

# Rango fijo de concentración (0 a 0.2), con ticks cada 0.05.
ax.set_xlim(0, 0.2)
ax.set_xticks([0.0, 0.05, 0.10, 0.15, 0.20])

# El límite superior deja un 45% de margen sobre el pico más alto de TODO
# el gráfico, para que la leyenda (arriba a la derecha) no tape curvas.
ax.set_ylim(0, max_y_global * 1.45)

ax.legend(loc='upper right', frameon=True, edgecolor='black', framealpha=1.0)

plt.tight_layout()

# =============================================================================
# 4. GUARDAR O MOSTRAR
# =============================================================================
# Nombre de archivo distinto según si es una sola configuración o una
# comparación de varias, para no pisar archivos previos.
if len(configs) > 1:
    out_pdf = "fuerzas_por_tipo_comparacion_multiple.pdf"
else:
    out_pdf = f"fuerzas_por_tipo_{configs[0][0]}_ratio_{configs[0][1]}.pdf"

if mode == 'pdf':
    plt.savefig(out_pdf, bbox_inches='tight')
else:
    plt.show()

EOF