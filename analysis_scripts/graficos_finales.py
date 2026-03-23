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
    print("[+] Generando gráficos finales de alta calidad (SVG y CSV)...")
    
    if not os.path.exists(DATA_PATH):
        print(f" [!] Error: No se encontró {DATA_PATH}.")
        print("     Asegurate de correr el nuevo flow_analysis.py primero.")
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
        df_puros[cols_export].to_csv(f"{OUT_DIR}/1_puros_vs_orificio.csv", index=False)

        plt.figure(figsize=(8, 6))
        plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                     fmt='o-', color='black', capsize=4, label='Discos Puros')
        
        plt.xlabel(r"Ratio de Orificio $(D/d)^2$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title("Efecto del Tamaño del Orificio de Descarga")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(f"{OUT_DIR}/1_puros_vs_orificio.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 2: Disco-Disco vs Ratio de Áreas (Barrido de Tamaños)
    # =========================================================================
    print("  -> Generando Gráfico 2: Disco-Disco vs Tamaño Aditivo...")
    df_dd = df[(df['sistema'] == 'Disco(G)-Disco(C)') & (df['chi'] > 0.0)].copy()
    
    if not df_dd.empty:
        main_D_d_sq = df_dd['D_d_sq'].value_counts().idxmax()

        df_dd = df_dd[df_dd['D_d_sq'] == main_D_d_sq]
        
        df_base = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco')) & (df['D_d_sq'] == main_D_d_sq)]
        df_export_g2 = pd.concat([df_base, df_dd]).sort_values(['chi', 'area_ratio'])
        cols_export = ['sistema', 'chi', 'area_ratio', 'D_d_sq', 'S_mean', 'S_sem', 'log_S', 'log_S_err']
        
        # El CSV se exporta con TODOS los datos originales
        df_export_g2[cols_export].to_csv(f"{OUT_DIR}/2_disco_disco_vs_area_ratio.csv", index=False)


        chis_deseados = [0.2, 0.1, 0.14, 0.01]
        
        # Filtramos df_dd creando un nuevo df_plot para no alterar los datos originales
        df_plot = df_dd[df_dd['chi'].isin(chis_deseados)]
        # ---------------------------------------------------------

        plt.figure(figsize=(9, 6))
        if not df_base.empty:
            base_val = df_base['log_S'].mean()
            base_err = df_base['log_S_err'].mean()
            plt.axhline(base_val, color='black', linestyle='--', linewidth=2, label=r'Puro ($\chi = 0$)')
            x_min, x_max = df_plot['area_ratio'].min(), df_plot['area_ratio'].max() # Cambiado a df_plot
            plt.fill_between([x_min, x_max], base_val - base_err, base_val + base_err, color='black', alpha=0.1)

        # Cambiamos df_dd por df_plot aquí
        chis = np.sort(df_plot['chi'].unique())
        cmap = cm.plasma 
        norm = mcolors.Normalize(vmin=chis.min(), vmax=chis.max())

        for chi_val in chis:
            # Cambiamos df_dd por df_plot aquí también
            grp = df_plot[df_plot['chi'] == chi_val].sort_values('area_ratio')
            color_linea = cmap(norm(chi_val))
            plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'], 
                         fmt='s-', color=color_linea, label=rf"$\chi$ = {chi_val}", capsize=3, alpha=0.85, linewidth=1.5)
            
        plt.xlabel(r"Ratio de Áreas ($A_S/A_L$)")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Efecto del Tamaño del Aditivo (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        plt.legend(title="Concentración", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/2_disco_disco_vs_area_ratio.png", bbox_inches='tight', format='png')
        plt.close()



    # =========================================================================
    # GRÁFICO 3: log_S vs Concentración (chi) para Ratios de Área Específicos
    # =========================================================================
    print("  -> Generando Gráfico 3: log_S vs Concentración (chi)...")
    
    ratios_deseados = [0.1, 0.3, 0.4, 0.8, 1.0] #np.round(np.linspace(0.1, 1.0, 10), 1).tolist()
    
    # Filtrar datos de la mezcla
    df_mezcla = df[(df['sistema'] == 'Disco(G)-Disco(C)') & (df['chi'] > 0.0)].copy()
    
    if not df_mezcla.empty:
        # Mantener el orificio principal como en el gráfico anterior
        main_D_d_sq = df_mezcla['D_d_sq'].value_counts().idxmax()
        df_mezcla = df_mezcla[df_mezcla['D_d_sq'] == main_D_d_sq]
        
        # SOLUCIÓN 1: Crear una columna temporal redondeada para comparaciones seguras
        df_mezcla['area_ratio_round'] = df_mezcla['area_ratio'].round(3)
        
        # Filtrar el sistema puro (chi = 0) para el mismo orificio
        df_puro = df[(df['chi'] == 0.0) & (df['sistema'].str.startswith('Disco')) & (df['D_d_sq'] == main_D_d_sq)]
        
        plt.figure(figsize=(9, 6))
        
        # SOLUCIÓN 2: Mapa de colores automático basado en tus ratios
        cmap = cm.viridis # Cambia 'viridis' por 'plasma' o 'magma' si prefieres
        norm = mcolors.Normalize(vmin=min(ratios_deseados), vmax=max(ratios_deseados))
        
        # Obtener el valor del sistema puro para añadirlo a x=0
        puro_val, puro_err = None, None
        if not df_puro.empty:
            puro_val = df_puro['log_S'].mean()
            puro_err = df_puro['log_S_err'].mean()
            plt.errorbar([0], [puro_val], yerr=[puro_err], fmt='k*', markersize=10, 
                         label=r'Puro ($\chi = 0$)', capsize=3, zorder=5)

        # Iterar sobre los ratios de área y graficar
        for ar in ratios_deseados:
            # Usar la columna redondeada para filtrar
            grp = df_mezcla[df_mezcla['area_ratio_round'] == round(ar, 3)].sort_values('chi')
            
            if not grp.empty:
                x_data = grp['chi'].tolist()
                y_data = grp['log_S'].tolist()
                y_err = grp['log_S_err'].tolist()
                
                # Conectar la curva con el punto puro (chi=0) si existe
                if puro_val is not None:
                    x_data = [0.0] + x_data
                    y_data = [puro_val] + y_data
                    y_err = [puro_err] + y_err

                color_linea = cmap(norm(ar))

                plt.errorbar(x_data, y_data, yerr=y_err, 
                             fmt="o-", # Marcador genérico 'o' para todas las curvas
                             color=color_linea, 
                             label=rf"Ratio de Área = {ar}", 
                             capsize=3, alpha=0.85, linewidth=2)
            else:
                # Un aviso por consola por si pides un ratio que realmente no existe
                print(f"    - Aviso: No se encontraron datos para area_ratio = {ar}")
                
        plt.xlabel(r"Concentración ($\chi$)")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Tamaño de Avalancha vs Concentración (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        
        # Ajustar leyenda y grilla
        plt.legend(title="Configuración", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        
        # Guardar gráfico
        plt.savefig(f"{OUT_DIR}/3_logs_vs_chi.png", bbox_inches='tight', format='png')
        plt.close()



    # =========================================================================
    # GRÁFICO 4: Disco-Disco vs Chi (Barrido de Concentración por Tamaño)
    # =========================================================================
    min_puntos = 3
    
    print("  -> Generando Gráfico 4: Disco-Disco vs Chi (Superpuestos)...")
    if not df_dd.empty:
        plt.figure(figsize=(8, 6))
        for area_ratio, grp in df_dd.groupby('area_ratio'):
            # --- FILTRO AQUÍ ---
            if len(grp) < min_puntos:
                continue 
            # -------------------
            
            grp = grp.sort_values('chi')
            plt.errorbar(grp['chi'], grp['log_S'], yerr=grp['log_S_err'], 
                         fmt='^-', label=f"Ratio Área = {area_ratio:.2f}", capsize=4)
            
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Curvas de Atascamiento por Tamaño (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        plt.legend(title="Tamaño Aditivo", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/4_disco_disco_vs_chi_tamanos.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 5: Todas las Formas vs Chi (Normalizado)
    # =========================================================================
    print("  -> Generando Gráfico 5: Formas vs Chi (Normalizado)...")
    df_mezclas = df[~df['sistema'].str.contains('Puro')].copy()
    
    if 'main_D_d_sq' in locals():
        df_mezclas = df_mezclas[df_mezclas['D_d_sq'] == main_D_d_sq]

    df_puros_ref = df[df['chi'] == 0.0][['grano_base', 'D_d_sq', 'S_mean', 'S_sem']].drop_duplicates()
    df_puros_ref = df_puros_ref.rename(columns={'S_mean': 'S_mean_0', 'S_sem': 'S_sem_0'})
    df_formas = pd.merge(df_mezclas, df_puros_ref, on=['grano_base', 'D_d_sq'], how='inner')
    
    if not df_formas.empty:
        sistemas_interes = ['Disco(G)-Disco(C)', 'Disco(G)-Cuad(C)', 'Disco(G)-Pent(C)']
        df_formas = df_formas[df_formas['sistema'].isin(sistemas_interes)]

        df_formas['val_norm'] = df_formas['S_mean'] / df_formas['S_mean_0']
        df_formas['err_norm'] = df_formas['val_norm'] * np.sqrt(
            (df_formas['S_sem'] / df_formas['S_mean'])**2 + 
            (df_formas['S_sem_0'] / df_formas['S_mean_0'])**2
        )
        df_formas['log_S_norm'] = np.log(df_formas['val_norm'] + 1)
        df_formas['log_S_err_norm'] = df_formas['err_norm'] / (df_formas['val_norm'] + 1)

        plt.figure(figsize=(8, 6))
        marcadores = {'Disco(G)-Disco(C)': 'o', 'Disco(G)-Tri(C)': '^', 'Disco(G)-Cuad(C)': 's', 'Disco(G)-Pent(C)': 'p'}
        
        datos_g4_export = []

        for sis in df_formas['sistema'].unique():
            df_sis = df_formas[df_formas['sistema'] == sis]
            main_ar = df_sis['area_ratio'].value_counts().idxmax()
            grp = df_sis[df_sis['area_ratio'] == main_ar].sort_values('chi')
            
            x_vals = grp['chi'].tolist()
            y_vals = grp['log_S_norm'].tolist()
            y_errs = grp['log_S_err_norm'].tolist()
            
            if 0.0 not in x_vals:
                x_vals.insert(0, 0.0)
                y_vals.insert(0, np.log(2.0))
                y_errs.insert(0, 0.0)
                
            for x, y, err in zip(x_vals, y_vals, y_errs):
                datos_g4_export.append({'sistema': sis, 'area_ratio_fijado': main_ar, 'chi': x, 'log_S_norm': y, 'log_S_err_norm': err})
            
            marker = marcadores.get(sis, 'X')
            plt.errorbar(x_vals, y_vals, yerr=y_errs, fmt=f'{marker}-', 
                         label=f"{sis} (AR={main_ar:.2f})", capsize=4)

        pd.DataFrame(datos_g4_export).to_csv(f"{OUT_DIR}/plot4_Formas_vs_Chi_Norm_data.csv", index=False)

        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle / \langle S \rangle_0 + 1)$")
        plt.title("Efecto Geométrico de la Forma (Normalizado)")
        plt.legend(title="Geometría del Sistema", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/5_formas_vs_chi_norm.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 6: Composición del Arco vs. Composición Global
    # =========================================================================
    print("  -> Generando Gráfico 6: Composición Local vs Global (Arcos)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        df_arcos = df_arcos[df_arcos['system_type'] != 'Cuad-Cuad']

        # Nos aseguramos de analizar solo los casos con mezcla
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty:
            # Calculamos la fracción local para cada atasco individual
            df_arcos_mezclas['Fraccion_Chicas_Arco'] = df_arcos_mezclas['Particulas_Tipo_1'] / df_arcos_mezclas['Total_Particulas_Arco']
            
            # Exportamos la tabla filtrada para reproducibilidad
            cols_export_g5 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Particulas_Tipo_1', 'Fraccion_Chicas_Arco']
            df_arcos_mezclas[cols_export_g5].to_csv(f"{OUT_DIR}/6_composicion_arcos.csv", index=False)

            # Configuramos Seaborn para un look limpio y profesional
            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            # Seaborn agrupa automáticamente por 'chi' y dibuja el promedio con su intervalo de confianza (ci=95)
            ax = sns.lineplot(
                data=df_arcos_mezclas, 
                x='chi', 
                y='Fraccion_Chicas_Arco', 
                hue='system_type', 
                style='system_type',
                markers=True,
                dashes=False,
                linewidth=2.5,
                err_style="bars", 
                errorbar=('ci', 95),
                err_kws={'capsize': 4}
            )

            # Línea de referencia y = x (Mezcla perfectamente homogénea en el arco)
            min_chi = df_arcos_mezclas['chi'].min()
            max_chi = df_arcos_mezclas['chi'].max()
            # Ajustamos la línea desde 0 para que sea más clara la perspectiva
            plt.plot([0, max_chi], [0, max_chi], 'k--', linewidth=2, alpha=0.7, label='Mezcla Homogénea (y=x)')

            plt.title("Preferencialidad de Atascamiento:\nComposición del Arco vs. Composición Global")
            plt.xlabel(r"Fracción Global de Partículas Chicas ($\chi$)")
            plt.ylabel("Fracción de Chicas en el Arco")
            
            plt.legend(title='Geometría', bbox_to_anchor=(1.05, 1), loc='upper left')
            sns.despine() # Estilo limpio sin bordes superiores ni derechos
            plt.grid(True, alpha=0.3)
            
            plt.savefig(f"{OUT_DIR}/6_composicion_arcos.png", bbox_inches='tight', format='png')
            plt.close()
            
            plt.rcdefaults() 
        else:
            print("     ⚠️ No se detectaron casos de mezclas en el dataset de arcos.")
    else:
        print(f"     ⚠️ No se encontró {ARCOS_PATH}. Ejecutá primero la consolidación de arcos.")


    # =========================================================================
    # GRÁFICO 7: Composición del Arco vs. Composición Global por Tamaño
    # =========================================================================
    print("  -> Generando Gráfico 7: Composición Local vs Global (Arcos) por Tamaño de Aditivo...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        
        # 1. Calculamos el area_ratio base (como antes)
        if 'r_ratio' in df_arcos.columns:
            df_arcos['area_ratio'] = df_arcos['r_ratio'] ** 2
            if df_arcos['area_ratio'].max() > 1.1: 
                df_arcos['area_ratio'] = 1.0 / df_arcos['area_ratio']

        # Analizamos solo las mezclas de Disco-Disco
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['system_type'] == 'Disco-Disco')].copy()
        
        df_arcos_mezclas = df_arcos_mezclas[df_arcos_mezclas['Total_Particulas_Arco'] > 0]
        
        if not df_arcos_mezclas.empty and 'area_ratio' in df_arcos_mezclas.columns:
            target_area_ratios = [0.4, 0.6, 0.8]
            
            # Para filtrar de forma segura, primero redondeamos el area_ratio calculado
            df_arcos_mezclas['area_ratio_round'] = df_arcos_mezclas['area_ratio'].round(1)
            
            # Aplicamos el filtro: nos quedamos solo con los que están en la lista
            df_plot = df_arcos_mezclas[df_arcos_mezclas['area_ratio_round'].isin(target_area_ratios)].copy()
            # ---------------------------------------------------------
            
            if df_plot.empty:
                print(f"     ⚠️ Advertencia: No se encontraron datos para los ratios {target_area_ratios}. Verificalos.")
            else:
                # Calculamos la fracción local solo para los datos filtrados
                df_plot['Fraccion_Chicas_Arco'] = df_plot['Particulas_Tipo_1'] / df_plot['Total_Particulas_Arco']
                
                # Preparamos la variable categórica para Seaborn (0.1, 0.5, 0.9)
                # Usamos los valores ya redondeados y los convertimos a string
                col_agrupacion = 'area_ratio_round_str'
                df_plot[col_agrupacion] = df_plot['area_ratio_round'].astype(str)
                titulo_leyenda = 'Ratio de Área'
                
                # Ordenamos lógicamente para la leyenda
                orden_leyenda = sorted(df_plot[col_agrupacion].unique(), key=float)

                # Exportamos datos filtrados
                cols_export_g5 = ['sim_hash', col_agrupacion, 'chi', 'Total_Particulas_Arco', 'Particulas_Tipo_1', 'Fraccion_Chicas_Arco']
                cols_export_g5 = [c for c in cols_export_g5 if c in df_plot.columns]
                df_plot[cols_export_g5].to_csv(f"{OUT_DIR}/7_composicion_arcos_tamanos.csv", index=False)

                sns.set_theme(style="ticks", context="notebook")
                plt.figure(figsize=(9, 6))

                ax = sns.lineplot(
                    data=df_plot, 
                    x='chi', 
                    y='Fraccion_Chicas_Arco', 
                    hue=col_agrupacion, 
                    style=col_agrupacion,
                    hue_order=orden_leyenda,
                    style_order=orden_leyenda,
                    palette='viridis', 
                    markers=True,
                    dashes=False,
                    linewidth=2.5,
                    err_style="bars", 
                    errorbar=('ci', 95),
                    err_kws={'capsize': 4}
                )

                max_chi = df_plot['chi'].max()
                plt.plot([0, max_chi], [0, max_chi], 'k--', linewidth=2, alpha=0.7, label='Mezcla Homogénea (y=x)', zorder=0)

                plt.title("Preferencialidad de Atascamiento:\nComposición del Arco vs. Global (Discos - Filtrado)")
                plt.xlabel(r"Fracción Global de Partículas Chicas ($\chi$)")
                plt.ylabel("Fracción de Chicas en el Arco")
                
                handles, labels = ax.get_legend_handles_labels()
                plt.legend(handles=handles, labels=labels, title=titulo_leyenda, bbox_to_anchor=(1.05, 1), loc='upper left')
                
                sns.despine()
                plt.grid(True, alpha=0.3)
                
                # Cambié el nombre para que sepas que es el filtrado
                plt.savefig(f"{OUT_DIR}/7_composicion_arcos_tamanos.png", bbox_inches='tight', format='png')
                plt.close()
                
                plt.rcdefaults() 
                sns.reset_defaults()
        else:
            print("     ⚠️ No se pudo calcular 'area_ratio' para Disco-Disco en arcos.")
    else:
        print(f"     ⚠️ No se encontró {ARCOS_PATH}. Ejecutá primero la consolidación de arcos.")



    # =========================================================================
    # GRÁFICO 8: Composición del Arco vs. Ratio de ÁREAS (chi=0.1 vs chi=0.01)
    # =========================================================================
    print("  -> Generando Gráfico 8: Composición de Arcos vs Ratio de ÁREAS...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        
        # 1. Calculamos la fracción local en el arco
        df_arcos['Fraccion_Chicas_Arco'] = df_arcos['Particulas_Tipo_1'] / df_arcos['Total_Particulas_Arco']
        
        # 2. Calculamos el RATIO DE ÁREAS (Radio^2)
        # Asumiendo que r_ratio = R_grande / R_chico
        df_arcos['area_ratio'] = df_arcos['r_ratio']**2
        columna_x = 'area_ratio' 

        # 3. Filtramos para chi=0.1 y chi=0.01
        target_chis = [0.1, 0.01]
        df_plot = df_arcos[df_arcos['chi'].isin(target_chis)].copy()
        
        if not df_plot.empty:
            df_plot = df_plot.sort_values(by='chi', ascending=False)

            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            # Graficamos
            ax = sns.lineplot(
                data=df_plot, 
                x=columna_x, 
                y='Fraccion_Chicas_Arco', 
                hue='chi',
                palette="viridis",
                markers=True,
                dashes=False,
                linewidth=2.5,
                err_style="bars", 
                errorbar=('ci', 95),
                err_kws={'capsize': 4}
            )

            # Líneas de referencia para mezcla homogénea
            plt.axhline(y=0.1, color='green', linestyle='--', alpha=0.5, label=r'Referencia $\chi=0.1$')
            plt.axhline(y=0.01, color='purple', linestyle='--', alpha=0.5, label=r'Referencia $\chi=0.01$')

            plt.title(r"Preferencialidad en el Arco vs. Ratio de Áreas" + "\n" + r"Comparativa $\chi=0.1$ y $\chi=0.01$")
            plt.xlabel(r"Ratio de Áreas ($A_{large}/A_{small}$)")
            plt.ylabel("Fracción de Chicas en el Arco")
            
            plt.legend(title=r'Fracción Global ($\chi$)', bbox_to_anchor=(1.05, 1), loc='upper left')
            sns.despine()
            plt.grid(True, alpha=0.3)
            
            plt.savefig(f"{OUT_DIR}/8_composicion_vs_ratio_areas.png", bbox_inches='tight', format='png')
            plt.close()
            plt.rcdefaults() 
 

    # =========================================================================
    # GRÁFICO 9: Morfología del Arco (Violin Plot de Tortuosidad)
    # =========================================================================
    print("  -> Generando Gráfico 9: Morfología del Arco (Tortuosidad)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        df_arcos = df_arcos[df_arcos['system_type'] != 'Cuad-Cuad']

        # Filtramos un rango de mezcla representativo (excluimos chi=0 para ver solo el efecto del aditivo)
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty and 'Tortuosidad' in df_arcos_mezclas.columns:
            # Limpiamos posibles NaNs en la tortuosidad (por si algún arco falló en la medición)
            df_arcos_mezclas = df_arcos_mezclas.dropna(subset=['Tortuosidad'])
            
            # Exportamos los datos clave de este gráfico para reproducibilidad
            cols_export_g6 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Tortuosidad']
            df_arcos_mezclas[cols_export_g6].to_csv(f"{OUT_DIR}/plot6_Tortuosidad_Arcos_data.csv", index=False)

            # Configuramos Seaborn
            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(10, 6))

            # Creamos un Violin Plot
            # cut=0 evita que el violín extrapole y dibuje valores por debajo del mínimo real
            ax = sns.violinplot(
                data=df_arcos_mezclas, 
                x='system_type', 
                y='Tortuosidad', 
                hue='system_type',
                palette='Set2', 
                inner='quartile', # Dibuja las líneas punteadas de los cuartiles adentro del violín
                cut=0
            )

            plt.title("Morfología Estructural: Tortuosidad de los Arcos según Geometría")
            plt.xlabel("Geometría del Sistema")
            plt.ylabel("Tortuosidad del Arco (Longitud / Span)")
            
            sns.despine() # Limpia el gráfico
            plt.grid(True, axis='y', alpha=0.3) # Solo líneas horizontales para comparar alturas
            
            # Ajustamos la leyenda si es redundante, o la quitamos ya que el eje X tiene los nombres
            if ax.legend_ is not None:
                ax.legend_.remove()
            
            plt.savefig(f"{OUT_DIR}/9_tortuosidad_arcos.png", bbox_inches='tight', format='png')
            plt.close()
            
            plt.rcdefaults()
        else:
            print("     ⚠️ No se encontró la columna 'Tortuosidad' o no hay datos válidos.")

    # =========================================================================
    # GRÁFICO 9-b: Morfología del Arco (Violin Plot de Tortuosidad) - SOLO DISCO BASE
    # =========================================================================
    print("  -> Generando Gráfico 9-b: Morfología del Arco (Tortuosidad - Base Disco)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        df_arcos = df_arcos[df_arcos['system_type'] != 'Cuad-Cuad']

        # Filtramos un rango de mezcla representativo (excluimos chi=0 para ver solo el efecto del aditivo)
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty and 'Tortuosidad' in df_arcos_mezclas.columns:
            # Limpiamos posibles NaNs en la tortuosidad
            df_arcos_mezclas = df_arcos_mezclas.dropna(subset=['Tortuosidad'])
            
            # --- NUEVO FILTRO: DEJAR SOLO LOS SISTEMAS DONDE LA BASE ES DISCO ---
            df_arcos_mezclas = df_arcos_mezclas[df_arcos_mezclas['system_type'].str.startswith('Disco')]
            
            # Exportamos los datos clave de este gráfico para reproducibilidad
            cols_export_g6 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Tortuosidad']
            df_arcos_mezclas[cols_export_g6].to_csv(f"{OUT_DIR}/9b_tortuosidad_arcos_base_disco.csv", index=False)

            # Configuramos Seaborn
            sns.set_theme(style="ticks", context="notebook")
            plt.figure(figsize=(9, 6))

            # Ordenamos explícitamente para que quede lindo en el gráfico
            orden_sistemas = ['Disco-Disco', 'Disco-Tri', 'Disco-Cuad', 'Disco-Pent']
            # Filtramos el orden solo a los que realmente existen en el dataset
            orden_sistemas = [s for s in orden_sistemas if s in df_arcos_mezclas['system_type'].unique()]

            # Creamos el Violin Plot
            ax = sns.violinplot(
                data=df_arcos_mezclas, 
                x='system_type', 
                y='Tortuosidad', 
                hue='system_type',
                order=orden_sistemas, # Forzamos el orden visual
                palette='Set2', 
                inner='quartile', 
                cut=0
            )

            plt.title("Efecto del Aditivo: Tortuosidad de Arcos (Matriz de Discos)")
            plt.xlabel("Aditivo Inyectado en Matriz de Discos")
            plt.ylabel("Tortuosidad del Arco (Longitud / Span)")
            
            sns.despine() 
            plt.grid(True, axis='y', alpha=0.3) 
            
            # Borramos la leyenda si Seaborn la crea, ya que es redundante con el Eje X
            if ax.legend_ is not None:
                ax.legend_.remove()
            
            plt.savefig(f"{OUT_DIR}/9b_tortuosidad_arcos_base_disco.png", bbox_inches='tight', format='png')
            plt.close()
            
            plt.rcdefaults()
        else:
            print("     ⚠️ No se encontró la columna 'Tortuosidad' o no hay datos válidos.")



    # =========================================================================
    # ESTADÍSTICA DE DISPERSIÓN (Grafico 10)
    # =========================================================================
    RAW_FLOW_PATH = "/work/lab/project/sim-binary-shapes-2d/processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"

    if os.path.exists(RAW_FLOW_PATH) and os.path.exists(ARCOS_PATH):
        # Leemos los datos crudos de avalanchas (esqueleto) para tener el 'sim_hash'
        df_esqueleto_raw = pd.read_csv(RAW_FLOW_PATH)
        df_arcos_meta = pd.read_csv(ARCOS_PATH)
        
        df_arcos_meta = df_arcos_meta[df_arcos_meta['system_type'] != 'Cuad-Cuad']

        # Mapeo: sim_hash -> system_type, chi
        meta = df_arcos_meta[['sim_hash', 'system_type', 'chi']].drop_duplicates()
        
        # Merge de datos crudos con metadatos del sistema
        df_raw = pd.merge(df_esqueleto_raw, meta, on='sim_hash', how='inner')

        # --- GRÁFICO 13: Boxplot (Distribución de Avalanchas) ---
        print("  -> Generando Gráfico 10: Boxplot...")
        chi_max = df_raw['chi'].max()
        df_box = df_raw[np.isclose(df_raw['chi'], chi_max)].copy()
        df_box.to_csv(f"{OUT_DIR}/10_boxplot.csv", index=False)

        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df_box, x='system_type', y='tamano_big', hue='system_type', palette='Set3', legend=False)
        plt.yscale('log')
        
        # NOTA: Usamos fr"..." para que el \approx no de error
        plt.title(fr"Distribución de Avalanchas para $\chi \approx {chi_max:.2f}$")
        plt.ylabel("Tamaño de Avalancha (S) [Escala Log]")
        plt.xlabel("Sistema")
        plt.grid(True, axis='y', alpha=0.3)
        plt.savefig(f"{OUT_DIR}/10_boxplot_avalanchas.png", dpi=300, bbox_inches='tight')
        plt.close()
    else:
        print(f"     ⚠️ No se encontró el archivo de esqueleto crudo para los gráficos de dispersión.")

    print(f"[+] ¡Listo! Todos los gráficos y sus tablas de datos se guardaron en: {OUT_DIR}")

if __name__ == "__main__":
    main()