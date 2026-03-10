import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import seaborn as sns # <-- NUEVA LIBRERÍA PARA EL GRÁFICO 5

# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================
DATA_PATH = "../processed_data/1_avalanche_data/estadisticas_flujo_agregadas.csv"
ARCOS_PATH = "../processed_data/1_avalanche_data/resultados_completos_arcos.csv"
OUT_DIR = "../processed_data/5_graficos_finales"

def main():
    print("[+] Generando gráficos finales de alta calidad (SVG y CSV)...")
    
    if not os.path.exists(DATA_PATH):
        print(f" [!] Error: No se encontró {DATA_PATH}.")
        print("     Asegurate de correr el nuevo flow_analysis.py primero.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(DATA_PATH)

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
        df_puros[cols_export].to_csv(f"{OUT_DIR}/plot1_Puros_vs_Orificio_data.csv", index=False)

        plt.figure(figsize=(8, 6))
        plt.errorbar(df_puros['D_d_sq'], df_puros['log_S'], yerr=df_puros['log_S_err'], 
                     fmt='o-', color='black', capsize=4, label='Discos Puros')
        
        plt.xlabel(r"Ratio de Orificio $(D/d)^2$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title("Efecto del Tamaño del Orificio de Descarga")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig(f"{OUT_DIR}/plot1_Puros_vs_Orificio.png", bbox_inches='tight', format='png')
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
        df_export_g2[cols_export].to_csv(f"{OUT_DIR}/plot2_DiscoDisco_vs_AreaRatio_data.csv", index=False)

        plt.figure(figsize=(9, 6))
        if not df_base.empty:
            base_val = df_base['log_S'].mean()
            base_err = df_base['log_S_err'].mean()
            plt.axhline(base_val, color='black', linestyle='--', linewidth=2, label=r'Puro ($\chi = 0$)')
            x_min, x_max = df_dd['area_ratio'].min(), df_dd['area_ratio'].max()
            plt.fill_between([x_min, x_max], base_val - base_err, base_val + base_err, color='black', alpha=0.1)

        chis = np.sort(df_dd['chi'].unique())
        cmap = cm.plasma 
        norm = mcolors.Normalize(vmin=chis.min(), vmax=chis.max())

        for chi_val in chis:
            grp = df_dd[df_dd['chi'] == chi_val].sort_values('area_ratio')
            color_linea = cmap(norm(chi_val))
            plt.errorbar(grp['area_ratio'], grp['log_S'], yerr=grp['log_S_err'], 
                         fmt='s-', color=color_linea, label=f"$\chi$ = {chi_val}", capsize=3, alpha=0.85, linewidth=1.5)
            
        plt.xlabel(r"Ratio de Áreas ($A_S/A_L$)")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Efecto del Tamaño del Aditivo (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        plt.legend(title="Concentración", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/plot2_DiscoDisco_vs_AreaRatio.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 3: Disco-Disco vs Chi (Barrido de Concentración por Tamaño)
    # =========================================================================
    print("  -> Generando Gráfico 3: Disco-Disco vs Chi (Superpuestos)...")
    if not df_dd.empty:
        plt.figure(figsize=(8, 6))
        for area_ratio, grp in df_dd.groupby('area_ratio'):
            grp = grp.sort_values('chi')
            plt.errorbar(grp['chi'], grp['log_S'], yerr=grp['log_S_err'], 
                         fmt='^-', label=f"Ratio Área = {area_ratio:.2f}", capsize=4)
            
        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle + 1)$")
        plt.title(f"Curvas de Atascamiento por Tamaño (Orificio $(D/d)^2 = {main_D_d_sq:.2f}$)")
        plt.legend(title="Tamaño Aditivo", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/plot3_DiscoDisco_vs_Chi_Tamanos.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 4: Todas las Formas vs Chi (Normalizado)
    # =========================================================================
    print("  -> Generando Gráfico 4: Formas vs Chi (Normalizado)...")
    df_mezclas = df[~df['sistema'].str.contains('Puro')].copy()
    
    if 'main_D_d_sq' in locals():
        df_mezclas = df_mezclas[df_mezclas['D_d_sq'] == main_D_d_sq]

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
        plt.savefig(f"{OUT_DIR}/plot4_Formas_vs_Chi_Norm.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 5: Composición del Arco vs. Composición Global (NUEVO)
    # =========================================================================
    print("  -> Generando Gráfico 5: Composición Local vs Global (Arcos)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        
        # Nos aseguramos de analizar solo los casos con mezcla
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty:
            # Calculamos la fracción local para cada atasco individual
            df_arcos_mezclas['Fraccion_Chicas_Arco'] = df_arcos_mezclas['Particulas_Tipo_1'] / df_arcos_mezclas['Total_Particulas_Arco']
            
            # Exportamos la tabla filtrada para reproducibilidad
            cols_export_g5 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Particulas_Tipo_1', 'Fraccion_Chicas_Arco']
            df_arcos_mezclas[cols_export_g5].to_csv(f"{OUT_DIR}/plot5_Composicion_Arcos_data.csv", index=False)

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
            
            plt.savefig(f"{OUT_DIR}/plot5_Composicion_Arcos.png", bbox_inches='tight', format='png')
            plt.close()
            
            # Restauramos el estilo original de Matplotlib por si agregamos más gráficos luego
            plt.rcdefaults() 
        else:
            print("     ⚠️ No se detectaron casos de mezclas en el dataset de arcos.")
    else:
        print(f"     ⚠️ No se encontró {ARCOS_PATH}. Ejecutá primero la consolidación de arcos.")


    # =========================================================================
    # GRÁFICO 6: Morfología del Arco (Violin Plot de Tortuosidad)
    # =========================================================================
    print("  -> Generando Gráfico 6: Morfología del Arco (Tortuosidad)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        
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
            
            plt.savefig(f"{OUT_DIR}/plot6_Tortuosidad_Arcos.png", bbox_inches='tight', format='png')
            plt.close()
            
            # Restauramos el estilo base por si corremos más cosas
            plt.rcdefaults()
        else:
            print("     ⚠️ No se encontró la columna 'Tortuosidad' o no hay datos válidos.")

    # =========================================================================
    # GRÁFICO 6-b: Morfología del Arco (Violin Plot de Tortuosidad) - SOLO DISCO BASE
    # =========================================================================
    print("  -> Generando Gráfico 6: Morfología del Arco (Tortuosidad - Base Disco)...")
    if os.path.exists(ARCOS_PATH):
        df_arcos = pd.read_csv(ARCOS_PATH)
        
        # Filtramos un rango de mezcla representativo (excluimos chi=0 para ver solo el efecto del aditivo)
        df_arcos_mezclas = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['chi'] <= 0.2)].copy()
        
        if not df_arcos_mezclas.empty and 'Tortuosidad' in df_arcos_mezclas.columns:
            # Limpiamos posibles NaNs en la tortuosidad
            df_arcos_mezclas = df_arcos_mezclas.dropna(subset=['Tortuosidad'])
            
            # --- NUEVO FILTRO: DEJAR SOLO LOS SISTEMAS DONDE LA BASE ES DISCO ---
            df_arcos_mezclas = df_arcos_mezclas[df_arcos_mezclas['system_type'].str.startswith('Disco')]
            
            # Exportamos los datos clave de este gráfico para reproducibilidad
            cols_export_g6 = ['sim_hash', 'system_type', 'chi', 'Total_Particulas_Arco', 'Tortuosidad']
            df_arcos_mezclas[cols_export_g6].to_csv(f"{OUT_DIR}/plot6_Tortuosidad_Arcos_BaseDisco_data.csv", index=False)

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
            
            plt.savefig(f"{OUT_DIR}/plot6_Tortuosidad_Arcos_BaseDisco.png", bbox_inches='tight', format='png')
            plt.close()
            
            plt.rcdefaults()
        else:
            print("     ⚠️ No se encontró la columna 'Tortuosidad' o no hay datos válidos.")


    # =========================================================================
    # GRÁFICO 7: Efecto Estructural vs Efecto de Dilución
    # =========================================================================
    print("  -> Generando Gráfico 7: Corrección por Dilución (Efecto Estructural Puro)...")
    if 'df_formas' in locals() and not df_formas.empty:
        df_dilucion = df_formas.copy()
        
        # Aplicamos la corrección matemática: S_real = S_medido / (1 - chi)
        # Esto estima cuántas partículas totales (grandes + chicas) cayeron en la avalancha
        df_dilucion['val_norm_corregido'] = (df_dilucion['S_mean'] / (1 - df_dilucion['chi'])) / df_dilucion['S_mean_0']
        df_dilucion['log_S_norm_corr'] = np.log(df_dilucion['val_norm_corregido'] + 1)
        
        # Asumimos un error similar propagado
        df_dilucion['log_S_err_norm_corr'] = df_dilucion['log_S_err_norm'] # Simplificación visual
        
        plt.figure(figsize=(9, 6))
        
        # Vamos a graficar SOLO un par de sistemas contrastantes para que sea claro
        sistemas_clave = ['Disco(G)-Disco(C)', 'Cuad(G)-Cuad(C)'] # Cambialos si querés ver otros
        sistemas_presentes = [s for s in sistemas_clave if s in df_dilucion['sistema'].unique()]
        
        colores = {'Disco(G)-Disco(C)': 'tab:blue', 'Cuad(G)-Cuad(C)': 'tab:red'}
        
        for sis in sistemas_presentes:
            df_sis = df_dilucion[df_dilucion['sistema'] == sis]
            main_ar = df_sis['area_ratio'].value_counts().idxmax()
            grp = df_sis[df_sis['area_ratio'] == main_ar].sort_values('chi')
            
            x_vals = grp['chi'].tolist()
            # Datos crudos (con sesgo de dilución)
            y_crudo = grp['log_S_norm'].tolist()
            # Datos corregidos (física pura)
            y_corr = grp['log_S_norm_corr'].tolist()
            
            if 0.0 not in x_vals:
                x_vals.insert(0, 0.0)
                y_crudo.insert(0, np.log(2.0))
                y_corr.insert(0, np.log(2.0))
            
            color = colores.get(sis, 'black')
            
            # Línea punteada: Lo que mide el código (sesgado)
            plt.plot(x_vals, y_crudo, f'o--', color=color, alpha=0.4, label=f"{sis} (Sin corregir)")
            # Línea continua: La física real de la estructura
            plt.plot(x_vals, y_corr, f's-', color=color, linewidth=2.5, label=f"{sis} (Corregido)")

        plt.xlabel(r"Concentración $\chi$")
        plt.ylabel(r"$\ln(\langle S \rangle / \langle S \rangle_0 + 1)$")
        plt.title("Efecto de Dilución vs. Efecto Estructural Real")
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.savefig(f"{OUT_DIR}/plot7_Correccion_Dilucion.png", bbox_inches='tight', format='png')
        plt.close()

    # =========================================================================
    # GRÁFICO 9: Robustez del Arco (Total Partículas)
    # =========================================================================
    print("  -> Generando Gráfico 9: Robustez del Arco...")
    df_a9 = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['system_type'].str.startswith('Disco'))].copy()
    
    if not df_a9.empty:
        # GUARDAR CSV DEL GRÁFICO 9
        df_a9[['system_type', 'chi', 'Total_Particulas_Arco']].to_csv(f"{OUT_DIR}/plot9_Robustez_Arcos_data.csv", index=False)

        plt.figure(figsize=(9, 6))
        sns.kdeplot(data=df_a9, x='Total_Particulas_Arco', hue='system_type', fill=True, alpha=0.3, linewidth=2)
        plt.title("Robustez: ¿Cuántas partículas forman el arco?")
        plt.xlim(0, df_a9['Total_Particulas_Arco'].quantile(0.98))
        plt.savefig(f"{OUT_DIR}/plot9_Robustez_Arcos.png", bbox_inches='tight')
        plt.close()

    # =========================================================================
    # GRÁFICO 10: Espacio de Fases (Span vs Altura)
    # =========================================================================
    print("  -> Generando Gráfico 10: Espacio de Fases (Span vs Altura)...")
    df_a10 = df_arcos[(df_arcos['chi'] > 0.0) & (df_arcos['system_type'].isin(['Disco-Disco', 'Disco-Cuad']))].copy()
    
    if not df_a10.empty:
        df_a10['Fraccion_Chicas'] = df_a10['Particulas_Tipo_1'] / df_a10['Total_Particulas_Arco']
        
        # GUARDAR CSV DEL GRÁFICO 10
        df_a10[['system_type', 'Span', 'Altura', 'Fraccion_Chicas']].to_csv(f"{OUT_DIR}/plot10_EspacioFases_data.csv", index=False)

        g = sns.FacetGrid(df_a10, col="system_type", height=6)
        g.map_dataframe(sns.scatterplot, x="Span", y="Altura", hue="Fraccion_Chicas", palette="viridis", alpha=0.5)
        
        for ax in g.axes.flat:
            x = np.linspace(df_a10['Span'].min(), df_a10['Span'].max(), 10)
            ax.plot(x, x/2, 'r--', label='Semicírculo') # Referencia geométrica
            
        plt.savefig(f"{OUT_DIR}/plot10_EspacioFases_Arcos.png", bbox_inches='tight', dpi=300)
        plt.close()
    

    # =========================================================================
    # ESTADÍSTICA DE DISPERSIÓN (Graficos 11, 12 y 13)
    # =========================================================================
    RAW_FLOW_PATH = "../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"

    if os.path.exists(RAW_FLOW_PATH) and os.path.exists(ARCOS_PATH):
        # Leemos los datos crudos de avalanchas (esqueleto) para tener el 'sim_hash'
        df_esqueleto_raw = pd.read_csv(RAW_FLOW_PATH)
        df_arcos_meta = pd.read_csv(ARCOS_PATH)
        
        # Mapeo: sim_hash -> system_type, chi
        meta = df_arcos_meta[['sim_hash', 'system_type', 'chi']].drop_duplicates()
        
        # Merge de datos crudos con metadatos del sistema
        df_raw = pd.merge(df_esqueleto_raw, meta, on='sim_hash', how='inner')

        # Estadísticas agrupadas para CV y Fluctuaciones
        stats_disp = df_raw.groupby(['system_type', 'chi'])['tamano_big'].agg(['mean', 'std']).reset_index()
        stats_disp['cv'] = stats_disp['std'] / stats_disp['mean']

        # --- GRÁFICO 11: Coeficiente de Variación (CV) ---
        print("  -> Generando Gráfico 11: CV...")
        stats_disp.to_csv(f"{OUT_DIR}/plot11_CV_data.csv", index=False)
        
        plt.figure(figsize=(9, 6))
        sns.lineplot(data=stats_disp, x='chi', y='cv', hue='system_type', marker='o', linewidth=2)
        plt.axhline(1.0, color='black', linestyle='--', alpha=0.5, label='Límite Poisson (CV=1)')
        
        plt.title("Estabilidad del Flujo: Coeficiente de Variación")
        plt.ylabel(r"CV ($\sigma / \mu$)")
        plt.xlabel(r"Concentración $\chi$")
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.savefig(f"{OUT_DIR}/plot11_CV_vs_Chi.png", dpi=300, bbox_inches='tight')
        plt.close()

        # --- GRÁFICO 12: Scaling de Fluctuaciones (Sigma vs Mu) ---
        print("  -> Generando Gráfico 12: Fluctuaciones...")
        stats_disp.to_csv(f"{OUT_DIR}/plot12_Fluctuaciones_data.csv", index=False)
        
        plt.figure(figsize=(8, 8))
        sns.scatterplot(data=stats_disp, x='mean', y='std', hue='system_type', s=100, alpha=0.8)
        
        # Referencia Poissoniana (sigma = sqrt(mu))
        x_ref = np.logspace(np.log10(stats_disp['mean'].min()), np.log10(stats_disp['mean'].max()), 100)
        plt.plot(x_ref, np.sqrt(x_ref), 'k--', alpha=0.5, label=r'Poisson ($\sigma = \sqrt{\mu}$)')
        
        plt.xscale('log')
        plt.yscale('log')
        plt.title(r"Scaling de Fluctuaciones: $\sigma$ vs $\mu$")
        plt.xlabel(r"Promedio de Avalancha ($\mu$)")
        plt.ylabel(r"Desviación Estándar ($\sigma$)")
        plt.grid(True, which="both", alpha=0.2)
        plt.legend()
        plt.savefig(f"{OUT_DIR}/plot12_Fluctuaciones_Scaling.png", dpi=300, bbox_inches='tight')
        plt.close()

        # --- GRÁFICO 13: Boxplot (Distribución de Avalanchas) ---
        print("  -> Generando Gráfico 13: Boxplot...")
        chi_max = df_raw['chi'].max()
        df_box = df_raw[np.isclose(df_raw['chi'], chi_max)].copy()
        df_box.to_csv(f"{OUT_DIR}/plot13_Boxplot_data.csv", index=False)

        plt.figure(figsize=(10, 6))
        sns.boxplot(data=df_box, x='system_type', y='tamano_big', hue='system_type', palette='Set3', legend=False)
        plt.yscale('log')
        
        # NOTA: Usamos fr"..." para que el \approx no de error
        plt.title(fr"Distribución de Avalanchas para $\chi \approx {chi_max:.2f}$")
        plt.ylabel("Tamaño de Avalancha (S) [Escala Log]")
        plt.xlabel("Sistema")
        plt.grid(True, axis='y', alpha=0.3)
        plt.savefig(f"{OUT_DIR}/plot13_Boxplot_Avalanchas.png", dpi=300, bbox_inches='tight')
        plt.close()
    else:
        print(f"     ⚠️ No se encontró el archivo de esqueleto crudo para los gráficos de dispersión.")

    print(f"[+] ¡Listo! Todos los gráficos y sus tablas de datos se guardaron en: {OUT_DIR}")

if __name__ == "__main__":
    main()