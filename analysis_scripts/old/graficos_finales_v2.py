import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import seaborn as sns
from dataclasses import dataclass
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================
BASE_DIR = "/work/lab/project/sim-binary-shapes-2d/processed_data"
DATA_PATH = f"{BASE_DIR}/1_avalanche_data/estadisticas_flujo_agregadas.csv"
ARCOS_PATH = f"{BASE_DIR}/1_avalanche_data/resultados_completos_arcos.csv"
RAW_FLOW_PATH = f"{BASE_DIR}/1_avalanche_data/resultados_completos_esqueleto.csv"
OUT_DIR = f"{BASE_DIR}/5_graficos_finales"

# =============================================================================
# ESTILO GLOBAL (Copiado del primer código)
# =============================================================================
sns.set_theme(style="ticks", context="notebook")

@dataclass
class PlotStyle:
    cmap_main: str = "viridis"
    cmap_secondary: str = "plasma"
    pure_color: str = "black"
    alpha: float = 0.85
    capsize: int = 4

STYLE = PlotStyle()

# =============================================================================
# UTILIDADES
# =============================================================================

def ensure_dir():
    os.makedirs(OUT_DIR, exist_ok=True)

def savefig(name):
    plt.savefig(f"{OUT_DIR}/{name}.png", bbox_inches='tight', dpi=300)
    plt.close()

def get_main_dd(df):
    return df['D_d_sq'].value_counts().idxmax()

def get_pure_stats(df, base, D_d_sq):
    df_puro = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith(base)) & (df['D_d_sq'] == D_d_sq)]
    if df_puro.empty: return None, None
    return df_puro['log_S'].mean(), df_puro['log_S_err'].mean()

def add_pure_point(x, y, yerr, pure_val, pure_err):
    if pure_val is None: return x, y, yerr
    return [0.0] + list(x), [pure_val] + list(y), [pure_err] + list(yerr)

# =============================================================================
# BLOQUE 1: AVALANCHAS (Gráficos 1 al 5)
# =============================================================================

def plot_1_puros(df):
    df_puros = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco'))].sort_values('D_d_sq')
    if df_puros.empty: return
    plt.figure(figsize=(8, 6))
    plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                 fmt='o-', color=STYLE.pure_color, capsize=STYLE.capsize)
    plt.xlabel(r"$(D/d)^2$"); plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    plt.title("Discos Puros"); plt.grid(alpha=0.3)
    savefig("1-puros")

def plot_2_4_sweeps(df, sistema, base):
    df_mix = df[(df['sistema'] == sistema) & (df['chi'] > 0)].copy()
    if df_mix.empty: return
    D_d = get_main_dd(df_mix); df_mix = df_mix[df_mix['D_d_sq'] == D_d]
    pure_val, pure_err = get_pure_stats(df, base, D_d)

    # Gráfico 2: vs Area Ratio
    plt.figure(figsize=(8, 6))
    cmap = plt.get_cmap(STYLE.cmap_secondary)
    chis = sorted(df_mix['chi'].unique())
    for chi in chis:
        grp = df_mix[df_mix['chi'] == chi].sort_values('area_ratio')
        plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'],
                     fmt='o-', color=cmap(chi/max(chis)), label=fr"$\chi={chi}$", capsize=3)
    if pure_val: plt.axhline(pure_val, color=STYLE.pure_color, linestyle='--', alpha=0.5)
    plt.legend(title=fr"$\chi$"); plt.title(f"Efecto Tamaño: {sistema}"); plt.grid(alpha=0.3)
    savefig(f"2-{sistema}")

    # Gráfico 4: vs Chi
    plt.figure(figsize=(8, 6))
    for ar, grp in df_mix.groupby('area_ratio'):
        grp = grp.sort_values('chi')
        x, y, yerr = add_pure_point(grp['chi'], grp['log_S'], grp['log_S_err'], pure_val, pure_err)
        plt.errorbar(x, y, yerr=yerr, fmt='o-', label=f"AR={ar:.2f}", capsize=3)
    plt.legend(title="AR"); plt.xlabel(fr"$\chi$"); plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    plt.grid(alpha=0.3); savefig(f"4-{sistema}")

def plot_3_chi_filtered(df, sistema, base):
    ratios = [0.1, 0.4, 0.8, 1.0]
    df_mix = df[(df['sistema'] == sistema) & (df['chi'] > 0)].copy()
    if df_mix.empty: return
    D_d = get_main_dd(df_mix); df_mix = df_mix[df_mix['D_d_sq'] == D_d]
    pure_val, pure_err = get_pure_stats(df, base, D_d)
    
    plt.figure(figsize=(8, 6))
    cmap = plt.get_cmap(STYLE.cmap_main)
    for ar in ratios:
        grp = df_mix[np.isclose(df_mix['area_ratio'], ar, atol=0.05)].sort_values('chi')
        if grp.empty: continue
        x, y, yerr = add_pure_point(grp['chi'], grp['log_S'], grp['log_S_err'], pure_val, pure_err)
        plt.errorbar(x, y, yerr=yerr, fmt='o-', color=cmap(ar), label=f"AR={ar}", capsize=3)
    plt.legend(title="Ratio Área"); plt.xlabel(fr"$\chi$"); plt.title(f"Atascamiento: {sistema}")
    plt.grid(alpha=0.3); savefig(f"3-{sistema}-chi-sweep")

def plot_5_formas(df, modo='aditivo'):
    df_mezclas = df[df['chi'] > 0].copy()
    D_d = get_main_dd(df_mezclas); df_mezclas = df_mezclas[df_mezclas['D_d_sq'] == D_d]
    df_puros = df[df['chi'] == 0][['grano_base', 'D_d_sq', 'S_mean']].rename(columns={'S_mean': 'S0'})
    df_norm = pd.merge(df_mezclas, df_puros, on=['grano_base', 'D_d_sq'])
    df_norm['log_S_norm'] = np.log((df_norm['S_mean'] / df_norm['S0']) + 1)

    sist_map = {
        'aditivo': (['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)'], "Efecto Aditivo"),
        'matriz': (['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)'], "Efecto Matriz")
    }
    target, title = sist_map[modo]
    plt.figure(figsize=(8, 6))
    for sis in target:
        grp = df_norm[df_norm['sistema'] == sis]
        if grp.empty: continue
        main_ar = grp['area_ratio'].value_counts().idxmax()
        grp = grp[grp['area_ratio'] == main_ar].sort_values('chi')
        plt.plot(grp['chi'], grp['log_S_norm'], 'o-', label=sis)
    plt.legend(); plt.xlabel(fr"$\chi$"); plt.ylabel("Norm. Log S"); plt.title(title)
    plt.grid(alpha=0.3); savefig(f"5-{modo}")

# =============================================================================
# BLOQUE 2: ARCOS Y ESTRUCTURA (Gráficos 6 al 10)
# =============================================================================

def plot_6_7_arcos():
    if not os.path.exists(ARCOS_PATH): return
    df = pd.read_csv(ARCOS_PATH); df = df[(df['chi'] > 0) & (df['chi'] <= 0.2)].copy()
    df['frac'] = df['Particulas_Tipo_1'] / df['Total_Particulas_Arco']
    
    # 6: General
    plt.figure(figsize=(8, 6))
    sns.lineplot(data=df, x='chi', y='frac', hue='system_type', marker='o')
    plt.plot([0, 0.2], [0, 0.2], 'k--', alpha=0.5); plt.title("Composición Arco")
    plt.grid(alpha=0.3); savefig("6-arcos-general")

    # 7: Por tamaño (Solo Disco-Disco)
    plt.figure(figsize=(8, 6))
    df_dd = df[df['system_type'] == 'Disco-Disco'].copy()
    if not df_dd.empty:
        sns.lineplot(data=df_dd, x='chi', y='frac', hue='r_ratio', palette='viridis', marker='o')
        plt.plot([0, 0.2], [0, 0.2], 'k--', alpha=0.5); plt.title("Disco-Disco: Efecto Tamaño")
        plt.grid(alpha=0.3); savefig("7-arcos-tamanos")

def plot_8_arcos_vs_ar():
    if not os.path.exists(ARCOS_PATH): return
    df = pd.read_csv(ARCOS_PATH)
    df['frac'] = df['Particulas_Tipo_1'] / df['Total_Particulas_Arco']
    df['area_ratio'] = df['r_ratio']**2
    df_plot = df[df['chi'].isin([0.01, 0.1])]
    plt.figure(figsize=(8, 6))
    sns.lineplot(data=df_plot, x='area_ratio', y='frac', hue='chi', palette='flare', marker='o')
    plt.xlabel("Ratio Áreas"); plt.ylabel("Fracción en Arco"); plt.grid(alpha=0.3)
    savefig("8-arcos-vs-ar")

def plot_9_10_morfologia():
    if not os.path.exists(ARCOS_PATH): return
    df_arcos = pd.read_csv(ARCOS_PATH).dropna(subset=['Tortuosidad'])
    
    # 9: Tortuosidad
    plt.figure(figsize=(8, 6))
    sns.violinplot(data=df_arcos[df_arcos['system_type'].str.contains('Disco')], 
                   x='system_type', y='Tortuosidad', hue='system_type', palette='Set2', legend=False)
    plt.grid(axis='y', alpha=0.3); savefig("9-tortuosidad")

    # 10: Boxplot Dispersion
    if os.path.exists(RAW_FLOW_PATH):
        df_raw = pd.read_csv(RAW_FLOW_PATH)
        df_meta = df_arcos[['sim_hash', 'system_type', 'chi']].drop_duplicates()
        df = pd.merge(df_raw, df_meta, on='sim_hash')
        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df[df['chi'] == df['chi'].max()], x='system_type', y='tamano_big', 
                    hue='system_type', palette='Set3', legend=False)
        plt.yscale('log'); plt.title(fr"Dispersión ($\chi \approx {df['chi'].max()}$)")
        plt.grid(axis='y', alpha=0.3); savefig("10-boxplot")

# =============================================================================
# MAIN
# =============================================================================

def main():
    ensure_dir(); print("[+] Iniciando pipeline completo en USG-Ishimura...")
    df = pd.read_csv(DATA_PATH); df = df[df['sistema'] != 'Cuad(G)-Cuad(C)']
    sistemas = [('Disco(G)-Disco(C)', 'Disco'), ('Cuad(G)-Disco(C)', 'Cuad'), ('Pent(G)-Disco(C)', 'Pent')]

    plot_1_puros(df)
    for sist, base in sistemas:
        plot_2_4_sweeps(df, sist, base)
        plot_3_chi_filtered(df, sist, base)
    
    plot_5_formas(df, 'aditivo'); plot_5_formas(df, 'matriz')
    plot_6_7_arcos()
    plot_8_arcos_vs_ar()
    plot_9_10_morfologia()
    print(f"[+] DONE. 10 gráficos generados en {OUT_DIR}")

if __name__ == "__main__":
    main()