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
    data_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/estadisticas_flujo_agregadas.csv"
    arcos_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv"
    raw_flow_path: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
    out_dir: str = "/home/juli/work/lab/project/sim-binary-shapes-2d/processed_data/5_graficos_finales"
    
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
    # save_plot("1-puros-vs-orificio", df_puros[['sistema', 'D_d_sq', 'log_S', 'log_S_err']])
    save_plot("1-puros-vs-orificio")

def plot_sweeps_by_system(df: pd.DataFrame, sistemas_objetivo: List[Tuple[str, str]]):
    """Gráficos 2 y 4: Barridos de Ratio de Área y Concentración por sistema."""
    for sist_nombre, sist_base in sistemas_objetivo:
        sist_id = clean_system_name(sist_nombre)
        print(f"\n[+] Procesando Gráficos 2 y 4 para: {sist_nombre}")
        
        # Filtramos por sistema y solo mezclas (chi > 0)
        df_mix = df[(df['sistema'] == sist_nombre) & (df['chi'] > 0.0)].copy()
        if df_mix.empty: 
            print(f"    [!] Sin datos de mezcla para {sist_nombre}. Saltando...")
            continue

        # Buscamos el tamaño de orificio más frecuente para este sistema
        main_dd = df_mix['D_d_sq'].value_counts().idxmax()
        df_mix = df_mix[df_mix['D_d_sq'] == main_dd]
        puro_val, puro_err = get_pure_reference(df, sist_base, main_dd)

        # ---------------------------------------------------------------------
        # Gráfico 2: vs Ratio de Áreas
        # ---------------------------------------------------------------------
        plt.figure(figsize=CFG.figsize_wide)
        if puro_val is not None:
            plt.axhline(puro_val, color='black', linestyle='--', label=r'Puro ($\chi = 0$)')
            plt.fill_between([df_mix['area_ratio'].min(), df_mix['area_ratio'].max()], 
                             puro_val - puro_err, puro_val + puro_err, color='black', alpha=0.1)

        chis_interes = [0.01, 0.1, 0.14, 0.2]
        cmap = cm.plasma
        norm = mcolors.Normalize(vmin=min(chis_interes), vmax=max(chis_interes))

        for chi in chis_interes:
            grp = df_mix[np.isclose(df_mix['chi'], chi, atol=1e-3)].sort_values('area_ratio')
            if not grp.empty:
                # Usamos rf"" para evitar SyntaxWarning con \chi
                plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'], 
                             fmt='o-', color=cmap(norm(chi)), label=rf"$\chi$ = {chi}", capsize=3)

        plt.xlabel(r"Ratio de Áreas ($A_S/A_L$)")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Efecto del Tamaño del Aditivo ({sist_nombre})")
        plt.legend(title="Concentración", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        save_plot(f"2-{sist_id}-vs-area-ratio")

        # ---------------------------------------------------------------------
        # Gráfico 4: vs Concentración (Curvas de Atascamiento)
        # ---------------------------------------------------------------------
        plt.figure(figsize=CFG.figsize_std)
        
        # Targets de área y tolerancia para capturar polígonos
        ratios_target = [0.1, 0.2, 0.4, 0.5]
        tolerancia = 0.05 

        for target in ratios_target:
            # 1. Filtramos por proximidad al target
            mask = (df_mix['area_ratio'] >= target - tolerancia) & \
                (df_mix['area_ratio'] <= target + tolerancia)
            grp_raw = df_mix[mask].copy()

            if grp_raw.empty: 
                continue
            
            # 2. CONSOLIDACIÓN: Promediamos puntos con la misma concentración 'chi'
            #    - log_S: se promedia aritméticamente.
            #    - log_S_err: se propaga como la raíz de la suma de cuadrados dividida por N.
            grp = grp_raw.groupby('chi').agg({
                'log_S': 'mean',
                'log_S_err': lambda x: np.sqrt(np.sum(np.square(x))) / len(x)
            }).reset_index()

            # Imprimimos en terminal para control del usuario
            areas_reales = grp_raw['area_ratio'].unique()
            print(f"    -> Target {target}: Consolidando {len(grp_raw)} puntos en {len(grp)} niveles de chi.")
            print(f"       Áreas detectadas: {np.round(areas_reales, 4)}")
            
            # 3. Ordenamos por concentración para evitar zigzags en la línea
            grp = grp.sort_values('chi')
            x = grp['chi'].tolist()
            y = grp['log_S'].tolist()
            yerr = grp['log_S_err'].tolist()

            # 4. Agregamos el punto inicial del sistema puro (chi = 0) si existe
            if puro_val is not None:
                x = [0.0] + x
                y = [puro_val] + y
                yerr = [puro_err] + yerr

            # 5. Graficado
            plt.errorbar(x, y, yerr=yerr, fmt='s-', 
                        label=rf"AR $\approx$ {target}", 
                        capsize=3, markersize=5)

        # Configuración estética del gráfico
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Curvas de Atascamiento ({sist_nombre})")
        plt.legend(title="Ratio de Área", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout() # Ajuste para que la leyenda no se corte
        
        # Guardado (asumiendo que save_plot existe en tu entorno)
        save_plot(f"4-{sist_id}-vs-chi-tamanos")

def plot_geometric_effects(df: pd.DataFrame, target_ar: float = 0.15):
    """
    Gráfico 5: Comparación de efectos geométricos (Normalizados).
    target_ar: Área común para que la comparación de formas sea justa.
    """
    df_mix = df[df['chi'] > 0].copy()
    
    # 1. Filtramos por el orificio más frecuente para que el D/d sea el mismo
    main_dd = df_mix['D_d_sq'].value_counts().idxmax()
    df_mix = df_mix[df_mix['D_d_sq'] == main_dd]

    # 2. Normalización respecto al puro de referencia
    # (S0 es el tamaño de avalancha del sistema puro de la MATRIZ correspondiente)
    df_puros = df[df['chi'] == 0][['grano_base', 'D_d_sq', 'S_mean', 'S_sem']].rename(
        columns={'S_mean': 'S0', 'S_sem': 'S0_err'}
    )
    df_norm = pd.merge(df_mix, df_puros, on=['grano_base', 'D_d_sq'], how='inner')
    
    # Cálculo del valor normalizado y su error propagado
    df_norm['log_S_norm'] = np.log((df_norm['S_mean'] / df_norm['S0']) + 1)
    # Error propagado (aproximación funcional: delta_S / (S + S0))
    df_norm['log_S_norm_err'] = df_norm['S_sem'] / (df_norm['S_mean'] + df_norm['S0'])

    def draw_comparison(sistemas, filename, title):
        plt.figure(figsize=CFG.figsize_std)
        # Agregamos el punto chi=0 (S0/S0 + 1 = 2) común a todos los sistemas
        
        for sis in sistemas:
            # Filtro por sistema
            grp_sis = df_norm[df_norm['sistema'] == sis].copy()
            if grp_sis.empty: continue
            
            # 3. FILTRO DE ÁREA CRUCIAL: Solo comparamos granos de tamaño similar (Target AR)
            # Usamos atol=0.07 para capturar tanto 0.1 como 0.15 y compararlos honestamente
            grp = grp_sis[np.isclose(grp_sis['area_ratio'], target_ar, atol=0.07)].copy()
            
            if grp.empty:
                print(f"    [!] {sis} no tiene datos para AR ≈ {target_ar}. Saltando.")
                continue

            # 4. CONSOLIDACIÓN: Promediamos por chi para limpiar el gráfico y capturar el chi=0.3
            grp = grp.groupby('chi').agg({
                'log_S_norm': 'mean', 
                'log_S_norm_err': lambda x: np.sqrt(np.sum(np.square(x))) / len(x)
            }).reset_index().sort_values('chi')

            # Preparamos vectores (incluyendo el punto chi=0)
            x = [0.0] + grp['chi'].tolist()
            y = [np.log(2.0)] + grp['log_S_norm'].tolist()
            yerr = [0.0] + grp['log_S_norm_err'].tolist()
            
            plt.errorbar(x, y, yerr=yerr, fmt=f"{CFG.marker_map.get(sis, 'X')}-", 
                         label=sis, capsize=4, alpha=0.9)
        
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"Log-S Normalizado $\ln(\langle S \rangle / \langle S_0 \rangle + 1)$")
        plt.title(rf"{title} (AR $\approx$ {target_ar})")
        plt.legend(fontsize='small')
        plt.grid(True, alpha=0.3)
        save_plot(filename)

    print(f"  -> Generando Gráficos 5a y 5b corregidos (Target AR: {target_ar})...")
    
    # 5a: Matriz Disco fija, variamos la forma del aditivo (chico)
    draw_comparison(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], 
                   "5a-efecto-aditivo", "Efecto de la Forma del Aditivo")
    
    # 5b: Aditivo Disco fijo (chico), variamos la forma de la matriz
    draw_comparison(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], 
                   "5b-efecto-matriz", "Efecto de la Forma de la Matriz")



def plot_arch_analysis():
    """Análisis de composición y morfología de arcos (Gráficos 6-10)."""
    if not os.path.exists(CFG.arcos_path): return
    df = pd.read_csv(CFG.arcos_path)
    
    # Gráfico 6: Composición Global
    print("  -> Generando Gráfico 6: Composición Arcos...")
    # df_mix = df[(df['chi'] > 0) & (df['chi'] <= 0.2)].copy()
    df_mix = df[df['chi'] > 0].copy()
    df_mix['frac_arco'] = df_mix['Particulas_Tipo_1'] / df_mix['Total_Particulas_Arco']
    
    plt.figure(figsize=CFG.figsize_wide)
    
    df_mix = df[(df['chi'] > 0) & (np.isclose(df['area_ratio'], 0.15, atol=0.07))].copy() # Agregue esto
    sns.lineplot(data=df_mix, x='chi', y='frac_arco', hue='system_type', marker='o', err_style="bars")

    max_chi = df_mix['chi'].max()
    plt.plot([0, max_chi], [0, max_chi], 'k--', alpha=0.7, label='Homogénea')
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


def plot_geometric_effects_linear(df: pd.DataFrame, target_ar: float = 0.15):
    """
    Gráfico 11: Comparación de efectos geométricos (Lineal).
    Muestra <S> directamente sin escala logarítmica.
    """
    print(f"  -> Generando Gráficos 11a y 11b: Efectos Geométricos (Lineales, AR ≈ {target_ar})...")
    
    # Filtramos por el orificio principal
    main_dd = df['D_d_sq'].value_counts().idxmax()
    df_plot = df[df['D_d_sq'] == main_dd].copy()

    def draw_comparison_linear(sistemas, filename, title):
        plt.figure(figsize=CFG.figsize_std)
        
        for sis in sistemas:
            grp_sis = df_plot[df_plot['sistema'] == sis].copy()
            if grp_sis.empty: continue
            
            # Filtro de área con tolerancia para que no se pierda el chi=0.3
            grp = grp_sis[np.isclose(grp_sis['area_ratio'], target_ar, atol=0.07)].copy()
            
            if grp.empty: continue
            
            # Agrupamos por chi para limpiar ruidos
            grp = grp.groupby('chi').agg({
                'S_mean': 'mean',
                'S_sem': lambda x: np.sqrt(np.sum(np.square(x))) / len(x)
            }).reset_index().sort_values('chi')
            
            plt.errorbar(grp['chi'], grp['S_mean'], yerr=grp['S_sem'], 
                         fmt=f"{CFG.marker_map.get(sis, 'o')}-", 
                         label=f"{sis}", capsize=4)
        
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"Tamaño Medio $\langle S \rangle$")
        # El prefijo 'rf' es vital aquí por el \approx
        plt.title(rf"{title} (AR $\approx$ {target_ar})")
        plt.legend(fontsize='small')
        plt.grid(True, alpha=0.3)
        save_plot(filename)

    # Llamadas con el set de sistemas que definiste
    draw_comparison_linear(['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)'], 
                           "11a-efecto-aditivo-lineal", "Efecto del Aditivo (Matriz Disco)")
    
    draw_comparison_linear(['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)'], 
                           "11b-efecto-matriz-lineal", "Efecto de la Matriz (Aditivo Disco)")



def plot_geometric_effects_raw(df: pd.DataFrame, target_ar: float = 0.15):
    """
    Gráfico 5c: Comparación de efectos de la matriz usando ln(S_mean + 1).
    Usa el prefijo rf"" para evitar errores de LaTeX con \approx.
    """
    print(f"  -> Generando Gráfico 5c: Efecto Matriz (Target AR ≈ {target_ar})...")
    
    main_dd = df['D_d_sq'].value_counts().idxmax()
    df_plot = df[df['D_d_sq'] == main_dd].copy()

    sistemas_matriz = ['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)']
    
    plt.figure(figsize=CFG.figsize_std)
    
    for sis in sistemas_matriz:
        grp_sis = df_plot[df_plot['sistema'] == sis].copy()
        if grp_sis.empty: continue
        
        # Filtro de área con tolerancia
        grp = grp_sis[np.isclose(grp_sis['area_ratio'], target_ar, atol=0.07)].copy()
        if grp.empty: continue

        # Consolidación por chi para evitar ruidos
        grp = grp.groupby('chi').agg({
            'S_mean': 'mean',
            'S_sem': lambda x: np.sqrt(np.sum(np.square(x))) / len(x)
        }).reset_index().sort_values('chi')

        # Transformación logarítmica
        y_vals = np.log(grp['S_mean'] + 1)
        y_errs = grp['S_sem'] / (grp['S_mean'] + 1)
        
        plt.errorbar(grp['chi'], y_vals, yerr=y_errs, 
                     fmt=f"{CFG.marker_map.get(sis, 'o')}-", 
                     label=sis, capsize=4)
    
    plt.xlabel(r"Concentración $\chi$")
    plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
    
    # EL FIX: Usamos rf"" para que \approx no rompa el script
    plt.title(rf"Efecto de la Matriz (AR $\approx$ {target_ar} - Crudo)")
    
    plt.legend()
    plt.grid(True, alpha=0.3)
    save_plot("5c-efecto-matriz-raw")

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

# =============================================================================
# RESUMEN DE MÓDULOS DE GRAFICADO
# =============================================================================
# plot_puros_vs_orificio(df): Evalúa discos puros vs tamaño de orificio (D/d)^2.
# plot_sweeps_by_system(df, sistemas): Barridos de Ratio de Área y Concentración (chi) por sistema.
# plot_geometric_effects(df): Comparación de formas (Aditivo/Matriz) normalizada respecto al puro.
# plot_arch_analysis(): Morfología de arcos (composición, tortuosidad) y boxplots de dispersión.
# plot_geometric_effects_linear(df): Idem Gráfico 5 pero en escala lineal para <S>.
# plot_geometric_effects_raw(df): Efecto de la matriz en valores crudos (sin normalizar).
    
    plot_sweeps_by_system(df, sistemas)
    plot_arch_analysis()
    plot_geometric_effects(df)
    plot_geometric_effects_raw(df)
    plot_geometric_effects_linear(df)   # Gráfico 11 (Igual al 5 pero lineal)    plot_arch_analysis()
    

    print(f"[+] ¡Listo! Proceso de análisis visual completado.")

if __name__ == "__main__":
    main()