import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import seaborn as sns
from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional, List

# =============================================================================
# CONFIGURACIÓN GLOBAL Y ESTILOS
# =============================================================================

@dataclass
class AnalysisConfig:
    """Centraliza rutas de archivos y parámetros de visualización."""
    # Rutas de datos
    data_path: str = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/estadisticas_flujo_agregadas.csv"
    arcos_path: str = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv"
    raw_flow_path: str = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
    out_dir: str = "/work/lab/project/sim-binary-shapes-2d/processed_data/5_graficos_finales"
    
    # Estilos de gráficos
    figsize_std: Tuple[int, int] = (8, 6)
    figsize_wide: Tuple[int, int] = (9, 6)
    capsize: int = 4
    alpha: float = 0.85
    marker_map: Dict[str, str] = field(default_factory=lambda: {
        'Disco(G)-Disco(C)': 'o', 'Disco(G)-Tri(C)': '^', 
        'Disco(G)-Cuad(C)': 's', 'Disco(G)-Pent(C)': 'p',
        'Tri(G)-Disco(C)': '^', 'Cuad(G)-Disco(C)': 's', 
        'Pent(G)-Disco(C)': 'p'
    })

CFG = AnalysisConfig()

# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def save_plot(filename: str, df: Optional[pd.DataFrame] = None):
    """Guarda el gráfico actual y opcionalmente exporta los datos a CSV."""
    plt.savefig(f"{CFG.out_dir}/{filename}.png", bbox_inches='tight', dpi=300)
    plt.close()
    if df is not None:
        df.to_csv(f"{CFG.out_dir}/{filename}.csv", index=False)

def get_pure_reference(df: pd.DataFrame, system_base: str, d_d_sq: float) -> Tuple[Optional[float], Optional[float]]:
    """Obtiene log_S y error de un sistema puro para un orificio específico."""
    ref = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith(system_base)) & (df['D_d_sq'] == d_d_sq)]
    if ref.empty: return None, None
    return ref['log_S'].mean(), ref['log_S_err'].mean()

def clean_system_name(name: str) -> str:
    """Normaliza nombres de sistema para usar en nombres de archivos."""
    return name.lower().replace('(', '').replace(')', '').replace('_', '-').replace('-g-', '-').replace('-c', '')

# =============================================================================
# MÓDULOS DE GENERACIÓN DE GRÁFICOS
# =============================================================================

def plot_puros_vs_orificio(df: pd.DataFrame):
    """Gráfico 1: Avalanchas en sistemas puros vs tamaño de orificio."""
    print("  -> Generando Gráfico 1: Puros vs Orificio...")
    df_puros = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco')) & (df['D_d_sq'].notnull())].copy()
    if df_puros.empty: return

    df_puros = df_puros.sort_values('D_d_sq')
    plt.figure(figsize=CFG.figsize_std)
    plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                 fmt='o-', color='black', capsize=CFG.capsize, label='Discos Puros')
    
    plt.xlabel(r"Ratio de Orificio $(D/d)^2$")
    plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    plt.title("Efecto del Tamaño del Orificio de Descarga")
    plt.grid(True, alpha=0.3)
    plt.legend()
    save_plot("1-puros-vs-orificio", df_puros[['sistema', 'D_d_sq', 'log_S', 'log_S_err']])

def plot_sweeps_by_system(df: pd.DataFrame, sistemas_objetivo: List[Tuple[str, str]]):
    """Gráficos 2 y 4: Barridos de Ratio de Área y Concentración por sistema."""
    for sist_nombre, sist_base in sistemas_objetivo:
        sist_id = clean_system_name(sist_nombre)
        print(f"  -> Procesando Gráficos 2 y 4 para: {sist_nombre}...")
        
        df_mix = df[(df['sistema'] == sist_nombre) & (df['chi'] > 0.0)].copy()
        if df_mix.empty: continue

        main_dd = df_mix['D_d_sq'].value_counts().idxmax()
        df_mix = df_mix[df_mix['D_d_sq'] == main_dd]
        puro_val, puro_err = get_pure_reference(df, sist_base, main_dd)

        # Gráfico 2: vs Ratio de Áreas
        plt.figure(figsize=CFG.figsize_wide)
        if puro_val:
            plt.axhline(puro_val, color='black', linestyle='--', label=r'Puro ($\chi = 0$)')
            plt.fill_between([df_mix['area_ratio'].min(), df_mix['area_ratio'].max()], 
                             puro_val - puro_err, puro_val + puro_err, color='black', alpha=0.1)

        chis = [0.01, 0.1, 0.14, 0.2]
        cmap = cm.plasma
        norm = mcolors.Normalize(vmin=min(chis), vmax=max(chis))

        for chi in chis:
            grp = df_mix[np.isclose(df_mix['chi'], chi, atol=1e-3)].sort_values('area_ratio')
            if not grp.empty:
                plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'], 
                             fmt='s-', color=cmap(norm(chi)), label=f"$\chi$ = {chi}", capsize=3)

        plt.xlabel(r"Ratio de Áreas ($A_S/A_L$)"); plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Efecto del Tamaño del Aditivo ({sist_nombre})")
        plt.legend(title="Concentración", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        save_plot(f"2-{sist_id}-vs-area-ratio")

        # Gráfico 4: vs Concentración (Curvas de Atascamiento)
        plt.figure(figsize=CFG.figsize_std)
        ratios_deseados = [0.1,0.2, 0.4, 0.5]
        df_mix['area_ratio'] = df_mix['area_ratio'].round(2)

        for ar, grp in df_mix.groupby('area_ratio'):
        
            if ar not in ratios_deseados:
                continue
            
            if len(grp) < 3: continue
            grp = grp.sort_values('chi')
            x, y, yerr = grp['chi'], grp['log_S'], grp['log_S_err']
            if puro_val:
                x, y, yerr = [0.0] + x.tolist(), [puro_val] + y.tolist(), [puro_err] + yerr.tolist()
            plt.errorbar(x, y, yerr=yerr, fmt='^-', label=f"AR = {ar:.2f}", capsize=3)

        plt.xlabel(r"Concentración $\chi$"); plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Curvas de Atascamiento ({sist_nombre})")
        plt.legend(title="Tamaño Aditivo", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        save_plot(f"4-{sist_id}-vs-chi-tamanos")

def plot_geometric_effects(df: pd.DataFrame):
    """Gráfico 5: Comparación de efectos geométricos (Aditivo vs Matriz)."""
    df_mix = df[df['chi'] > 0].copy()
    main_dd = df_mix['D_d_sq'].value_counts().idxmax()
    df_mix = df_mix[df_mix['D_d_sq'] == main_dd]

    # Normalización respecto al puro de referencia
    df_puros = df[df['chi'] == 0][['grano_base', 'D_d_sq', 'S_mean', 'S_sem']].rename(columns={'S_mean': 'S0', 'S_sem': 'S0_err'})
    df_norm = pd.merge(df_mix, df_puros, on=['grano_base', 'D_d_sq'], how='inner')
    df_norm['log_S_norm'] = np.log((df_norm['S_mean'] / df_norm['S0']) + 1)

    def draw_comparison(sistemas, filename, title):
        plt.figure(figsize=CFG.figsize_std)
        for sis in sistemas:
            grp = df_norm[df_norm['sistema'] == sis]
            if grp.empty: continue
            ar = grp['area_ratio'].value_counts().idxmax()
            grp = grp[grp['area_ratio'] == ar].sort_values('chi')
            x, y = [0.0] + grp['chi'].tolist(), [np.log(2.0)] + grp['log_S_norm'].tolist()
            plt.errorbar(x, y, fmt=f"{CFG.marker_map.get(sis, 'X')}-", label=sis, capsize=4)
        
        plt.xlabel(r"Concentración $\chi$"); plt.ylabel("Log-S Normalizado")
        plt.title(title); plt.legend(); plt.grid(True, alpha=0.3)
        save_plot(filename)

    print("  -> Generando Gráficos 5a y 5b: Efectos Geométricos...")
    draw_comparison(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], 
                   "5a-efecto-aditivo", "Efecto del Aditivo (Matriz Disco)")
    draw_comparison(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], 
                   "5b-efecto-matriz", "Efecto de la Matriz (Aditivo Disco)")

def plot_arch_analysis():
    """Análisis de composición y morfología de arcos (Gráficos 6-10)."""
    if not os.path.exists(CFG.arcos_path): return
    df = pd.read_csv(CFG.arcos_path)
    
    # Gráfico 6: Composición Global
    print("  -> Generando Gráfico 6: Composición Arcos...")
    df_mix = df[(df['chi'] > 0) & (df['chi'] <= 0.2)].copy()
    df_mix['frac_arco'] = df_mix['Particulas_Tipo_1'] / df_mix['Total_Particulas_Arco']
    
    plt.figure(figsize=CFG.figsize_wide)
    sns.lineplot(data=df_mix, x='chi', y='frac_arco', hue='system_type', marker='o', err_style="bars")
    plt.plot([0, 0.2], [0, 0.2], 'k--', alpha=0.7, label='Homogénea')
    plt.title("Composición del Arco vs Global"); plt.grid(True, alpha=0.3)
    save_plot("6-composicion-arcos")

    # Gráfico 9: Tortuosidad
    print("  -> Generando Gráfico 9: Tortuosidad...")
    plt.figure(figsize=CFG.figsize_wide)
    sns.violinplot(data=df_mix[df_mix['system_type'].str.startswith('Disco')], 
                   x='system_type', y='Tortuosidad', hue='system_type', palette='Set2', inner='quartile')
    plt.title("Tortuosidad de Arcos"); plt.grid(True, axis='y', alpha=0.3)
    save_plot("9-tortuosidad-arcos")

    # Gráfico 10: Dispersión (Boxplot)
    if os.path.exists(CFG.raw_flow_path):
        print("  -> Generando Gráfico 10: Boxplot de Avalanchas...")
        df_raw = pd.read_csv(CFG.raw_flow_path)
        df_meta = df_mix[['sim_hash', 'system_type', 'chi']].drop_duplicates()
        df_plot = pd.merge(df_raw, df_meta, on='sim_hash')
        
        plt.figure(figsize=CFG.figsize_wide)
        sns.boxplot(data=df_plot[df_plot['chi'] == df_plot['chi'].max()], 
                    x='system_type', y='tamano_big', hue='system_type', palette='Set3')
        plt.yscale('log'); plt.title("Distribución de Tamaños (S)"); plt.grid(True, axis='y', alpha=0.3)
        save_plot("10-boxplot-avalanchas")


def plot_geometric_effects_linear(df: pd.DataFrame):
    """
    Gráfico 11: Comparación de efectos geométricos (Lineal).
    Copia la lógica del Gráfico 5: agrupa sistemas para ver el efecto de la forma.
    """
    print("  -> Generando Gráficos 11a y 11b: Efectos Geométricos (Lineales)...")
    
    # 1. Filtramos datos base (chi >= 0 para incluir el puro)
    df_plot = df[df['chi'] >= 0].copy()
    
    # 2. Buscamos el orificio más común para que la comparación sea justa
    main_dd = df_plot['D_d_sq'].value_counts().idxmax()
    df_plot = df_plot[df_plot['D_d_sq'] == main_dd]

    def draw_comparison_linear(sistemas, filename, title):
        plt.figure(figsize=CFG.figsize_std)
        
        for sis in sistemas:
            # Filtramos por sistema
            grp_sis = df_plot[df_plot['sistema'] == sis]
            if grp_sis.empty: continue
            
            # Buscamos el Area Ratio más común para este sistema específico
            # (En el gráfico 5 se suele fijar uno para comparar peras con peras)
            ar_comun = grp_sis['area_ratio'].value_counts().idxmax()
            grp = grp_sis[grp_sis['area_ratio'] == ar_comun].sort_values('chi')
            
            if grp.empty: continue
            
            # Graficamos S_mean directamente (sin log, sin +1)
            plt.errorbar(grp['chi'], grp['S_mean'], yerr=grp['S_sem'], 
                         fmt=f"{CFG.marker_map.get(sis, 'o')}-", 
                         label=f"{sis}", capsize=4)
        
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"Tamaño Medio $\langle S \rangle$")
        plt.title(title)
        plt.legend(fontsize='small')
        plt.grid(True, alpha=0.3)
        save_plot(filename)

    # 3. Definimos las mismas comparaciones que en el Gráfico 5
    # Comparación A: Matriz fija (Disco), variamos el aditivo
    draw_comparison_linear(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], 
                           "11a-efecto-aditivo-lineal", 
                           "Efecto del Aditivo (Matriz Disco) - Lineal")
    
    # Comparación B: Aditivo fijo (Disco), variamos la matriz
    draw_comparison_linear(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], 
                           "11b-efecto-matriz-lineal", 
                           "Efecto de la Matriz (Aditivo Disco) - Lineal")

# =============================================================================
# EJECUCIÓN PRINCIPAL (ORQUESTADOR)
# =============================================================================

def main():
    """Punto de entrada para el pipeline completo de generación de figuras."""
    print(f"[+] Iniciando pipeline de gráficos finales en: {CFG.out_dir}")
    
    if not os.path.exists(CFG.data_path):
        print(f" [!] Error: No se encontró {CFG.data_path}. Abortando.")
        return

    os.makedirs(CFG.out_dir, exist_ok=True)
    sns.set_theme(style="ticks", context="notebook")
    
    # Carga de datos
    df = pd.read_csv(CFG.data_path)
    df = df[df['sistema'] != 'Cuad(G)-Cuad(C)']

    # Ejecución de módulos de gráficos
    plot_puros_vs_orificio(df)
    
    sistemas = [
        ('Disco(G)-Disco(C)', 'Disco'),
        ('Cuad(G)-Disco(C)', 'Cuad'),
        ('Pent(G)-Disco(C)', 'Pent')
    ]
    plot_sweeps_by_system(df, sistemas)
    plot_geometric_effects(df)
    plot_geometric_effects_linear(df)   # Gráfico 11 (Igual al 5 pero lineal)    plot_arch_analysis()

    print(f"[+] ¡Listo! Proceso de análisis visual completado.")

if __name__ == "__main__":
    main()