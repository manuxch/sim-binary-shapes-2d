#!/bin/bash

# --- 1. Definir contenedor ---
CONTENEDOR="/home/juli/work/lab/containers/workstation_full.sif"

# --- 2. Ejecutar Python dentro del contenedor ---
apptainer exec $CONTENEDOR python3 - "$@" << 'EOF'
import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================================
# 1. LECTURA DE ARGUMENTOS (Heredados desde Bash)
# =============================================================================
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

configs = []
for g, r in [(g1, r1), (g2, r2), (g3, r3), (g4, r4)]:
    if g != 'none' and r != 'none':
        configs.append((g, float(r)))

if not configs:
    print("Error: No se proporcionaron configuraciones válidas.")
    sys.exit(1)

archivo_in = "resumen_fuerza_normal_por_configuracion.csv"
if not os.path.exists(archivo_in):
    print(f"Error: No se encuentra el archivo {archivo_in}")
    sys.exit(1)

df = pd.read_csv(archivo_in)

# =============================================================================
# 2. CONFIGURACIÓN DE ESTÉTICA MATPLOTLIB
# =============================================================================
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

geom_names = {
    'Disco-Disco': 'Disk-Disk',
    'Cuad-Disco': 'Square-Disk',
    'Tri-Disco': 'Triangle-Disk',
    'Pent-Disco': 'Pentagon-Disk'
}

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

# Variable para llevar el registro del valor más alto en el eje Y
max_y_global = 0

for g, r in configs:
    mask = (df["geometry_label"] == g) & np.isclose(df["area_ratio_nominal"].astype(float), r, atol=0.03)
    df_sub = df[mask].copy()
    
    if df_sub.empty:
        print(f"Advertencia: No hay datos para {g} con ratio {r}")
        continue
        
    df_sub = df_sub.groupby("chi").mean(numeric_only=True).reset_index().sort_values("chi")
    chi = df_sub["chi"]
    
    geom_en = geom_names.get(g, g)
    marker = get_marker(g)
    
    c_bb, c_bs, c_ss = '#0072B2', '#D55E00', '#009E73'
    c_sum = '#000000'
    c_sum_roi = '#666666'
    
    # --- ARCOS (Línea sólida, marcadores llenos) ---
    arch_bb = df_sub["mean_contrib_Fn_arco_BB"]
    arch_bs = df_sub["mean_contrib_Fn_arco_BS"]
    arch_ss = df_sub["mean_contrib_Fn_arco_SS"]
    arch_sum = arch_bb + arch_bs + arch_ss
    
    ax.plot(chi, arch_bb, label=f"{geom_en}({r}) Arch BB", color=c_bb, marker=marker, ls='-', mfc=c_bb, mec=c_bb, lw=2, ms=8)
    ax.plot(chi, arch_bs, label=f"{geom_en}({r}) Arch BS", color=c_bs, marker=marker, ls='-', mfc=c_bs, mec=c_bs, lw=2, ms=8)
    ax.plot(chi, arch_ss, label=f"{geom_en}({r}) Arch SS", color=c_ss, marker=marker, ls='-', mfc=c_ss, mec=c_ss, lw=2, ms=8)
    ax.plot(chi, arch_sum, label=f"{geom_en} Sum Arch", color=c_sum, marker=marker, ls='-', mfc=c_sum, mec=c_sum, lw=2.5, ms=10)
    
    # --- ROI (Línea punteada, marcadores vacíos) ---
    roi_bb = df_sub["mean_contrib_Fn_roi_BB"]
    roi_bs = df_sub["mean_contrib_Fn_roi_BS"]
    roi_ss = df_sub["mean_contrib_Fn_roi_SS"]
    roi_sum = roi_bb + roi_bs + roi_ss
    
    ax.plot(chi, roi_bb, label=f"{geom_en}({r}) ROI BB", color=c_bb, marker=marker, ls='--', mfc='none', mec=c_bb, lw=2, ms=8)
    ax.plot(chi, roi_bs, label=f"{geom_en}({r}) ROI BS", color=c_bs, marker=marker, ls='--', mfc='none', mec=c_bs, lw=2, ms=8)
    ax.plot(chi, roi_ss, label=f"{geom_en}({r}) ROI SS", color=c_ss, marker=marker, ls='--', mfc='none', mec=c_ss, lw=2, ms=8)
    ax.plot(chi, roi_sum, label=f"{geom_en} Sum ROI", color=c_sum_roi, marker=marker, ls='--', mfc='none', mec=c_sum_roi, lw=2.5, ms=10)

    # CORRECCIÓN: Revisar el máximo absoluto considerando AMBAS curvas sumadas
    max_actual = max(arch_sum.max(), roi_sum.max())
    if max_actual > max_y_global:
        max_y_global = max_actual

# Configuraciones de ejes
ax.set_xlabel(r"Concentration $\chi$")
ax.set_ylabel("Average Normal Force Contribution")

# Limpieza de los ticks del eje X para que no se superpongan los ceros
ax.set_xlim(0, 0.2)
ax.set_xticks([0.0, 0.05, 0.10, 0.15, 0.20])

# El límite superior se calcula sobre el pico MÁS ALTO de todo el gráfico + 45%
ax.set_ylim(0, max_y_global * 1.45)

# Leyenda adentro, arriba a la derecha
ax.legend(loc='upper right', frameon=True, edgecolor='black', framealpha=1.0)

plt.tight_layout()

# =============================================================================
# 4. GUARDAR O MOSTRAR
# =============================================================================
if len(configs) > 1:
    out_pdf = "fuerzas_comparacion_multiple.pdf"
else:
    out_pdf = f"fuerzas_{configs[0][0]}_ratio_{configs[0][1]}.pdf"

if mode == 'pdf':
    plt.savefig(out_pdf, bbox_inches='tight')
else:
    plt.show()

EOF