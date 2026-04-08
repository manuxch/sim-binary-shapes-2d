import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import seaborn as sns

# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================
DATA_PATH = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/estadisticas_flujo_agregadas.csv"
ARCOS_PATH = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_arcos.csv"
OUT_DIR = "/work/lab/project/sim-binary-shapes-2d/processed_data/5_graficos_finales"

def main():
    """
    Main execution function that orchestrates the generation of high-quality plots (SVG/PNG) 
    and their corresponding data tables (CSV) from processed avalanche and arch data.
    
    It covers several analysis categories:
    1. Pure disks vs Orifice ratio.
    2. Size and concentration sweeps for specific binary systems.
    3. Avalanche size vs concentration for specific area ratios.
    4. Geometric effects of additives and matrices on clogging.
    5. Arch composition vs global composition.
    6. Arch morphology (tortuosity).
    7. Statistical dispersion (boxplots).
    """
    print("[+] Generando gráficos finales de alta calidad (SVG y CSV)...")
    
    if not os.path.exists(DATA_PATH):
        print(f" [!] Error: No se encontró {DATA_PATH}.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATA_PATH)
    df = df[df['sistema'] != 'Cuad(G)-Cuad(C)']

    # =========================================================================
    # GRÁFICO 1: Discos Puros vs Orificio (D/d)^2
    # =========================================================================
    print("  -> Generando Gráfico 1: Puros vs Orificio...")
    df_puros = df[(df['chi'] == 0.0) & 
                  (df['sistema'].str.startswith('Disco')) & 
                  (df['D_d_sq'].notnull())].copy()
    
    if not df_puros.empty:
        df_puros = df_puros.sort_values('D_d_sq')
        cols_export = ['sistema', 'D_d_sq', 'S_mean', 'S_sem', 'log_S', 'log_S_err']
        df_puros[cols_export].to_csv(f"{OUT_DIR}/1-puros-vs-orificio.csv", index=False)

        plt.figure(figsize=(8, 6))
        plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                     fmt='o-', color='black', capsize=4, label='Discos Puros')
        
        plt.xlabel(r"Ratio de Orificio $(D/d)^2$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title("Efecto del Tamaño del Orificio de Descarga")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(f"{OUT_DIR}/1-puros-vs-orificio.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # DEFINICIÓN DE SISTEMAS PARA GRÁFICOS 2, 3 Y 4
    # =========================================================================
    sistemas_objetivo = [
        ('Disco(G)-Disco(C)', 'Disco'),
        ('Cuad(G)-Disco(C)', 'Cuad'),
        ('Pent(G)-Disco(C)', 'Pent')
    ]

    # =========================================================================
    # GRÁFICO 2 y 4: Barrido de Tamaños y Concentración por Sistema
    # =========================================================================
    for sist_nombre, sist_base in sistemas_objetivo:
        sist_id = sist_nombre.lower().replace('(', '').replace(')', '').replace('_', '-').replace('-g-','-').replace('-c','')
        print(f"  -> Procesando Gráficos 2 y 4 para sistema: {sist_nombre}...")
        
        df_dd = df[(df['sistema'] == sist_nombre) & (df['chi'] > 0.0)].copy()
        
        if not df_dd.empty:
            main_D_d_sq = df_dd['D_d_sq'].value_counts().idxmax()
            df_dd = df_dd[df_dd['D_d_sq'] == main_D_d_sq]
            
            df_base = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith(sist_base)) & (df['D_d_sq'] == main_D_d_sq)]
            df_export_g2 = pd.concat([df_base, df_dd]).sort_values(['chi', 'area_ratio'])
            cols_export = ['sistema', 'chi', 'area_ratio', 'D_d_sq', 'S_mean', 'S_sem', 'log_S', 'log_S_err']
            
            df_export_g2[cols_export].to_csv(f"{OUT_DIR}/2-{sist_id}-vs-area-ratio.csv", index=False)

            chis_deseados = [0.2, 0.1, 0.14, 0.01]
            df_plot = df_dd[df_dd['chi'].isin(chis_deseados)]

            # Generación Gráfico 2
            plt.figure(figsize=(9, 6))
            if not df_base.empty:
                base_val = df_base['log_S'].mean()
                base_err = df_base['log_S_err'].mean()
                plt.axhline(base_val, color='black', linestyle='--', linewidth=2, label=r'Puro ($\chi = 0$)')
                x_min, x_max = df_plot['area_ratio'].min(), df_plot['area_ratio'].max()
                plt.fill_between([x_min, x_max], base_val - base_err, base_val + base_err, color='black', alpha=0.1)

            chis = np.sort(df_plot['chi'].unique())
            cmap = cm.plasma 
            norm = mcolors.Normalize(vmin=chis.min(), vmax=chis.max())

            for chi_val in chis:
                grp = df_plot[df_plot['chi'] == chi_val].sort_values('area_ratio')
                color_linea = cmap(norm(chi_val))
                plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'], 
                             fmt='s-', color=color_linea, label=rf"$\chi$ = {chi_val}", capsize=3, alpha=0.85, linewidth=1.5)
                
            plt.xlabel(r"Ratio de Áreas ($A_S/A_L$)")
            plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
            plt.title(f"Efecto del Tamaño del Aditivo ({sist_nombre}) (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
            plt.legend(title="Concentración", bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, alpha=0.3)
            plt.savefig(f"{OUT_DIR}/2-{sist_id}-vs-area-ratio.png", bbox_inches='tight', format='png')
            plt.close()

            # Generación Gráfico 4
            min_puntos = 3
            plt.figure(figsize=(8, 6))
            for area_ratio, grp in df_dd.groupby('area_ratio'):
                if len(grp) < min_puntos:
                    continue 
                
                grp = grp.sort_values('chi')
                plt.errorbar(grp['chi'], grp['log_S'], yerr=grp['log_S_err'], 
                             fmt='^-', label=f"Ratio Área = {area_ratio:.2f}", capsize=4)
                
            plt.xlabel(r"Concentración $\chi$")
            plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
            plt.title(f"Curvas de Atascamiento por Tamaño ({sist_nombre}) (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
            plt.legend(title="Tamaño Aditivo", bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, alpha=0.3)
            plt.savefig(f"{OUT_DIR}/4-{sist_id}-vs-chi-tamanos.png", bbox_inches='tight', format='png')
            plt.close()

    # =========================================================================
    # GRÁFICO 3: log_S vs Concentración (chi) para Ratios de Área Específicos
    # =========================================================================
    ratios_deseados = [0.1, 0.3, 0.4, 0.8, 1.0] 
    
    for sist_nombre, sist_base in sistemas_objetivo:
        sist_id = sist_nombre.lower().replace('(', '').replace(')', '').replace('_', '-').replace('-g-','-').replace('-c','')
        print(f"  -> Procesando Gráfico 3 para sistema: {sist_nombre}...")
        
        df_mezcla = df[(df['sistema'] == sist_nombre) & (df['chi'] > 0.0)].copy()
        
        if not df_mezcla.empty:
            main_D_d_sq = df_mezcla['D_d_sq'].value_counts().idxmax()
            df_mezcla = df_mezcla[df_mezcla['D_d_sq'] == main_D_d_sq]
            df_mezcla['area_ratio_round'] = df_mezcla['area_ratio'].round(3)
            
            df_puro = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith(sist_base)) & (df['D_d_sq'] == main_D_d_sq)]
            
            plt.figure(figsize=(9, 6))
            cmap = cm.viridis 
            norm = mcolors.Normalize(vmin=min(ratios_deseados), vmax=max(ratios_deseados))
            
            puro_val, puro_err = None, None
            if not df_puro.empty:
                puro_val = df_puro['log_S'].mean()
                puro_err = df_puro['log_S_err'].mean()
                plt.errorbar([0], [puro_val], yerr=[puro_err], fmt='k*', markersize=10, 
                             label=r'Puro ($\chi = 0$)', capsize=3, zorder=5)

            for ar in ratios_deseados:
                grp = df_mezcla[df_mezcla['area_ratio_round'] == round(ar, 3)].sort_values('chi')
                
                if not grp.empty:
                    x_data = grp['chi'].tolist()
                    y_data = grp['log_S'].tolist()
                    y_err = grp['log_S_err'].tolist()
                    
                    if puro_val is not None:
                        x_data = [0.0] + x_data
                        y_data = [puro_val] + y_data
                        y_err = [puro_err] + y_err

                    color_linea = cmap(norm(ar))
                    plt.errorbar(x_data, y_data, yerr=y_err, fmt="o-", color=color_linea, 
                                 label=rf"Ratio de Área = {ar}", capsize=3, alpha=0.85, linewidth=2)
                    
            plt.xlabel(r"Concentración ($\chi$)")
            plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
            plt.title(f"Tamaño de Avalancha vs Concentración ({sist_nombre}) (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
            plt.legend(title="Configuración", bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, alpha=0.3)
            plt.savefig(f"{OUT_DIR}/3-{sist_id}-logs-vs-chi.png", bbox_inches='tight', format='png')
            plt.close()


    # =========================================================================
    # GRÁFICO 4b: Disco(G)-Disco(C) para area_ratio = 0.4 y 0.5 vs chi (+ puro)
    # =========================================================================
    print("  -> Generando Gráfico 4b: Disco-Disco (ratios 0.4 y 0.5) vs chi...")

    sist_nombre = 'Disco(G)-Disco(C)'
    sist_base = 'Disco'
    sist_id = 'disco-disco-ratios-04-05'

    df_subset = df[(df['sistema'] == sist_nombre) & (df['chi'] > 0.0)].copy()

    if not df_subset.empty:
        main_D_d_sq = df_subset['D_d_sq'].value_counts().idxmax()
        df_subset = df_subset[df_subset['D_d_sq'] == main_D_d_sq]

        # --- CASO PURO (χ = 0)
        df_puro = df[
            (df['chi'] == 0.0) &
            (df['sistema'].str.startswith(sist_base)) &
            (df['D_d_sq'] == main_D_d_sq)
        ]

        puro_val, puro_err = None, None
        if not df_puro.empty:
            puro_val = df_puro['log_S'].mean()
            puro_err = df_puro['log_S_err'].mean()

        df_subset['area_ratio_round'] = df_subset['area_ratio'].round(3)
        ratios_target = [0.4, 0.5]

        plt.figure(figsize=(8, 6))

        for ar in ratios_target:
            grp = df_subset[df_subset['area_ratio_round'] == round(ar, 3)].sort_values('chi')

            if grp.empty:
                continue

            x_vals = grp['chi'].tolist()
            y_vals = grp['log_S'].tolist()
            y_errs = grp['log_S_err'].tolist()

            # --- agregar punto puro
            if puro_val is not None:
                x_vals = [0.0] + x_vals
                y_vals = [puro_val] + y_vals
                y_errs = [puro_err] + y_errs

            plt.errorbar(
                x_vals, y_vals, yerr=y_errs,
                fmt='o-', label=f"Ratio Área = {ar}", capsize=4
            )

        # marcar el puro explícitamente (opcional pero recomendable)
        if puro_val is not None:
            plt.errorbar(
                [0], [puro_val], yerr=[puro_err],
                fmt='k*', markersize=10,
                label=r'Puro ($\chi = 0$)', zorder=5
            )

        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Disco-Disco: Efecto de $\chi$ (Ratios 0.4 y 0.5)\n(Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.savefig(f"{OUT_DIR}/4b-{sist_id}-vs-chi.png", bbox_inches='tight', format='png')
        plt.close()


    # =========================================================================
    # FUNCIONES AUXILIARES PARA GRÁFICO 5
    # =========================================================================
    def graficar_forma_vs_chi(df_subset, sistemas, marcadores, filename_base, titulo_base):
        """
        Generates absolute and normalized plots of log avalanche size versus concentration 
        for a group of systems to compare geometric effects.
        
        Args:
            df_subset (pd.DataFrame): Dataframe containing the aggregated flow statistics.
            sistemas (list): List of system names to include in the plot.
            marcadores (dict): Mapping of system names to matplotlib marker styles.
            filename_base (str): Base name for the exported files (PNG and CSV).
            titulo_base (str): Base title for the plots.
        """
        datos_export = []
        
        # Figura 1: Absoluto
        plt.figure(figsize=(8, 6))
        for sis in sistemas:
            if sis not in df_subset['sistema'].unique():
                continue
            df_sis = df_subset[df_subset['sistema'] == sis]
            main_ar = df_sis['area_ratio'].value_counts().idxmax()
            grp = df_sis[df_sis['area_ratio'] == main_ar].sort_values('chi')
            
            x_vals = grp['chi'].tolist()
            y_vals = grp['log_S'].tolist()
            y_errs = grp['log_S_err'].tolist()
            
            if 0.0 not in x_vals:
                x_vals.insert(0, 0.0)
                s_0 = grp['S_mean_0'].iloc[0]
                s_0_err = grp['S_sem_0'].iloc[0]
                y_vals.insert(0, np.log(s_0 + 1))
                y_errs.insert(0, s_0_err / (s_0 + 1))
            
            marker = marcadores.get(sis, 'X')
            plt.errorbar(x_vals, y_vals, yerr=y_errs, fmt=f'{marker}-', label=f"{sis}", capsize=4)
        
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"{titulo_base} (Absoluto)")
        plt.legend(title="Geometría del Sistema", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.savefig(f"{OUT_DIR}/{filename_base}-absoluto.png", bbox_inches='tight', dpi=300)
        plt.close()

        # Figura 2: Normalizado
        plt.figure(figsize=(8, 6))
        for sis in sistemas:
            if sis not in df_subset['sistema'].unique():
                continue
            df_sis = df_subset[df_subset['sistema'] == sis]
            main_ar = df_sis['area_ratio'].value_counts().idxmax()
            grp = df_sis[df_sis['area_ratio'] == main_ar].sort_values('chi')
            
            x_vals = grp['chi'].tolist()
            y_vals_norm = grp['log_S_norm'].tolist()
            y_errs_norm = grp['log_S_err_norm'].tolist()
            
            if 0.0 not in x_vals:
                x_vals.insert(0, 0.0)
                y_vals_norm.insert(0, np.log(2.0))
                y_errs_norm.insert(0, 0.0)
            
            for i, x in enumerate(x_vals):
                # Usar variables extraídas del DataFrame original para exportación consistente
                y_abs = grp['log_S'].iloc[i-1] if i > 0 else np.log(grp['S_mean_0'].iloc[0] + 1)
                y_abs_err = grp['log_S_err'].iloc[i-1] if i > 0 else grp['S_sem_0'].iloc[0]/(grp['S_mean_0'].iloc[0]+1)
                
                datos_export.append({
                    'sistema': sis,
                    'area_ratio_fijado': main_ar,
                    'chi': x,
                    'log_S_abs': y_abs,
                    'log_S_err_abs': y_abs_err,
                    'log_S_norm': y_vals_norm[i],
                    'log_S_err_norm': y_errs_norm[i]
                })

            marker = marcadores.get(sis, 'X')
            plt.errorbar(x_vals, y_vals_norm, yerr=y_errs_norm, fmt=f'{marker}-', label=f"{sis}", capsize=4)
            
        pd.DataFrame(datos_export).to_csv(f"{OUT_DIR}/{filename_base}-data.csv", index=False)
        
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle / \langle S \rangle_0 + 1)$")
        plt.title(f"{titulo_base} (Normalizado)")
        plt.legend(title="Geometría del Sistema", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.savefig(f"{OUT_DIR}/{filename_base}-norm.png", bbox_inches='tight', dpi=300)
        plt.close()

    # =========================================================================
    # PREPARACIÓN DE DATOS PARA GRÁFICOS 5A Y 5B
    # =========================================================================
    df_mezclas = df[~df['sistema'].str.contains('Puro', case=False)].copy()
    if not df_mezclas.empty and 'D_d_sq' in df_mezclas.columns:
        main_D_d_sq_global = df_mezclas['D_d_sq'].value_counts().idxmax()
        df_mezclas = df_mezclas[df_mezclas['D_d_sq'] == main_D_d_sq_global]

        df_puros_ref = df[df['chi'] == 0.0][['grano_base', 'D_d_sq', 'S_mean', 'S_sem']].drop_duplicates()
        df_puros_ref = df_puros_ref.rename(columns={'S_mean': 'S_mean_0', 'S_sem': 'S_sem_0'})
        df_formas = pd.merge(df_mezclas, df_puros_ref, on=['grano_base', 'D_d_sq'], how='inner')
        
        if not df_formas.empty:
            df_formas['val_norm'] = df_formas['S_mean'] / df_formas['S_mean_0']
            df_formas['err_norm'] = df_formas['val_norm'] * np.sqrt(
                (df_formas['S_sem'] / df_formas['S_mean'])**2 + 
                (df_formas['S_sem_0'] / df_formas['S_mean_0'])**2
            )
            df_formas['log_S_norm'] = np.log(df_formas['val_norm'] + 1)
            df_formas['log_S_err_norm'] = df_formas['err_norm'] / (df_formas['val_norm'] + 1)

            # --- Gráfico 5a: Variación de Aditivo en Matriz de Discos ---
            print("  -> Generando Gráfico 5a: Aditivos en Matriz de Discos...")
            sistemas_5a = ['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)', 'Disco(G)-Tri(C)']
            marcadores_5a = {'Disco(G)-Disco(C)': 'o', 'Disco(G)-Tri(C)': '^', 'Disco(G)-Cuad(C)': 's', 'Disco(G)-Pent(C)': 'p'}
            graficar_forma_vs_chi(df_formas, sistemas_5a, marcadores_5a, "5a-efecto-aditivo-matriz-disco", "Efecto Geométrico del Aditivo en Discos")

            # --- Gráfico 5b: Variación de Matriz con Aditivo de Discos ---
            print("  -> Generando Gráfico 5b: Matriz Variable con Aditivo de Discos...")
            sistemas_5b = ['Disco(G)-Disco(C)', 'Cuad(G)-Disco(C)', 'Pent(G)-Disco(C)', 'Tri(G)-Disco(C)']
            marcadores_5b = {'Disco(G)-Disco(C)': 'o', 'Tri(G)-Disco(C)': '^', 'Cuad(G)-Disco(C)': 's', 'Pent(G)-Disco(C)': 'p'}
            graficar_forma_vs_chi(df_formas, sistemas_5b, marcadores_5b, "5b-efecto-matriz-aditivo-disco", "Efecto Geométrico de la Matriz Base")

    # =========================================================================
    # GRÁFICO 6: Composición del Arco vs. Composición Global
    # =========================================================================
    print("  -> Generando Gráfico 6: Composición Local vs Global (Arcos)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)

        sistemas_a_excluir = ['Cuad-Cuad', 'Disco-Cuad', 'Disco-Pent', 'Disco-Tri']
        df_arcos = df_arcos[~df_arcos['system_type'].isin(sistemas_a_excluir)]
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty:
            df_arcos_mezclas['Fraccion_Chicas_Arco'] = df_arcos_mezclas['Particulas_Tipo_1'] / df_arcos_mezclas['Total_Particulas_Arco']
            
            cols_export_g5 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Particulas_Tipo_1', 'Fraccion_Chicas_Arco']
            df_arcos_mezclas[cols_export_g5].to_csv(f"{OUT_DIR}/6-composicion-arcos.csv", index=False)

            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            ax = sns.lineplot(
                data=df_arcos_mezclas, x='chi', y='Fraccion_Chicas_Arco', hue='system_type', 
                style='system_type', markers=True, dashes=False, linewidth=2.5,
                err_style="bars", errorbar=('ci', 95), err_kws={'capsize': 4}
            )

            min_chi, max_chi = df_arcos_mezclas['chi'].min(), df_arcos_mezclas['chi'].max()
            plt.plot([0, max_chi], [0, max_chi], 'k--', linewidth=2, alpha=0.7, label='Mezcla Homogénea (y=x)')

            plt.title("Preferencialidad de Atascamiento:\nComposición del Arco vs. Composición Global")
            plt.xlabel(r"Fracción Global de Partículas Chicas ($\chi$)")
            plt.ylabel("Fracción de Chicas en el Arco")
            
            plt.legend(title='Geometría', bbox_to_anchor=(1.05, 1), loc='upper left')
            sns.despine() 
            plt.grid(True, alpha=0.3)
            
            plt.savefig(f"{OUT_DIR}/6-composicion-arcos.png", bbox_inches='tight', format='png')
            plt.close()
            plt.rcdefaults() 

    # =========================================================================
    # GRÁFICO 7: Composición del Arco vs. Composición Global por Tamaño
    # =========================================================================
    print("  -> Generando Gráfico 7: Composición Local vs Global (Arcos) por Tamaño de Aditivo...")
    if os.path.exists(ARCOS_PATH):
        df_arcos_g7 = pd.read_csv(ARCOS_PATH)
        
        if 'r_ratio' in df_arcos_g7.columns:
            df_arcos_g7['area_ratio'] = df_arcos_g7['r_ratio'] ** 2
            if df_arcos_g7['area_ratio'].max() > 1.1: 
                df_arcos_g7['area_ratio'] = 1.0 / df_arcos_g7['area_ratio']

        sistemas_arcos = ['Disco-Disco', 'Cuad-Disco', 'Pent-Disco']
        
        for sist_arco in sistemas_arcos:
            sist_arco_id = sist_arco.lower().replace('-', '-')
            print(f"     -> Procesando sistema: {sist_arco}...")
            
            df_arcos_mezclas = df_arcos_g7[(df_arcos_g7['chi'] > 0.0) & (df_arcos_g7['system_type'] == sist_arco)].copy()
            df_arcos_mezclas = df_arcos_mezclas[df_arcos_mezclas['Total_Particulas_Arco'] > 0]
            
            if not df_arcos_mezclas.empty and 'area_ratio' in df_arcos_mezclas.columns:
                target_area_ratios = [0.4, 0.6, 0.8]
                df_arcos_mezclas['area_ratio_round'] = df_arcos_mezclas['area_ratio'].round(1)
                
                df_plot = df_arcos_mezclas[df_arcos_mezclas['area_ratio_round'].isin(target_area_ratios)].copy()
                
                if not df_plot.empty:
                    df_plot['Fraccion_Chicas_Arco'] = df_plot['Particulas_Tipo_1'] / df_plot['Total_Particulas_Arco']
                    
                    col_agrupacion = 'area_ratio_round_str'
                    df_plot[col_agrupacion] = df_plot['area_ratio_round'].astype(str)
                    titulo_leyenda = 'Ratio de Área'
                    
                    orden_leyenda = sorted(df_plot[col_agrupacion].unique(), key=float)

                    cols_export_g5 = ['sim_hash', col_agrupacion, 'chi', 'Total_Particulas_Arco', 'Particulas_Tipo_1', 'Fraccion_Chicas_Arco']
                    cols_export_g5 = [c for c in cols_export_g5 if c in df_plot.columns]
                    df_plot[cols_export_g5].to_csv(f"{OUT_DIR}/7-{sist_arco_id}-composicion-arcos-tamanos.csv", index=False)

                    sns.set_theme(style="ticks", context="notebook")
                    plt.figure(figsize=(9, 6))

                    ax = sns.lineplot(
                        data=df_plot, x='chi', y='Fraccion_Chicas_Arco', hue=col_agrupacion, 
                        style=col_agrupacion, hue_order=orden_leyenda, style_order=orden_leyenda,
                        palette='viridis', markers=True, dashes=False, linewidth=2.5,
                        err_style="bars", errorbar=('ci', 95), err_kws={'capsize': 4}
                    )

                    max_chi = df_plot['chi'].max()
                    plt.plot([0, max_chi], [0, max_chi], 'k--', linewidth=2, alpha=0.7, label='Mezcla Homogénea (y=x)', zorder=0)

                    plt.title(f"Preferencialidad de Atascamiento:\nComposición del Arco vs. Global ({sist_arco})")
                    plt.xlabel(r"Fracción Global de Partículas Chicas ($\chi$)")
                    plt.ylabel("Fracción de Chicas en el Arco")
                    
                    handles, labels = ax.get_legend_handles_labels()
                    plt.legend(handles=handles, labels=labels, title=titulo_leyenda, bbox_to_anchor=(1.05, 1), loc='upper left')
                    
                    sns.despine()
                    plt.grid(True, alpha=0.3)
                    
                    plt.savefig(f"{OUT_DIR}/7-{sist_arco_id}-composicion-arcos-tamanos.png", bbox_inches='tight', format='png')
                    plt.close()
                    
                    plt.rcdefaults() 
                    sns.reset_defaults()

    # =========================================================================
    # GRÁFICO 8: Composición del Arco vs. Ratio de ÁREAS (chi=0.1 vs chi=0.01)
    # =========================================================================
    print("  -> Generando Gráfico 8: Composición de Arcos vs Ratio de ÁREAS...")
    if os.path.exists(ARCOS_PATH):
        df_arcos_g8 = pd.read_csv(ARCOS_PATH)
        
        df_arcos_g8['Fraccion_Chicas_Arco'] = df_arcos_g8['Particulas_Tipo_1'] / df_arcos_g8['Total_Particulas_Arco']
        df_arcos_g8['area_ratio'] = df_arcos_g8['r_ratio']**2
        columna_x = 'area_ratio' 

        target_chis = [0.1, 0.01]
        df_plot = df_arcos_g8[df_arcos_g8['chi'].isin(target_chis)].copy()
        
        if not df_plot.empty:
            df_plot = df_plot.sort_values(by='chi', ascending=False)

            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            ax = sns.lineplot(
                data=df_plot, x=columna_x, y='Fraccion_Chicas_Arco', hue='chi',
                palette="viridis", markers=True, dashes=False, linewidth=2.5,
                err_style="bars", errorbar=('ci', 95), err_kws={'capsize': 4}
            )

            plt.axhline(y=0.1, color='green', linestyle='--', alpha=0.5, label=r'Referencia $\chi=0.1$')
            plt.axhline(y=0.01, color='purple', linestyle='--', alpha=0.5, label=r'Referencia $\chi=0.01$')

            plt.title(r"Preferencialidad en el Arco vs. Ratio de Áreas" + "\n" + r"Comparativa $\chi=0.1$ y $\chi=0.01$")
            plt.xlabel(r"Ratio de Áreas ($A_{large}/A_{small}$)")
            plt.ylabel("Fracción de Chicas en el Arco")
            
            plt.legend(title=r'Fracción Global ($\chi$)', bbox_to_anchor=(1.05, 1), loc='upper left')
            sns.despine()
            plt.grid(True, alpha=0.3)
            
            plt.savefig(f"{OUT_DIR}/8-composicion-vs-ratio-areas.png", bbox_inches='tight', format='png')
            plt.close()
            plt.rcdefaults() 

    # =========================================================================
    # GRÁFICO 9: Morfología del Arco (Violin Plot de Tortuosidad)
    # =========================================================================
    print("  -> Generando Gráfico 9: Morfología del Arco (Tortuosidad)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)

        sistemas_a_excluir = ['Cuad-Cuad', 'Disco-Cuad', 'Disco-Pent', 'Disco-Tri']
        df_arcos = df_arcos[~df_arcos['system_type'].isin(sistemas_a_excluir)]
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty and 'Tortuosidad' in df_arcos_mezclas.columns:
            df_arcos_mezclas = df_arcos_mezclas.dropna(subset=['Tortuosidad'])
            
            cols_export_g6 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Tortuosidad']
            df_arcos_mezclas[cols_export_g6].to_csv(f"{OUT_DIR}/9-tortuosidad-arcos-data.csv", index=False)

            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(10, 6))

            ax = sns.violinplot(
                data=df_arcos_mezclas, x='system_type', y='Tortuosidad', hue='system_type',
                palette='Set2', inner='quartile', cut=0
            )

            plt.title("Morfología Estructural: Tortuosidad de los Arcos según Geometría")
            plt.xlabel("Geometría del Sistema")
            plt.ylabel("Tortuosidad del Arco (Longitud / Span)")
            
            sns.despine() 
            plt.grid(True, axis='y', alpha=0.3) 
            
            if ax.legend_ is not None:
                ax.legend_.remove()
            
            plt.savefig(f"{OUT_DIR}/9-tortuosidad-arcos.png", bbox_inches='tight', format='png')
            plt.close()
            plt.rcdefaults()

    # =========================================================================
    # GRÁFICO 9-b: Morfología del Arco (Violin Plot de Tortuosidad) - SOLO DISCO BASE
    # =========================================================================
    print("  -> Generando Gráfico 9-b: Morfología del Arco (Tortuosidad - Base Disco)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        df_arcos = df_arcos[df_arcos['system_type'] != 'Cuad-Cuad']

        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty and 'Tortuosidad' in df_arcos_mezclas.columns:
            df_arcos_mezclas = df_arcos_mezclas.dropna(subset=['Tortuosidad'])
            df_arcos_mezclas = df_arcos_mezclas[df_arcos_mezclas['system_type'].str.startswith('Disco')]
            
            cols_export_g6 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Tortuosidad']
            df_arcos_mezclas[cols_export_g6].to_csv(f"{OUT_DIR}/9b-tortuosidad-arcos-base-disco.csv", index=False)

            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            orden_sistemas = ['Disco-Disco', 'Disco-Tri', 'Disco-Cuad', 'Disco-Pent']
            orden_sistemas = [s for s in orden_sistemas if s in df_arcos_mezclas['system_type'].unique()]

            ax = sns.violinplot(
                data=df_arcos_mezclas, x='system_type', y='Tortuosidad', hue='system_type',
                order=orden_sistemas, palette='Set2', inner='quartile', cut=0
            )

            plt.title("Efecto del Aditivo: Tortuosidad de Arcos (Matriz de Discos)")
            plt.xlabel("Aditivo Inyectado en Matriz de Discos")
            plt.ylabel("Tortuosidad del Arco (Longitud / Span)")
            
            sns.despine() 
            plt.grid(True, axis='y', alpha=0.3) 
            
            if ax.legend_ is not None:
                ax.legend_.remove()
            
            plt.savefig(f"{OUT_DIR}/9b-tortuosidad-arcos-base-disco.png", bbox_inches='tight', format='png')
            plt.close()
            plt.rcdefaults()

    # =========================================================================
    # ESTADÍSTICA DE DISPERSIÓN (Grafico 10)
    # =========================================================================
    RAW_FLOW_PATH = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"
 
    if os.path.exists(RAW_FLOW_PATH) and os.path.exists(ARCOS_PATH):
        df_esqueleto_raw = pd.read_csv(RAW_FLOW_PATH)
        df_arcos_meta = pd.read_csv(ARCOS_PATH)
        
        df_arcos_meta = df_arcos_meta[df_arcos_meta['system_type'] != 'Cuad-Cuad']
        meta = df_arcos_meta[['sim_hash', 'system_type', 'chi']].drop_duplicates()
        df_raw = pd.merge(df_esqueleto_raw, meta, on='sim_hash', how='inner')

        print("  -> Generando Gráfico 10: Boxplot...")
        chi_max = df_raw['chi'].max()
        df_box = df_raw[np.isclose(df_raw['chi'], chi_max)].copy()
        df_box.to_csv(f"{OUT_DIR}/10-boxplot.csv", index=False)

        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df_box, x='system_type', y='tamano_big', hue='system_type', palette='Set3', legend=False)
        plt.yscale('log')
        
        plt.title(fr"Distribución de Avalanchas para $\chi \approx {chi_max:.2f}$")
        plt.ylabel("Tamaño de Avalancha (S) [Escala Log]")
        plt.xlabel("Sistema")
        plt.grid(True, axis='y', alpha=0.3)
        plt.savefig(f"{OUT_DIR}/10-boxplot-avalanchas.png", dpi=300, bbox_inches='tight')
        plt.close()

    print(f"[+] ¡Listo! Todos los gráficos y sus tablas de datos se guardaron en: {OUT_DIR}")

if __name__ == "__main__":
    main()