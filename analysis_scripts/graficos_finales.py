import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import seaborn as sns
from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional, List
from matplotlib.lines import Line2D

# =============================================================================
# GLOBAL CONFIGURATION AND STYLES
# =============================================================================

@dataclass
class AnalysisConfig:
    """Centralizes file paths and unified visualization styles."""
    data_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/estadisticas_flujo_agregadas.csv"
    arcos_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv"
    raw_flow_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
    out_dir: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/5_graficos_finales"
    
    # Unified Mapping: (Color, Marker) - Colorblind friendly palette
    system_style: Dict[str, Tuple[str, str]] = field(default_factory=lambda: {
        'Disco(G)-Disco(C)': ('#000000', 'o'),  # Black
        'Disco(G)-Tri(C)':   ('#E69F00', '^'),  # Orange
        'Disco(G)-Cuad(C)':  ('#D55E00', 's'),  # Red-Orange
        'Disco(G)-Pent(C)':  ('#CC79A7', 'p'),  # Pink
        'Tri(G)-Disco(C)':   ('#009E73', '^'),  # Green
        'Cuad(G)-Disco(C)':  ('#56B4E9', 's'),  # Sky Blue
        'Pent(G)-Disco(C)':  ('#0072B2', 'p')   # Dark Blue
    })

    # Translation map for clean publication labels
    english_labels: Dict[str, str] = field(default_factory=lambda: {
        'Disco(G)-Disco(C)': 'Disk-Disk',
        'Disco(G)-Tri(C)':   'Disk-Triangle',
        'Disco(G)-Cuad(C)':  'Disk-Square',
        'Disco(G)-Pent(C)':  'Disk-Pentagon',
        'Tri(G)-Disco(C)':   'Triangle-Disk',
        'Cuad(G)-Disco(C)':  'Square-Disk',
        'Pent(G)-Disco(C)':  'Pentagon-Disk'
    })

CFG = AnalysisConfig()

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def set_plot_fonts(labels: int = 20, ticks: int = 16, legend: int = 14):
    """Adjusts font sizes and math engine to work without system LaTeX."""
    plt.rcParams.update({
        'axes.labelsize': labels, 'xtick.labelsize': ticks, 'ytick.labelsize': ticks,
        'legend.fontsize': legend, 'text.usetex': False, 'mathtext.fontset': 'stix',
        'font.family': 'STIXGeneral'
    })

def save_plot(filename: str):
    """Saves the current figure as a PDF."""
    plt.savefig(f"{CFG.out_dir}/{filename}.pdf", bbox_inches='tight')
    plt.close()

def get_pure_ref(df: pd.DataFrame, system_name: str, orifice: float, col: str = 'log_S'):
    """Finds the value and error for the pure matrix system (chi=0)."""
    matrix_type = system_name.split('(')[0]
    ref = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith(matrix_type)) & (df['D_d_sq'] == orifice)]
    if ref.empty: return None, None
    err_col = col + '_err' if 'log' in col else 'S_sem'
    return ref[col].mean(), ref[err_col].mean()

def filter_standard_size(df: pd.DataFrame, target_ar: float, atol: float, system_col: str = 'sistema') -> pd.DataFrame:
    """Selective Filter: Disks -> AR~0.1, Others -> Target AR."""
    mask_disco = (df[system_col] == 'Disco(G)-Disco(C)') & np.isclose(df['area_ratio'], 0.1, atol=0.03)
    mask_otros = (df[system_col] != 'Disco(G)-Disco(C)') & np.isclose(df['area_ratio'], target_ar, atol=atol)
    return df[mask_disco | mask_otros].copy()

# =============================================================================
# PLOTTING MODULES
# =============================================================================

def plot_puros_vs_orificio(df: pd.DataFrame):
    print("  -> Plotting 1: Pure Systems vs Orifice...")
    df_puros = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco'))].sort_values('D_d_sq')
    plt.figure()
    plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                 fmt='o-', color='black', capsize=4, label='Pure Disks')
    plt.xlabel(r"Orifice Ratio $(D/d)^2$")
    plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    plt.legend(title="System")
    save_plot("1-pure-vs-orifice")

def plot_sweeps_by_system(df: pd.DataFrame, target_systems: List[Tuple[str, str]]):
    print("  -> Plotting 4: Clogging Curves (Sweeps)...")
    for system_name, _ in target_systems:
        system_id = system_name.lower().replace('(', '').replace(')', '').replace('_', '-')
        df_mix = df[(df['sistema'] == system_name) & (df['chi'] > 0.0)].copy()
        if df_mix.empty: continue
        
        main_dd = df_mix['D_d_sq'].value_counts().idxmax()
        p0, e0 = get_pure_ref(df, system_name, main_dd, 'log_S')

        plt.figure()
        for target in [0.1, 0.2, 0.4, 0.5]:
            grp_raw = df_mix[np.isclose(df_mix['area_ratio'], target, atol=0.05)].copy()
            if grp_raw.empty: continue
            grp = grp_raw.groupby('chi').agg({'log_S': 'mean', 'log_S_err': 'mean'}).reset_index().sort_values('chi')
            
            x, y, err = ([0.0] + grp['chi'].tolist(), [p0] + grp['log_S'].tolist(), [e0] + grp['log_S_err'].tolist())
            plt.errorbar(x, y, yerr=err, fmt='s-', label=rf"AR $=$ {target}", capsize=3)

        plt.xlabel(r"Concentration $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.legend(loc='upper left')
        save_plot(f"4-{system_id}-clogging-curves")

def plot_geometric_effects(df: pd.DataFrame, target_ar: float = 0.15):
    """Plot 5a & 5b: Normalized Effects."""
    print(f"  -> Plotting 5a/b: Normalized Effects (AR ~ {target_ar})...")
    df_mix = df[df['chi'] > 0].copy()
    main_dd = df_mix['D_d_sq'].value_counts().idxmax()
    df_puros = df[df['chi'] == 0][['grano_base', 'D_d_sq', 'S_mean', 'S_sem']].rename(columns={'S_mean': 'S0', 'S_sem': 'S0_err'})
    df_norm = pd.merge(df_mix[df_mix['D_d_sq'] == main_dd], df_puros, on=['grano_base', 'D_d_sq'])
    df_norm['log_S_norm'] = np.log((df_norm['S_mean'] / df_norm['S0']) + 1)
    df_norm['log_S_norm_err'] = df_norm['S_sem'] / (df_norm['S_mean'] + df_norm['S0'])

    def draw(sistemas, filename):
        plt.figure()
        for sis in sistemas:
            grp = filter_standard_size(df_norm[df_norm['sistema'] == sis], target_ar, 0.07).groupby('chi').agg({'log_S_norm': 'mean', 'log_S_norm_err': 'mean'}).reset_index().sort_values('chi')
            if grp.empty: continue
            color, marker = CFG.system_style.get(sis, ('black', 'o'))
            label_en = CFG.english_labels.get(sis, sis)
            plt.errorbar([0.0]+grp['chi'].tolist(), [np.log(2.0)]+grp['log_S_norm'].tolist(), yerr=[0.0]+grp['log_S_norm_err'].tolist(), fmt=f'{marker}-', color=color, label=label_en, capsize=4)
        plt.xlabel(r"Concentration $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle / \langle S_0 \rangle + 1)$")
        plt.ylim(0.4, 2.5)
        plt.legend(loc='upper left') # Legenda interna
        save_plot(filename)

    draw(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], "5a-additive-normalized")
    draw(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], "5b-matrix-normalized")

def plot_geometric_effects_raw(df: pd.DataFrame, target_ar: float = 0.15):
    """Plot 5c: Raw Log-Size Matrix Effect."""
    print(f"  -> Plotting 5c: Raw Log-Size Matrix Effect (AR ~ {target_ar})...")
    main_dd = df['D_d_sq'].value_counts().idxmax()
    plt.figure()
    for sis in ['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)']:
        grp = filter_standard_size(df[df['D_d_sq'] == main_dd], target_ar, 0.07).copy()
        grp_sis = grp[grp['sistema'] == sis].groupby('chi').agg({'log_S': 'mean', 'log_S_err': 'mean'}).reset_index().sort_values('chi')
        if grp_sis.empty: continue
        
        p0, e0 = get_pure_ref(df, sis, main_dd, 'log_S')
        color, marker = CFG.system_style.get(sis, ('black', 'o'))
        label_en = CFG.english_labels.get(sis, sis)
        plt.errorbar([0.0]+grp_sis['chi'].tolist(), [p0]+grp_sis['log_S'].tolist(), 
                     yerr=[e0]+grp_sis['log_S_err'].tolist(), fmt=f'{marker}-', color=color, label=label_en, capsize=4)
    
    plt.xlabel(r"Concentration $\chi$")
    plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    plt.ylim(2.2, 6.5)
    plt.legend()
    save_plot("5c-matrix-raw-log")

def plot_arch_analysis(df_stats: pd.DataFrame):
    """Plot 6, 9 & 10: Matrix Effect on Arch Morphology."""
    if not os.path.exists(CFG.arcos_path): return
    print("\n[+] Starting Arch Analysis (Matrix Effect)...")
    df_arcos = pd.read_csv(CFG.arcos_path)
    
    name_map_raw = {'Disco-Disco': 'Disco(G)-Disco(C)', 'Tri-Disco': 'Tri(G)-Disco(C)', 
                    'Cuad-Disco': 'Cuad(G)-Disco(C)', 'Pent-Disco': 'Pent(G)-Disco(C)'}
    df_arcos['system_type_norm'] = df_arcos['system_type'].map(name_map_raw)
    mapping = df_stats[['sistema', 'r_ratio', 'area_ratio']].drop_duplicates()
    df = pd.merge(df_arcos, mapping, left_on=['system_type_norm', 'r_ratio'], right_on=['sistema', 'r_ratio'], how='left')
    
    matrix_systems = ['Disco(G)-Disco(C)', 'Tri(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)']
    df_filtered = df[df['sistema'].isin(matrix_systems)].copy()
    df_mix = filter_standard_size(df_filtered[df_filtered['chi'] > 0], 0.15, 0.1, system_col='sistema')
    if df_mix.empty: return

    # Plot 6: Composition (Corrected Aggregation)
    df_mix['frac_arco'] = df_mix['Particulas_Tipo_1'] / df_mix['Total_Particulas_Arco']
    plt.figure()
    for sys_name in matrix_systems:
        group = df_mix[df_mix['sistema'] == sys_name]
        if group.empty: continue
        grp = group.groupby('chi').agg({'frac_arco': ['mean', 'std', 'count']}).reset_index()
        grp.columns = ['chi', 'mean', 'std', 'count']
        grp['sem'] = grp['std'] / np.sqrt(grp['count'])
        
        color, marker = CFG.system_style.get(sys_name, ('black', 'o'))
        plt.errorbar(grp['chi'], grp['mean'], yerr=grp['sem'], fmt=f'{marker}-', color=color, label=CFG.english_labels.get(sys_name, sys_name), capsize=4)
    
    plt.plot([0, df_mix['chi'].max()], [0, df_mix['chi'].max()], 'k--', alpha=0.5, label=r'Homogeneous ($\chi_{arch} = \chi_{global}$)')
    plt.xlabel(r"Global Concentration $\chi$"); plt.ylabel(r"Arch Additive Fraction $\chi_{arch}$")
    
    # Cambio solicitado: Leyenda arriba-izquierda interna
    plt.legend(loc='upper left', fontsize='large')
    save_plot("6-arch-composition")

    # Plot 9 & 10 (Seaborn-based)
    present = [s for s in matrix_systems if s in df_mix['sistema'].unique()]
    new_ticks = [CFG.english_labels.get(s, s) for s in present]
    
    plt.figure()
    ax = sns.violinplot(data=df_mix, x='sistema', y='Tortuosidad', hue='sistema', palette='Set2', inner='quartile', order=present, legend=False)
    ax.set_xticks(range(len(present))); ax.set_xticklabels(new_ticks, rotation=15)
    plt.xlabel(None); plt.ylabel("Tortuosity"); plt.grid(True, axis='y', alpha=0.3); save_plot("9-arch-tortuosity")

    if os.path.exists(CFG.raw_flow_path):
        df_raw = pd.read_csv(CFG.raw_flow_path)
        df_plot = pd.merge(df_raw, df_mix[['sim_hash', 'sistema', 'chi']].drop_duplicates(), on='sim_hash')
        if not df_plot.empty:
            plt.figure(); max_chi = df_plot['chi'].max()
            ax_box = sns.boxplot(data=df_plot[df_plot['chi'] == max_chi], x='sistema', y='tamano_big', hue='sistema', palette='Set3', order=present)
            ax_box.set_xticks(range(len(present))); ax_box.set_xticklabels(new_ticks, rotation=15)
            plt.xlabel(None); plt.yscale('log'); plt.ylabel("Avalanche Size (S)")
            handles = [Line2D([0], [0], color=CFG.system_style.get(s, ('black', 'o'))[0], lw=4) for s in present]
            ax_box.legend(handles, new_ticks, title="System", bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, axis='y', alpha=0.3, which="both"); save_plot("10-avalanche-boxplot")

def plot_geometric_effects_linear(df: pd.DataFrame, target_ar: float = 0.15):
    """Plot 11: Linear Scale Comparison."""
    print(f"  -> Plotting 11: Linear Scale (AR ~ {target_ar})...")
    main_dd = df['D_d_sq'].value_counts().idxmax()
    def draw_lin(sistemas, filename):
        plt.figure()
        for sis in sistemas:
            grp = filter_standard_size(df[df['D_d_sq'] == main_dd], target_ar, 0.07).copy()
            grp_sis = grp[grp['sistema'] == sis].groupby('chi').agg({'S_mean': 'mean', 'S_sem': 'mean'}).reset_index().sort_values('chi')
            if grp_sis.empty: continue
            p0, e0 = get_pure_ref(df, sis, main_dd, 'S_mean')
            color, marker = CFG.system_style.get(sis, ('black', 'o'))
            label_en = CFG.english_labels.get(sis, sis)
            plt.errorbar([0.0]+grp_sis['chi'].tolist(), [p0]+grp_sis['S_mean'].tolist(), yerr=[e0]+grp_sis['S_sem'].tolist(), fmt=f'{marker}-', color=color, label=label_en, capsize=4)
        plt.xlabel(r"Concentration $\chi$"); plt.ylabel(r"Mean Size $\langle S \rangle$")
        plt.legend(fontsize='large', loc='upper left')
        save_plot(filename)
    
    draw_lin(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], "11a-additive-linear")
    draw_lin(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], "11b-matrix-linear")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print(f"[+] Starting integrated PDF pipeline...")
    set_plot_fonts()
    if os.path.exists("figs.mplstyle"):
        plt.style.use('figs.mplstyle')
        plt.rcParams['text.usetex'] = False 
    os.makedirs(CFG.out_dir, exist_ok=True)
    df = pd.read_csv(CFG.data_path)
    df = df[df['sistema'] != 'Cuad(G)-Cuad(C)']
    sistemas_meta = [('Disco(G)-Disco(C)', 'Disk'), ('Cuad(G)-Disco(C)', 'Square'), ('Pent(G)-Disco(C)', 'Pentagon')]

    # plot_puros_vs_orificio(df)
    plot_sweeps_by_system(df, sistemas_meta)
    plot_geometric_effects(df)
    plot_geometric_effects_raw(df)
    plot_arch_analysis(df)
    plot_geometric_effects_linear(df)
    print(f"[+] All plots generated successfully in {CFG.out_dir}")

if __name__ == "__main__": 
    main()