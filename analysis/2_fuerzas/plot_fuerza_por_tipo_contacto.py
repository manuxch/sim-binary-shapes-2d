"""
Grafica Fuerza Normal promedio (Arco vs ROI, BB/BS/SS) vs chi, con barras de
error, a partir de resumen_fuerza_normal_por_configuracion.csv (salida de
force_arch_v4.py).

Reemplaza a graficar_fuerza.sh (forces_old/), que:
  - no normalizaba por Mg,
  - no tenia barras de error,
  - usaba mean_Fn_{region}_{tipo} (promedio simple de los promedios por
    atasco) en vez del valor pooled sobre todos los contactos,
  - promediaba "a lo bruto" (.groupby("chi").mean()) filas duplicadas de
    chi que vienen de distintos "category" (distintas tandas de
    simulaciones para el mismo chi/ratio nominal) -- eso NO es valido para
    columnas ya pooled (mean_Fn_pooled_*, sem_pooled_Fn_*): hay que volver a
    poolear esas filas entre si, no promediarlas.

Uso:
    python3 plot_fuerza_por_tipo_contacto.py <modo> g1 r1 [g2 r2] [g3 r3] [g4 r4]
    modo: 'pdf' (guarda archivo) o cualquier otra cosa (muestra en pantalla)
    g:    geometry_label ('Cuad-Disco', 'Tri-Disco', 'Pent-Disco', 'Disco-Disco')
    r:    area_ratio_nominal (ej: 0.1, 0.2, 0.4, 0.6, 0.8)
"""
import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from force_arch_v4 import pool_stats  # misma formula de pooling que el analisis pesado

# =============================================================================
# 0. CONSTANTES
# =============================================================================
MG = 9.8  # M=1 kg, g=9.8 m/s^2. Normalizamos al graficar (no bakeado en los CSV,
          # asi cambiar M o g no requiere re-correr el analisis pesado).
W_SALIDA_PRINCIPAL = 2.0  # excluye COMPARACION-GOLDBERG (barre w_salida a chi fijo)
MIN_N_SEGUNDO_POOLING = 1  # min-n ya se aplico en force_arch_v4.py; aca solo repoolea

GEOM_REFERENCIA_FILTRADO = "Disco-Disco"  # geometria cuya cantidad de puntos en chi
                                           # se usa como objetivo al filtrar las demas
                                           # (ver filtrar_chi_por_cantidad, seccion 2b)

CHI_MAX_EJE = 0.4  # eje x fijo en [0, CHI_MAX_EJE] en TODOS los graficos, para que
                    # sean comparables entre geometrias (Cuad/Pent-Disco tienen datos
                    # hasta chi=0.6, Tri-Disco hasta 0.3-0.4, Disco-Disco solo hasta
                    # 0.2). Los puntos con chi > CHI_MAX_EJE se descartan antes de
                    # graficar (no solo se recorta la vista), para que tampoco influyan
                    # en el escalado del eje y. Poner en None para volver al
                    # comportamiento anterior (rango automatico por grafico).

REGIONES = ["arco", "roi"]
TIPOS = ["BB", "BS", "SS"]

# Solo para mostrar en leyendas/etiquetas: las columnas del CSV siguen usando
# B(ig)/S(mall) tal cual las escribe force_arch_v4.py (cambiarlas ahi
# implicaria re-correr el analisis pesado completo). Acá se muestran como
# L(arge)/S(mall), que es la terminologia que se quiere en los graficos.
TIPO_DISPLAY = {"BB": "LL", "BS": "LS", "SS": "SS"}

# =============================================================================
# 1. LECTURA DE ARGUMENTOS
# =============================================================================
args = sys.argv[1:]
mode = args[0] if len(args) > 0 else "interactivo"
pares = args[1:9]
configs = []
for i in range(0, len(pares) - 1, 2):
    g, r = pares[i], pares[i + 1]
    if g != "none" and r != "none":
        configs.append((g, float(r)))

if not configs:
    print("Error: No se proporcionaron configuraciones validas.")
    sys.exit(1)

# El CSV de entrada (salida de force_arch_v4.py) vive en processed_data/fuerzas/datos_v4/
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
archivo_in = os.path.join(REPO_DIR, "processed_data", "fuerzas", "datos_v4", "resumen_fuerza_normal_por_configuracion.csv")
if not os.path.exists(archivo_in):
    print(f"Error: No se encuentra el archivo {archivo_in}")
    sys.exit(1)

df = pd.read_csv(archivo_in)
df = df[np.isclose(df["w_salida"].astype(float), W_SALIDA_PRINCIPAL, atol=0.01)].copy()

# =============================================================================
# 2. RE-POOLING de filas duplicadas de chi (distintas tandas/category para el
#    mismo chi/ratio nominal). Pooling es asociativo: poolear dos subgrupos ya
#    pooled (N, mean_pooled, sem_pooled) da el mismo resultado exacto que
#    poolear todos los atascos crudos juntos -- ver force_arch_v4.pool_stats.
# =============================================================================
def col_names(region, tipo=None):
    suf = f"_{tipo}" if tipo else ""
    return f"N_contactos_total_{region}{suf}", f"mean_Fn_pooled_{region}{suf}", f"sem_pooled_Fn_{region}{suf}"

def repool_group(df_chi, region, tipo=None):
    n_col, m_col, sem_col = col_names(region, tipo)
    n = df_chi[n_col].to_numpy(dtype=float)
    m = df_chi[m_col].to_numpy(dtype=float)
    sem = df_chi[sem_col].to_numpy(dtype=float)
    valid = (n > 0) & ~np.isnan(m) & ~np.isnan(sem)
    if not valid.any():
        return np.nan, np.nan
    n, m, sem = n[valid], m[valid], sem[valid]
    s = sem * np.sqrt(n)  # recupera std_pooled de cada subgrupo a partir de su SEM
    _, M, _, SEM = pool_stats(n, m, s)
    return M, SEM

def build_series(df_sub):
    """Para cada chi (posiblemente varias filas de distintas 'category'),
    re-poolea las 8 series (arco/roi x BB/BS/SS/Total) y devuelve un
    DataFrame con una fila por chi, ordenado."""
    rows = []
    for chi, df_chi in df_sub.groupby("chi"):
        row = {"chi": chi}
        for region in REGIONES:
            m, sem = repool_group(df_chi, region)
            row[f"mean_Fn_{region}"], row[f"sem_Fn_{region}"] = m, sem
            for tipo in TIPOS:
                m, sem = repool_group(df_chi, region, tipo)
                row[f"mean_Fn_{region}_{tipo}"], row[f"sem_Fn_{region}_{tipo}"] = m, sem
        rows.append(row)
    return pd.DataFrame(rows).sort_values("chi")

# =============================================================================
# 2b. FILTRADO DE CHI (decluttering): las geometrias con aditivo (Cuad/Tri/
#     Pent-Disco) tienen muchos mas puntos de chi que Disco-Disco en la
#     region de chi bajo (barridos mas finos), lo que satura visualmente el
#     grafico. Se iguala la CANTIDAD de puntos a la de GEOM_REFERENCIA_FILTRADO
#     (mismo ratio), tomando indices equiespaciados sobre el chi YA ORDENADO
#     de cada geometria. Al ser equiespaciado por INDICE (no por valor de chi)
#     sobre una grilla no uniforme, esto adelgaza mas donde hay mas puntos
#     apretados (chi bajo) y casi no toca las zonas ya dispersas (chi alto) -
#     conserva siempre el primer y el ultimo chi de la serie.
# =============================================================================
def n_puntos_referencia(df_full, ratio, geom_ref=GEOM_REFERENCIA_FILTRADO, chi_max=CHI_MAX_EJE):
    """Cantidad de chi unicos de la geometria de referencia (disco) para el
    mismo ratio nominal, usada como objetivo de cantidad de puntos. Respeta
    CHI_MAX_EJE para que el objetivo sea consistente con el rango que
    realmente se va a graficar (relevante si mas adelante hay una geometria
    de referencia que tambien tenga datos mas alla de CHI_MAX_EJE)."""
    mask = (df_full["geometry_label"] == geom_ref) & np.isclose(df_full["area_ratio_nominal"].astype(float), ratio, atol=0.03)
    if chi_max is not None:
        mask &= df_full["chi"] <= chi_max
    return int(df_full.loc[mask, "chi"].nunique())

def recortar_chi_max(df_series, chi_max=CHI_MAX_EJE):
    """Descarta filas con chi > chi_max. Se aplica ANTES del filtro de
    cantidad de puntos (filtrar_chi_por_cantidad) y antes de calcular
    max_y_global, para que los puntos fuera de rango ni se cuenten ni
    influyan en el escalado del eje y."""
    if chi_max is None:
        return df_series
    return df_series[df_series["chi"] <= chi_max].reset_index(drop=True)

def filtrar_chi_por_cantidad(df_series, n_objetivo):
    """Subsamplea df_series (ya construido por build_series, ordenado por
    chi) a ~n_objetivo puntos, tomando indices equiespaciados. Si ya tiene
    <= n_objetivo puntos, se devuelve sin tocar."""
    n = len(df_series)
    if not n_objetivo or n <= n_objetivo:
        return df_series
    idx = np.unique(np.linspace(0, n - 1, n_objetivo).round().astype(int))
    return df_series.iloc[idx].reset_index(drop=True)

# =============================================================================
# 3. ESTETICA (igual que graficar_fuerza.sh viejo)
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
# 4. GRAFICACION
# =============================================================================
fig, ax = plt.subplots(figsize=(10, 7))

max_y_global = 0.0
min_chi, max_chi = np.inf, -np.inf

for g, r in configs:
    mask = (df["geometry_label"] == g) & np.isclose(df["area_ratio_nominal"].astype(float), r, atol=0.03)
    df_sub = df[mask].copy()

    if df_sub.empty:
        print(f"Advertencia: No hay datos para {g} con ratio {r}")
        continue

    df_sub = build_series(df_sub)
    df_sub = recortar_chi_max(df_sub)

    if g != GEOM_REFERENCIA_FILTRADO:
        n_obj = n_puntos_referencia(df, r)
        n_antes = len(df_sub)
        df_sub = filtrar_chi_por_cantidad(df_sub, n_obj)
        if len(df_sub) != n_antes:
            print(f"[i] {g}(ratio={r}): {n_antes} -> {len(df_sub)} puntos "
                  f"(objetivo tomado de {GEOM_REFERENCIA_FILTRADO}={n_obj})")

    chi = df_sub["chi"]
    min_chi, max_chi = min(min_chi, chi.min()), max(max_chi, chi.max())

    geom_en = geom_names.get(g, g)
    marker = get_marker(g)

    c_bb, c_bs, c_ss = '#0072B2', '#D55E00', '#009E73'
    c_sum = '#000000'
    c_sum_roi = '#666666'

    def to_mg(series):
        return series / MG

    # --- ARCO (linea solida, marcadores llenos) ---
    arch_bb, arch_bb_err = to_mg(df_sub["mean_Fn_arco_BB"]), to_mg(df_sub["sem_Fn_arco_BB"])
    arch_bs, arch_bs_err = to_mg(df_sub["mean_Fn_arco_BS"]), to_mg(df_sub["sem_Fn_arco_BS"])
    arch_ss, arch_ss_err = to_mg(df_sub["mean_Fn_arco_SS"]), to_mg(df_sub["sem_Fn_arco_SS"])
    arch_total, arch_total_err = to_mg(df_sub["mean_Fn_arco"]), to_mg(df_sub["sem_Fn_arco"])

    ax.errorbar(chi, arch_bb, yerr=arch_bb_err, label=f"{geom_en}({r}) Arch {TIPO_DISPLAY['BB']}", color=c_bb, marker=marker, ls='-', mfc=c_bb, mec=c_bb, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, arch_bs, yerr=arch_bs_err, label=f"{geom_en}({r}) Arch {TIPO_DISPLAY['BS']}", color=c_bs, marker=marker, ls='-', mfc=c_bs, mec=c_bs, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, arch_ss, yerr=arch_ss_err, label=f"{geom_en}({r}) Arch {TIPO_DISPLAY['SS']}", color=c_ss, marker=marker, ls='-', mfc=c_ss, mec=c_ss, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, arch_total, yerr=arch_total_err, label=f"{geom_en} Total Arch", color=c_sum, marker=marker, ls='-', mfc=c_sum, mec=c_sum, lw=2.5, ms=10, capsize=4)

    # --- ROI (linea punteada, marcadores vacios) ---
    roi_bb, roi_bb_err = to_mg(df_sub["mean_Fn_roi_BB"]), to_mg(df_sub["sem_Fn_roi_BB"])
    roi_bs, roi_bs_err = to_mg(df_sub["mean_Fn_roi_BS"]), to_mg(df_sub["sem_Fn_roi_BS"])
    roi_ss, roi_ss_err = to_mg(df_sub["mean_Fn_roi_SS"]), to_mg(df_sub["sem_Fn_roi_SS"])
    roi_total, roi_total_err = to_mg(df_sub["mean_Fn_roi"]), to_mg(df_sub["sem_Fn_roi"])

    ax.errorbar(chi, roi_bb, yerr=roi_bb_err, label=f"{geom_en}({r}) ROI {TIPO_DISPLAY['BB']}", color=c_bb, marker=marker, ls='--', mfc='none', mec=c_bb, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, roi_bs, yerr=roi_bs_err, label=f"{geom_en}({r}) ROI {TIPO_DISPLAY['BS']}", color=c_bs, marker=marker, ls='--', mfc='none', mec=c_bs, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, roi_ss, yerr=roi_ss_err, label=f"{geom_en}({r}) ROI {TIPO_DISPLAY['SS']}", color=c_ss, marker=marker, ls='--', mfc='none', mec=c_ss, lw=2, ms=8, capsize=4)
    ax.errorbar(chi, roi_total, yerr=roi_total_err, label=f"{geom_en} Total ROI", color=c_sum_roi, marker=marker, ls='--', mfc='none', mec=c_sum_roi, lw=2.5, ms=10, capsize=4)

    # Margen superior: considera y + yerr, no solo y, para que la barra de
    # error no quede cortada por el limite del eje.
    for y, yerr in [(arch_bb, arch_bb_err), (arch_bs, arch_bs_err), (arch_ss, arch_ss_err), (arch_total, arch_total_err),
                     (roi_bb, roi_bb_err), (roi_bs, roi_bs_err), (roi_ss, roi_ss_err), (roi_total, roi_total_err)]:
        top = (y + yerr.fillna(0)).max()
        if pd.notnull(top) and top > max_y_global:
            max_y_global = top

ax.set_xlabel(r"Concentration $\chi$")
ax.set_ylabel(r"Average Normal Force / $Mg$")

if CHI_MAX_EJE is not None:
    ax.set_xlim(-0.01, CHI_MAX_EJE + 0.01)
elif np.isfinite(min_chi) and np.isfinite(max_chi):
    span = max_chi - min_chi
    pad = span * 0.05 if span > 0 else 0.02
    ax.set_xlim(min_chi - pad, max_chi + pad)

ax.set_ylim(0, max_y_global * 1.45 if max_y_global > 0 else 1.0)

ax.legend(loc='upper right', frameon=True, edgecolor='black', framealpha=1.0)

plt.tight_layout()

# =============================================================================
# 5. GUARDAR O MOSTRAR
# =============================================================================
if len(configs) > 1:
    out_pdf = "fuerzas_por_tipo_comparacion_multiple.pdf"
else:
    out_pdf = f"fuerzas_por_tipo_{configs[0][0]}_ratio_{configs[0][1]}.pdf"

if mode == 'pdf':
    plt.savefig(out_pdf, bbox_inches='tight')
    print(f"[+] Guardado: {out_pdf}")
else:
    plt.show()